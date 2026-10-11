"""Transactional record cleanup, task completion and personal reminder state."""
import calendar
import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

PERSONAL_DOMAINS = set('gmail.com googlemail.com outlook.com hotmail.com live.com msn.com yahoo.com yahoo.ca ymail.com icloud.com me.com mac.com aol.com proton.me protonmail.com pm.me fastmail.com hey.com mail.com gmx.com'.split())

def domain(value):
    return (urlparse(value if '://' in value else '//'+value).hostname or '').lower().removeprefix('www.')

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS reminder_state(owner TEXT NOT NULL,task_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,fingerprint TEXT NOT NULL,snooze_until TEXT NOT NULL DEFAULT \'\',dismissed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(owner,task_id))')

def review(db):
    records=[dict(json.loads(r['body']),id=r['id'],kind=r['kind']) for r in db.execute("SELECT * FROM records WHERE kind IN ('contacts','companies')")]
    groups={}
    for r in records:
        key=str(r.get('email','')).strip().lower() if r['kind']=='contacts' else domain(str(r.get('domain','')).strip())
        if key:groups.setdefault((r['kind'],key),[]).append(r)
    return dict(duplicates=[dict(kind=k[0],key=k[1],records=v) for k,v in groups.items() if len(v)>1],imported=[r for r in records if r.get('record_source')=='Email sync'],personal_companies=[r for r in records if r['kind']=='companies' and r.get('record_source')=='Email sync' and domain(r.get('domain','')) in PERSONAL_DOMAINS])

def merge(db,data):
    source,target=data.get('source_id'),data.get('target_id')
    if not source or source==target:raise ValueError('Choose two different records.')
    rows=[db.execute('SELECT * FROM records WHERE id=?',(ident,)).fetchone() for ident in (source,target)]
    if not all(rows) or rows[0]['kind']!=rows[1]['kind'] or rows[0]['kind'] not in ('contacts','companies'):raise ValueError('Only contacts or companies of the same type can be merged.')
    src,dst=[json.loads(r['body']) for r in rows]
    for key,value in src.items():
        if key!='links' and dst.get(key) in (None,'',[]):dst[key]=value
    dst['links']=list(dict.fromkeys(x for x in dst.get('links',[])+src.get('links',[]) if x not in (source,target)))
    now=datetime.now(timezone.utc).isoformat()
    db.execute('UPDATE records SET body=?,updated=? WHERE id=?',(json.dumps(dst),now,target))
    for r in db.execute('SELECT * FROM records WHERE id NOT IN (?,?)',(source,target)).fetchall():
        body=json.loads(r['body'])
        if source in body.get('links',[]):
            body['links']=list(dict.fromkeys(target if x==source else x for x in body['links']))
            db.execute('UPDATE records SET body=?,updated=? WHERE id=?',(json.dumps(body),now,r['id']))
    # Retain calendar logging identities when duplicate contacts are merged.
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_logs'").fetchone():
        for log in db.execute('SELECT * FROM calendar_logs WHERE record_id=?',(source,)).fetchall():
            existing=db.execute('SELECT activity_id FROM calendar_logs WHERE account_id=? AND event_id=? AND record_id=?',(log['account_id'],log['event_id'],target)).fetchone()
            if existing:
                db.execute('DELETE FROM activities WHERE id=?',(log['activity_id'],))
                db.execute('DELETE FROM calendar_logs WHERE account_id=? AND event_id=? AND record_id=?',(log['account_id'],log['event_id'],source))
            else:db.execute('UPDATE calendar_logs SET record_id=? WHERE account_id=? AND event_id=? AND record_id=?',(target,log['account_id'],log['event_id'],source))
    # Keep one activity per message after combining two email-matched contacts.
    target_messages={json.loads(r['body']).get('mail_message_id') for r in db.execute('SELECT body FROM activities WHERE record_id=?',(target,))}
    for row in db.execute('SELECT * FROM activities WHERE record_id=?',(source,)).fetchall():
        message=json.loads(row['body']).get('mail_message_id')
        if message and message in target_messages:db.execute('DELETE FROM activities WHERE id=?',(row['id'],))
        else:
            db.execute('UPDATE activities SET record_id=? WHERE id=?',(target,row['id']))
            if message:target_messages.add(message)
    db.execute('INSERT OR IGNORE INTO mail_logs(message_id,record_id) SELECT message_id,? FROM mail_logs WHERE record_id=?',(target,source))
    db.execute('DELETE FROM mail_logs WHERE record_id=?',(source,))
    db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),target,json.dumps(dict(type='Note',text='Merged record: '+src.get('name',source))),now))
    db.execute('DELETE FROM records WHERE id=?',(source,))
    return dict(ok=True,id=target)

def complete_task(db,data):
    row=db.execute("SELECT * FROM records WHERE id=? AND kind='tasks'",(data.get('id'),)).fetchone()
    if not row:raise ValueError('Task not found.')
    body=json.loads(row['body']);now=datetime.now(timezone.utc).isoformat()
    if body.get('completed'):return dict(ok=True)
    if data.get('expected_updated') and data['expected_updated']!=row['updated']:raise ValueError('This task changed. Refresh before completing it.')
    repeat=body.get('repeat_preference','Does not repeat');due=body.get('due_date','')
    next_date=None
    if repeat in ('Daily','Weekly','Monthly') and due:
        day=datetime.strptime(due,'%Y-%m-%d').date();today=datetime.now().date()
        while True:
            if repeat=='Monthly':
                year=day.year+(day.month==12);month=day.month%12+1
                day=day.replace(year=year,month=month,day=min(day.day,calendar.monthrange(year,month)[1]))
            else:day+=timedelta(days=1 if repeat=='Daily' else 7)
            if day>today:break
        next_date=day.isoformat();body['due_date']=next_date
    else:body['completed']=True;body['completed_at']=now
    db.execute('UPDATE records SET body=?,updated=? WHERE id=?',(json.dumps(body),now,row['id']))
    db.execute('DELETE FROM reminder_state WHERE task_id=?',(row['id'],))
    db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),row['id'],json.dumps(dict(type='Note',text='Task completed'+('; next occurrence '+next_date if next_date else '.'))),now))
    return dict(ok=True,next_date=next_date)

def reminders(db,owner):
    return dict(states=[dict(r) for r in db.execute('SELECT task_id,fingerprint,snooze_until,dismissed FROM reminder_state WHERE owner=?',(owner,))])

def reminder(db,owner,data):
    if not db.execute("SELECT id FROM records WHERE id=? AND kind='tasks'",(data.get('id'),)).fetchone():raise ValueError('Task not found.')
    fingerprint=data.get('fingerprint','');action=data.get('action')
    if not isinstance(fingerprint,str) or len(fingerprint)>300 or action not in ('dismiss','snooze'):raise ValueError('Invalid reminder action.')
    until=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat() if action=='snooze' else ''
    db.execute('INSERT INTO reminder_state VALUES(?,?,?,?,?) ON CONFLICT(owner,task_id) DO UPDATE SET fingerprint=excluded.fingerprint,snooze_until=excluded.snooze_until,dismissed=excluded.dismissed',(owner,data['id'],fingerprint,until,int(action=='dismiss')))
    return dict(ok=True)
