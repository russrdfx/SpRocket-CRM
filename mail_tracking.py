"""Opt-in, tenant-hosted image tracking. Image requests are not read receipts."""
import base64,hashlib,ipaddress,json,os,re,secrets,time,uuid
from datetime import datetime,timezone
from urllib.parse import urlparse

PIXEL=base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
TTL=90*86400
# Collapse rapid retries rather than presenting a reload burst as many opens.
DEBOUNCE=30

def origin():
 value=(os.getenv('SPROCKET_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL','')).rstrip('/')
 u=urlparse(value);host=u.hostname or ''
 if os.getenv('SPROCKET_WEB')!='1' or u.scheme!='https' or not host or u.username or u.password or u.path or u.query or u.fragment or host=='localhost' or host.endswith('.localhost'):return ''
 try:
  if not ipaddress.ip_address(host).is_global:return ''
 except ValueError:pass
 return value

class Tracking:
 def __init__(self,connect):self.connect=connect
 def initialize(self,db):
  db.executescript('''
  CREATE TABLE IF NOT EXISTS mail_tracking_config(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS mail_tracking_defaults(account_id TEXT PRIMARY KEY REFERENCES mail_accounts(id) ON DELETE CASCADE,enabled INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS mail_tracking(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,owner TEXT NOT NULL,account_id TEXT NOT NULL REFERENCES mail_accounts(id) ON DELETE CASCADE,send_id TEXT NOT NULL,message_id TEXT NOT NULL DEFAULT '',state TEXT NOT NULL,expires REAL NOT NULL,last_hit REAL NOT NULL DEFAULT 0,UNIQUE(owner,send_id));
  CREATE TABLE IF NOT EXISTS mail_tracking_events(id TEXT PRIMARY KEY,tracking_id TEXT NOT NULL REFERENCES mail_tracking(id) ON DELETE CASCADE,created TEXT NOT NULL);
  ''')
  db.execute('CREATE INDEX IF NOT EXISTS mail_tracking_message_idx ON mail_tracking(message_id)')
  db.execute('CREATE INDEX IF NOT EXISTS mail_tracking_event_idx ON mail_tracking_events(tracking_id,created)')
 def enabled(self,db):
  r=db.execute('SELECT enabled FROM mail_tracking_config WHERE id=1').fetchone();return bool(r and r[0])
 def status(self,owner,admin=False):
  with self.connect() as db:
   accounts=[dict(id=r['id'],email=r['email'],default_enabled=bool(r['enabled'])) for r in db.execute('SELECT a.id,a.email,COALESCE(t.enabled,0) AS enabled FROM mail_accounts a LEFT JOIN mail_tracking_defaults t ON t.account_id=a.id WHERE a.owner=?',(owner,))]
   return dict(available=bool(origin()),enabled=self.enabled(db),can_configure=admin,accounts=accounts,expiry_days=90)
 def configure(self,data):
  enabled=data.get('enabled')
  if type(enabled) is not bool:raise ValueError('Choose enable or disable tracking.')
  if enabled and not origin():raise ValueError('Email tracking requires a hosted CRM with a public HTTPS address.')
  with self.connect() as db:db.execute('INSERT INTO mail_tracking_config VALUES(1,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled',(int(enabled),))
  return dict(ok=True)
 def preference(self,owner,data):
  enabled=data.get('enabled')
  if type(enabled) is not bool:raise ValueError('Choose a tracking default.')
  with self.connect() as db:
   if not db.execute('SELECT 1 FROM mail_accounts WHERE id=? AND owner=?',(data.get('account_id'),owner)).fetchone():raise ValueError('Email account unavailable.')
   if enabled and (not origin() or not self.enabled(db)):raise ValueError('Ask your administrator to enable email tracking first.')
   db.execute('INSERT INTO mail_tracking_defaults VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled',(data['account_id'],int(enabled)))
  return dict(ok=True)
 def prepare(self,db,owner,account,send_id,recipient,requested):
  if type(requested) is not bool:raise ValueError('Choose whether to track this email.')
  if not requested:return None
  host=origin()
  if not host or not self.enabled(db):raise ValueError('Email tracking is unavailable or disabled.')
  for row in db.execute("SELECT body FROM records WHERE kind='contacts'"):
   record=json.loads(row[0])
   if str(record.get('email','')).strip().lower()==recipient.lower() and record.get('email_tracking_disabled') is True:raise ValueError('Email tracking is excluded for this contact. Turn off Track opens to send.')
  token=secrets.token_urlsafe(32);ident=str(uuid.uuid4())
  db.execute('INSERT INTO mail_tracking(id,token_hash,owner,account_id,send_id,state,expires) VALUES(?,?,?,?,?,?,?)',(ident,hashlib.sha256(token.encode()).hexdigest(),owner,account,send_id,'attempted',time.time()+TTL))
  return dict(id=ident,url=host+'/email-open/'+token+'.gif')
 def accept(self,db,tracking,message):
  if tracking:db.execute("UPDATE mail_tracking SET state='accepted',message_id=? WHERE id=?",(message,tracking['id']))
 def hit(self,token):
  if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):return
  now=time.time()
  with self.connect() as db:
   if not origin() or not self.enabled(db):return
   # One atomic reservation makes concurrent image retries a single event.
   row=db.execute("UPDATE mail_tracking SET last_hit=? WHERE token_hash=? AND expires>? AND last_hit<? AND state IN ('attempted','accepted') RETURNING id",(now,hashlib.sha256(token.encode()).hexdigest(),now,now-DEBOUNCE)).fetchone()
   if row:db.execute('INSERT INTO mail_tracking_events VALUES(?,?,?)',(str(uuid.uuid4()),row['id'],datetime.fromtimestamp(now,timezone.utc).isoformat()))
 def summaries(self,db,message_ids):
  ids=set(message_ids);out={}
  # No tokens or recipient identifiers are exposed in tracking summaries.
  for row in db.execute("SELECT id,message_id,expires FROM mail_tracking WHERE state='accepted'"):
   if row['message_id'] not in ids:continue
   times=[r[0] for r in db.execute('SELECT created FROM mail_tracking_events WHERE tracking_id=? ORDER BY created DESC',(row['id'],))]
   out[row['message_id']]=dict(tracked=True,count=len(times),opens=times,expired=row['expires']<time.time(),collecting=self.enabled(db) and row['expires']>time.time())
  return out
 def decorate(self,db,activities):
  summaries=self.summaries(db,[a.get('mail_message_id') for a in activities])
  for a in activities:
   if a.get('email') and a.get('mail_message_id') in summaries:a['email']['tracking']=summaries[a['mail_message_id']]

 def visible_opens(self,owner):
  with self.connect() as db:
   ids={r[0] for r in db.execute('SELECT m.id FROM mail_messages m JOIN mail_accounts a ON a.id=m.account_id WHERE a.owner=?',(owner,))}
   # Activity copies already have workspace visibility; other personal caches do not.
   ids.update(json.loads(r[0]).get('mail_message_id') for r in db.execute('SELECT body FROM activities'))
   return dict(messages=self.summaries(db,ids))

 def archive(self,db,account):
  ids=[r[0] for r in db.execute('SELECT message_id FROM mail_tracking WHERE account_id=?',(account,))]
  saved=self.summaries(db,ids)
  for row in db.execute('SELECT id,body FROM activities').fetchall():
   body=json.loads(row['body']);summary=saved.get(body.get('mail_message_id'))
   if summary and body.get('email'):
    body['email']['tracking']=dict(summary,collecting=False,disconnected=True)
    db.execute('UPDATE activities SET body=? WHERE id=?',(json.dumps(body),row['id']))
