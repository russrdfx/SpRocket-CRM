"""PostgreSQL transport for the existing parameterized CRM queries."""
import re,sqlite3
class Row(dict):
    def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
def row_factory(cursor):
    names=[c.name for c in (cursor.description or [])]
    return lambda values:Row(zip(names,values))
class Database:
    def __init__(self,url):
        import psycopg
        self.conn=psycopg.connect(url,row_factory=row_factory)
    def execute(self,sql,params=()):
        import psycopg
        if sql=="SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_logs'":sql="SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='calendar_logs'"
        if sql.startswith('CREATE TABLE '):sql=re.sub(r'\bREAL\b','DOUBLE PRECISION',sql)
        if sql.startswith('INSERT OR IGNORE '):sql=sql.replace('INSERT OR IGNORE ','INSERT ',1)+' ON CONFLICT DO NOTHING'
        # Only placeholders outside SQL literals are translated. Percent signs are escaped for psycopg.
        parts=re.split(r"('(?:''|[^'])*')",sql)
        sql=''.join(p.replace('%','%%').replace('?','%s') if i%2==0 else p.replace('%','%%') for i,p in enumerate(parts))
        try:return self.conn.execute(sql,params)
        except psycopg.IntegrityError as e:raise sqlite3.IntegrityError('Database constraint failed.') from e
    def executescript(self,script):
        pending=[s.strip() for s in script.split(';') if s.strip()]
        # SQLite permits forward references in CREATE TABLE; PostgreSQL requires the referenced table first.
        names={re.search(r'CREATE TABLE IF NOT EXISTS (\w+)',s).group(1) for s in pending}
        while pending:
            ready=[s for s in pending if not set(re.findall(r'REFERENCES (\w+)',s)).intersection(names)]
            if not ready:raise ValueError('Cyclic schema dependency.')
            for sql in ready:
                self.execute(sql);pending.remove(sql);m=re.search(r'CREATE TABLE IF NOT EXISTS (\w+)',sql)
                if m:names.discard(m.group(1))
    def __enter__(self):return self
    def __exit__(self,typ,value,trace):
        try:self.conn.rollback() if typ else self.conn.commit()
        finally:self.conn.close()
    def close(self):self.conn.close()
