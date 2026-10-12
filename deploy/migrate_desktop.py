"""Copy desktop records into an empty web workspace; never copy credentials or sessions."""
import argparse,json,os,sqlite3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from web_database import Database

def migrate(path,url,apply=False):
    source=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Source database failed integrity checks.')
        settings=source.execute('SELECT body FROM settings WHERE id=1').fetchone()
        if not settings:raise ValueError('Source settings are missing.')
        parsed=json.loads(settings[0]);records=source.execute('SELECT * FROM records').fetchall();activities=source.execute('SELECT * FROM activities').fetchall()
        counts={'records':len(records),'activities':len(activities)}
        with Database(url) as target:
            target.execute('LOCK TABLE records,activities,settings IN EXCLUSIVE MODE')
            if target.execute('SELECT 1 FROM records LIMIT 1').fetchone():raise ValueError('The web workspace must have no records before migration.')
            from server import validate_settings,validate_record
            validate_settings(parsed,parsed,records)
            for row in records:target.execute('INSERT INTO records VALUES (?,?,?,?)',tuple(row))
            target.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(parsed),))
            for row in records:validate_record(target,row['kind'],json.loads(row['body']))
            for row in activities:target.execute('INSERT INTO activities VALUES (?,?,?,?)',tuple(row))
            if not apply:target.conn.rollback()
        return counts
    finally:source.close()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not os.environ.get('DATABASE_URL'):parser.error('Set DATABASE_URL to the destination web workspace.')
    print(('Imported ' if args.apply else 'Preview; no changes saved: ')+json.dumps(migrate(args.source,os.environ['DATABASE_URL'],args.apply)))
