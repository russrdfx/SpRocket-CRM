"""Administrator setup guide; progress is personal and never changes CRM configuration."""
import json
from datetime import datetime,timezone
REVIEWED=('workspace','pipeline','fields','backup')
OPTIONAL=('email','calendar','team')
DEFAULT={'reviewed':[],'skipped':[],'hidden':False}
def initialize(db):
 db.execute('CREATE TABLE IF NOT EXISTS onboarding_progress(owner TEXT PRIMARY KEY,body TEXT NOT NULL)')
def load(db,owner):
 row=db.execute('SELECT body FROM onboarding_progress WHERE owner=?',(owner,)).fetchone()
 return json.loads(row[0]) if row else dict(reviewed=[],skipped=[],hidden=False)
def save(db,owner,data):
 if not isinstance(data,dict):raise ValueError('Invalid setup progress.')
 db.execute('INSERT INTO onboarding_progress VALUES(?,?) ON CONFLICT(owner) DO NOTHING',(owner,json.dumps(DEFAULT)))
 before=db.execute('SELECT body FROM onboarding_progress WHERE owner=?',(owner,)).fetchone()[0];body=json.loads(before);action=data.get('action');step=data.get('step');enabled=data.get('enabled')
 if type(enabled) is not bool:raise ValueError('Choose a valid setup progress value.')
 if action=='hidden':body['hidden']=enabled
 elif action in ('reviewed','skipped'):
  if step not in (REVIEWED if action=='reviewed' else OPTIONAL):raise ValueError('Choose a valid setup step.')
  body[action]=[s for s in body[action] if s!=step]+([step] if enabled else [])
 else:raise ValueError('Unknown setup action.')
 changed=db.execute('UPDATE onboarding_progress SET body=? WHERE owner=? AND body=?',(json.dumps(body),owner,before))
 if not changed.rowcount:raise ValueError('Setup progress changed in another window. Reload and try again.')
 return dict(ok=True)
def status(db,owner,settings,web=False):
 progress=load(db,owner);reviewed=set(progress['reviewed']);skipped=set(progress['skipped']);pipes=[p for p in settings.get('pipelines',[]) if p.get('kind')=='deals' and p.get('stages')]
 records=db.execute("SELECT COUNT(*) FROM records WHERE kind IN ('contacts','companies','deals')").fetchone()[0]
 mail=db.execute('SELECT COUNT(*) FROM mail_accounts WHERE owner=?',(owner,)).fetchone()[0]
 calendar=db.execute('SELECT COUNT(*) FROM calendar_accounts WHERE owner=?',(owner,)).fetchone()[0]
 team=False
 if web:
  team=db.execute('SELECT COUNT(*) FROM web_users WHERE active=1').fetchone()[0]>1 or bool(db.execute('SELECT 1 FROM web_invites WHERE expires>? LIMIT 1',(datetime.now(timezone.utc).timestamp(),)).fetchone())
 facts={'workspace':bool(settings.get('name') and settings.get('currency')),'pipeline':bool(pipes),'fields':bool(settings.get('types')),'records':bool(records),'backup':True,'email':bool(mail),'calendar':bool(calendar),'team':team}
 required={'workspace','pipeline','fields','records','backup'}
 steps=[]
 for ident in ['workspace','pipeline','fields','records','email','calendar','team','backup']:
  done=facts[ident] and (ident not in REVIEWED or ident in reviewed)
  steps.append(dict(id=ident,done=done,skipped=ident in skipped and not done,optional=ident not in required,available=ident!='team' or web,reviewed=ident in reviewed))
 return dict(progress=progress,steps=steps,required_done=sum(s['done'] for s in steps if not s['optional']),required_total=len(required),pipeline_count=len(pipes),record_count=records,web=web)
