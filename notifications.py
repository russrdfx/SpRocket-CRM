"""Personal CRM notifications. Provider content stays scoped to its account owner."""
import hashlib,json
from datetime import datetime,timedelta,timezone

TYPES=('email_open','incoming_email','task_reminder')
DEFAULTS={**{k:True for k in TYPES},'desktop':False}

def initialize(db):
 db.executescript('''
 CREATE TABLE IF NOT EXISTS notification_preferences(owner TEXT PRIMARY KEY,body TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS notifications(owner TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL,record_id TEXT NOT NULL DEFAULT '',message_id TEXT NOT NULL DEFAULT '',version TEXT NOT NULL DEFAULT '',read_at TEXT NOT NULL DEFAULT '',PRIMARY KEY(owner,id));
 ''')
 db.execute('CREATE INDEX IF NOT EXISTS notifications_owner_date ON notifications(owner,created)')

def preferences(db,owner):
 row=db.execute('SELECT body,created FROM notification_preferences WHERE owner=?',(owner,)).fetchone()
 if row:return {**DEFAULTS,**json.loads(row['body'])},row['created']
 now=datetime.now(timezone.utc).isoformat()
 db.execute('INSERT INTO notification_preferences VALUES(?,?,?) ON CONFLICT(owner) DO NOTHING',(owner,json.dumps(DEFAULTS),now))
 row=db.execute('SELECT body,created FROM notification_preferences WHERE owner=?',(owner,)).fetchone()
 return {**DEFAULTS,**json.loads(row['body'])},row['created']

def emit(db,owner,ident,kind,title,detail,created,record='',message='',version=''):
 db.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,id) DO NOTHING',(owner,ident,kind,title[:300],detail[:600],created,record,message,version,''))

def incoming(db,owner,message):
 _,since=preferences(db,owner)
 # Historical imports are useful CRM data, but not new-mail alerts.
 date=message.get('date','')
 try:
  if datetime.fromisoformat(date.replace('Z','+00:00'))<datetime.fromisoformat(since):return
 except (ValueError,TypeError):return
 if message.get('direction')!='received':return
 emit(db,owner,'mail:'+message['id'],'incoming_email','New email',(message.get('subject') or '(No subject)')+' · From: '+str(message.get('sender') or ''),date,message=message['id'])

def fingerprint(task):
 return hashlib.sha256(json.dumps([task.get('due_date'),task.get('due_time'),task.get('reminder_preference')],separators=(',',':')).encode()).hexdigest()

def task_candidates(db,aliases,offset,now):
 aliases={str(a).strip().lower() for a in aliases if a}
 offsets={'At due time':0,'15 minutes before':15,'1 hour before':60,'1 day before':1440}
 for row in db.execute("SELECT id,body FROM records WHERE kind='tasks'"):
  task=json.loads(row['body']);assigned=str(task.get('owner') or '').strip().lower()
  if task.get('completed') or (assigned and assigned not in aliases) or task.get('reminder_preference') not in offsets:continue
  try:
   due=datetime.fromisoformat(task['due_date']+'T'+(task.get('due_time') or '09:00')).replace(tzinfo=timezone.utc)+timedelta(minutes=offset-offsets[task['reminder_preference']])
  except (ValueError,KeyError,TypeError):continue
  if due<=now:yield row['id'],task,due

def feed(db,owner,aliases,offset=0,now=None):
 if type(offset) is not int or abs(offset)>840:raise ValueError('Invalid time zone offset.')
 now=now or datetime.now(timezone.utc);prefs,_=preferences(db,owner)
 db.execute('DELETE FROM notifications WHERE owner=? AND created<?',(owner,(now-timedelta(days=90)).isoformat()))
 # Read the accepted sender's events only; shared activity visibility is insufficient.
 for row in db.execute("SELECT e.id,e.created,t.message_id,m.body FROM mail_tracking_events e JOIN mail_tracking t ON t.id=e.tracking_id JOIN mail_messages m ON m.id=t.message_id JOIN mail_accounts a ON a.id=m.account_id WHERE t.owner=? AND a.owner=? AND t.state='accepted' AND e.created>=? ORDER BY e.created DESC LIMIT 500",(owner,owner,(now-timedelta(days=90)).isoformat())):
  m=json.loads(row['body'])
  emit(db,owner,'open:'+row['id'],'email_open','Email opened',(m.get('subject') or '(No subject)')+' · To: '+str(m.get('to') or ''),row['created'],message=row['message_id'])
 active_tasks={}
 states={r['task_id']:dict(r) for r in db.execute('SELECT * FROM reminder_state WHERE owner=?',(owner,))}
 for ident,task,due in task_candidates(db,aliases,offset,now):
  if due<now-timedelta(days=90):continue
  version=fingerprint(task);saved=states.get(ident);legacy=json.dumps([task.get('due_date'),task.get('due_time'),task.get('reminder_preference')],separators=(',',':'))
  if saved and saved['fingerprint']==legacy and (saved['dismissed'] or (saved['snooze_until'] and saved['snooze_until']>now.isoformat())):continue
  active_tasks[ident]=version
  emit(db,owner,'task:'+ident+':'+version,'task_reminder','Task reminder',task.get('name') or 'Follow up',due.isoformat(),record=ident,version=version)
 rows=[dict(r) for r in db.execute('SELECT id,kind,title,detail,created,record_id,message_id,version,read_at FROM notifications WHERE owner=? AND created>=? ORDER BY created DESC LIMIT 1000',(owner,(now-timedelta(days=90)).isoformat()))]
 rows=[r for r in rows if prefs.get(r['kind'],False) and (r['kind']!='task_reminder' or active_tasks.get(r['record_id'])==r['version'])]
 for r in rows:r.pop('version',None);r['read']=bool(r.pop('read_at'))
 return dict(items=rows[:100],unread=sum(not r['read'] for r in rows),preferences=prefs)

def save(db,owner,data):
 if not isinstance(data,dict):raise ValueError('Invalid notification request.')
 preferences(db,owner)
 if data.get('action')=='preferences':
  values=data.get('preferences')
  if not isinstance(values,dict) or set(values)!=set(DEFAULTS) or any(type(v) is not bool for v in values.values()):raise ValueError('Invalid notification preferences.')
  db.execute('UPDATE notification_preferences SET body=? WHERE owner=?',(json.dumps(values),owner))
 elif data.get('action')=='read':
  ids=data.get('ids')
  if not isinstance(ids,list) or len(ids)>1000 or any(not isinstance(i,str) or len(i)>200 for i in ids):raise ValueError('Choose notifications to mark read.')
  now=datetime.now(timezone.utc).isoformat()
  for ident in set(ids):db.execute("UPDATE notifications SET read_at=? WHERE owner=? AND id=? AND read_at=''",(now,owner,ident))
 else:raise ValueError('Unknown notification action.')
 return dict(ok=True)
