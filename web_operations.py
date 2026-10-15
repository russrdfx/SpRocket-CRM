"""Host job health; no credentials, provider payloads or private inbox contents."""
import time,json,os
from datetime import datetime,timezone
from pathlib import Path

def initialize(db):
    db.execute("CREATE TABLE IF NOT EXISTS web_job_health(id INTEGER PRIMARY KEY CHECK(id=1),started DOUBLE PRECISION NOT NULL DEFAULT 0,finished DOUBLE PRECISION NOT NULL DEFAULT 0,last_success DOUBLE PRECISION NOT NULL DEFAULT 0,failures INTEGER NOT NULL DEFAULT 0)")
    db.execute('INSERT INTO web_job_health(id) VALUES(1) ON CONFLICT(id) DO NOTHING')

def started(connect):
    with connect() as db:db.execute('UPDATE web_job_health SET started=? WHERE id=1',(time.time(),))

def finished(connect,failures):
    now=time.time()
    with connect() as db:
        db.execute('UPDATE web_job_health SET finished=?,failures=?,last_success=CASE WHEN ?=0 THEN ? ELSE last_success END WHERE id=1',(now,failures,failures,now))

def status(connect,enabled):
    with connect() as db:row=dict(db.execute('SELECT started,finished,last_success,failures FROM web_job_health WHERE id=1').fetchone())
    age=time.time()-row['started'] if row['started'] else None
    state='disabled' if not enabled else 'not_started' if age is None else 'stale' if age>300 else 'attention' if row['failures'] else 'running'
    backup=dict(state='not_configured')
    receipt=os.environ.get('SPROCKET_BACKUP_RECEIPT')
    if receipt:
        try:
            saved=json.loads(Path(receipt).read_text());completed=datetime.fromisoformat(saved['completed'])
            if completed.tzinfo is None or saved.get('restore_verified') is not True:raise ValueError('Invalid receipt')
            hours=(datetime.now(timezone.utc)-completed).total_seconds()/3600
            backup=dict(state='current' if 0<=hours<=36 else 'stale',completed=saved['completed'],restore_verified=True)
        except (OSError,ValueError,KeyError,TypeError):backup=dict(state='unavailable')
    return dict(enabled=enabled,state=state,backup=backup,**row)
