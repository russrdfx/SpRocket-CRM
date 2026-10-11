"""Admin-only SQLite snapshot download and validated transactional restore."""
import base64,hashlib,json,os,sqlite3,tempfile,time,uuid
from pathlib import Path

MAX_BYTES=24000000
class Recovery:
    def __init__(self,connect,path):self.connect=connect;self.path=path;self.pending={}
    def snapshot(self):
        fd,name=tempfile.mkstemp(suffix='.db');os.close(fd)
        try:
            with self.connect() as source,sqlite3.connect(name) as target:source.backup(target)
            content=Path(name).read_bytes()
            if len(content)>MAX_BYTES:raise ValueError('This database exceeds the 24 MB browser limit. Use the desktop File → Back Up Database option.')
            return content
        finally:Path(name).unlink(missing_ok=True)
    def download(self):
        content=self.snapshot();return dict(data=base64.b64encode(content).decode(),sha256=hashlib.sha256(content).hexdigest(),filename='SpRocket-backup-'+time.strftime('%Y-%m-%d-%H%M%S')+'.db')
    def fingerprint(self,db):
        # All durable table contents, not only records, protect changes since review.
        digest=hashlib.sha256()
        for table in sorted(r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")):
            digest.update(table.encode())
            for row in sorted([repr(tuple(r)) for r in db.execute('SELECT * FROM "'+table+'"')]):digest.update(row.encode())
        return digest.hexdigest()
    def preview(self,owner,data,validate_settings,validate_record):
        try:content=base64.b64decode(data.get('data',''),validate=True)
        except (ValueError,TypeError):raise ValueError('Choose a SQLite backup file.') from None
        if len(content)>MAX_BYTES or not content.startswith(b'SQLite format 3\x00'):raise ValueError('Choose a SQLite database up to 24 MB.')
        fd,name=tempfile.mkstemp(suffix='.db');os.close(fd);Path(name).write_bytes(content)
        try:
            with self.connect() as live,sqlite3.connect('file:'+name+'?mode=ro',uri=True) as backup:
                backup.row_factory=sqlite3.Row;backup.execute('PRAGMA trusted_schema=OFF')
                if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or backup.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Backup failed integrity checks.')
                if backup.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():raise ValueError('Backups containing triggers or views are not supported.')
                def schema(db):return {r[0]:[tuple(c)[1:6] for c in db.execute('PRAGMA table_info("'+r[0]+'")')] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                if schema(backup)!=schema(live):raise ValueError('Use a backup created by this version of SpRocket CRM. Older database migration is not supported in browser restore.')
                settings=json.loads(backup.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]);records=backup.execute('SELECT * FROM records').fetchall();validate_settings(settings,settings,records)
                for record in records:validate_record(backup,record['kind'],json.loads(record['body']))
                # Read data only. Never execute SQL/schema supplied by the upload.
                tables={table:[tuple(row) for row in backup.execute('SELECT * FROM "'+table+'"')] for table in schema(backup)}
                baseline=self.fingerprint(live)
        except (sqlite3.Error,IndexError,TypeError,KeyError):raise ValueError('Backup is invalid or incompatible. No data was changed.') from None
        finally:Path(name).unlink(missing_ok=True)
        ident=str(uuid.uuid4());self.pending={k:v for k,v in self.pending.items() if v['expires']>time.time()}
        if len(self.pending)>=3:self.pending.pop(next(iter(self.pending)))
        self.pending[ident]=dict(owner=owner,expires=time.time()+600,tables=tables,baseline=baseline)
        return dict(id=ident,records=len(records),workspace=settings['name'],activities=len(tables['activities']),sha256=hashlib.sha256(content).hexdigest())
    def apply(self,owner,data):
        job=self.pending.get(data.get('id'))
        if not job or job['owner']!=owner or job['expires']<time.time() or data.get('confirm')!='RESTORE':raise ValueError('Review the backup and type RESTORE to confirm.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.fingerprint(db)!=job['baseline']:raise ValueError('Workspace changed after preview. Review the backup again.')
            folder=self.path().parent/'backups';folder.mkdir(parents=True,exist_ok=True,mode=0o700);name=folder/('before-restore-'+str(uuid.uuid4())+'.db')
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
            # Reserved write lock prevents other writers; a second reader takes the current snapshot.
            with self.connect() as source,sqlite3.connect(name) as target:source.backup(target)
            os.chmod(name,0o600);db.execute('PRAGMA defer_foreign_keys=ON')
            for table in job['tables']:db.execute('DELETE FROM "'+table+'"')
            for table,rows in job['tables'].items():
                if rows:db.executemany('INSERT INTO "'+table+'" VALUES('+','.join('?' for _ in rows[0])+')',rows)
        self.pending.pop(data['id'],None);return dict(ok=True,safety_backup=name.name)
