"""Contextual next actions and personal/shared reusable email templates."""
import copy,json,re,uuid
from datetime import datetime,timezone
from html import escape

VARIABLES=('contact.first_name','contact.last_name','contact.name','contact.email','contact.job_title','company.name','company.domain','user.name','workspace.name')

def initialize(db):
 db.executescript('''
 CREATE TABLE IF NOT EXISTS followup_requests(owner TEXT NOT NULL,request_id TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(owner,request_id));
 CREATE TABLE IF NOT EXISTS email_templates(id TEXT PRIMARY KEY,owner TEXT NOT NULL,scope TEXT NOT NULL,name TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,html TEXT NOT NULL,updated TEXT NOT NULL);
 ''')

def schedule(db,owner,actor,data,validate,mail):
 request=data.get('request_id')
 if not isinstance(request,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',request):raise ValueError('A unique follow-up request is required.')
 # Reserve first to serialize repeated requests in both database transports.
 ident=str(uuid.uuid4())
 reserved=db.execute('INSERT INTO followup_requests VALUES(?,?,?) ON CONFLICT(owner,request_id) DO NOTHING RETURNING task_id',(owner,request,ident)).fetchone()
 if not reserved:
  existing=db.execute('SELECT task_id FROM followup_requests WHERE owner=? AND request_id=?',(owner,request)).fetchone()[0]
  if not db.execute("SELECT 1 FROM records WHERE id=? AND kind='tasks'",(existing,)).fetchone():raise ValueError('This follow-up was removed. Start a new request.')
  return dict(ok=True,id=existing,existing=True)
 title=data.get('name','');notes=data.get('notes','');due=data.get('due_date','');clock=data.get('due_time','09:00')
 if not isinstance(title,str) or not title.strip() or len(title)>300 or not isinstance(notes,str) or len(notes)>5000:raise ValueError('Enter a task title and notes within the limits.')
 if not isinstance(due,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',due):raise ValueError('Choose a due date.')
 datetime.strptime(due,'%Y-%m-%d')
 if not isinstance(clock,str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('Choose a valid due time.')
 priority=data.get('priority','Medium');reminder=data.get('reminder_preference','At due time');task_type=data.get('task_type','To-do')
 if not isinstance(priority,str) or len(priority)>100 or reminder not in ('No reminder','At due time','15 minutes before','1 hour before','1 day before') or task_type not in ('To-do','Call','Email'):raise ValueError('Choose valid task options.')
 context=data.get('record_id');message_id=data.get('message_id');links=[]
 if context and message_id:raise ValueError('Choose one follow-up source.')
 if context:
  row=db.execute('SELECT * FROM records WHERE id=?',(context,)).fetchone()
  if not row or row['kind'] not in ('contacts','companies','deals'):raise ValueError('Choose a contact, company or deal.')
  record=json.loads(row['body']);links=[context]
  for linked in record.get('links',[]):
   other=db.execute('SELECT kind FROM records WHERE id=?',(linked,)).fetchone()
   if other and other[0] in ('contacts','companies','deals') and linked not in links:links.append(linked)
 elif message_id:
  message=mail.message(db,owner,message_id);links=[r['id'] for r in mail.matched(db,message)]
 assigned=data.get('owner',actor)
 settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0])
 allowed=set(settings.get('owners',[]))|{actor}|{json.loads(r[0]).get('owner','') for r in db.execute('SELECT body FROM records')}
 if not isinstance(assigned,str) or assigned not in allowed|{''}:raise ValueError('Choose an available owner.')
 body=dict(name=title.strip(),notes=notes.strip(),owner=assigned,due_date=due,due_time=clock,priority=priority,task_type=task_type,reminder_preference=reminder,repeat_preference='Does not repeat',completed=False,links=links)
 if message_id:body['mail_message_id']=message_id
 validate(db,'tasks',body);now=datetime.now(timezone.utc).isoformat()
 db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,'tasks',json.dumps(body),now))
 text='Follow-up scheduled: '+body['name']+'\nDue: '+due+' '+clock+'\nOwner: '+(assigned or 'Unassigned')
 for linked in links:db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),linked,json.dumps(dict(type='Task',text=text,task_id=ident)),now))
 return dict(ok=True,id=ident)

def reschedule(db,data,validate):
 row=db.execute("SELECT * FROM records WHERE id=? AND kind='tasks'",(data.get('id'),)).fetchone()
 if not row or row['updated']!=data.get('expected_updated'):raise ValueError('Task changed. Refresh before rescheduling.')
 body=json.loads(row['body'])
 if body.get('completed'):raise ValueError('Completed tasks cannot be rescheduled.')
 due=data.get('due_date');clock=data.get('due_time')
 if not isinstance(due,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',due):raise ValueError('Choose a due date.')
 datetime.strptime(due,'%Y-%m-%d')
 if not isinstance(clock,str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('Choose a due time.')
 body.update(due_date=due,due_time=clock);validate(db,'tasks',body);now=datetime.now(timezone.utc).isoformat()
 result=db.execute('UPDATE records SET body=?,updated=? WHERE id=? AND updated=?',(json.dumps(body),now,row['id'],row['updated']))
 if result.rowcount!=1:raise ValueError('Task changed during rescheduling. Refresh and try again.')
 db.execute('DELETE FROM reminder_state WHERE task_id=?',(row['id'],))
 db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),row['id'],json.dumps(dict(type='Task',text='Rescheduled to '+due+' '+clock)),now))
 return dict(ok=True)

def templates(db,owner,admin=False):
 return dict(variables=VARIABLES,can_share=admin,templates=[dict(r,can_edit=(r['owner']==owner and r['scope']=='personal') or (admin and r['scope']=='workspace')) for r in db.execute("SELECT * FROM email_templates WHERE owner=? OR scope='workspace' ORDER BY name",(owner,))])

def save_template(db,owner,data,admin,sanitize):
 ident=data.get('id') or str(uuid.uuid4());row=db.execute('SELECT * FROM email_templates WHERE id=?',(ident,)).fetchone()
 if row and row['scope']=='workspace' and not admin:raise ValueError('Only administrators can manage workspace templates.')
 if row and not(row['owner']==owner or (admin and row['scope']=='workspace')):raise ValueError('Template is unavailable for editing.')
 if row and row['updated']!=data.get('expected_updated'):raise ValueError('Template changed. Reopen before editing.')
 if data.get('delete') is True:
  if not row:raise ValueError('Template not found.')
  changed=db.execute('DELETE FROM email_templates WHERE id=? AND updated=?',(ident,row['updated']))
  if changed.rowcount!=1:raise ValueError('Template changed. Reopen before deleting.')
  return dict(ok=True)
 scope=data.get('scope','personal')
 if row and row['owner']!=owner and scope!='workspace':raise ValueError('A shared template owned by another user must stay shared.')
 if scope not in ('personal','workspace') or (scope=='workspace' and not admin):raise ValueError('Only administrators can manage workspace templates.')
 values={}
 for key,limit in (('name',100),('subject',500),('body',50000),('html',200000)):
  value=data.get(key,'')
  if not isinstance(value,str) or len(value)>limit or (key!='html' and not value.strip()):raise ValueError('Enter a template name, subject and message within the limits.')
  if key=='subject' and ('\n' in value or '\r' in value):raise ValueError('Subject must be on one line.')
  variables=re.findall(r'{{\s*([^{}]+?)\s*}}',value)
  if any(v.strip() not in VARIABLES for v in variables) or '{{' in re.sub(r'{{\s*([^{}]+?)\s*}}','',value):raise ValueError('Use only the listed template placeholders.')
  values[key]=sanitize(value) if key=='html' else value.strip()
 now=datetime.now(timezone.utc).isoformat()
 if row:
  changed=db.execute('UPDATE email_templates SET scope=?,name=?,subject=?,body=?,html=?,updated=? WHERE id=? AND updated=?',(scope,values['name'],values['subject'],values['body'],values['html'],now,ident,row['updated']))
  if changed.rowcount!=1:raise ValueError('Template changed. Reopen before editing.')
 else:db.execute('INSERT INTO email_templates VALUES(?,?,?,?,?,?,?,?)',(ident,owner,scope,values['name'],values['subject'],values['body'],values['html'],now))
 return dict(ok=True,id=ident)

def render_template(db,owner,actor,data,sanitize):
 row=db.execute("SELECT * FROM email_templates WHERE id=? AND (owner=? OR scope='workspace')",(data.get('id'),owner)).fetchone()
 if not row:raise ValueError('Template unavailable.')
 contact={};company={};recipient=data.get('email','')
 if not isinstance(recipient,str) or len(recipient)>320:raise ValueError('Choose a valid recipient.')
 matches=[json.loads(r['body']) for r in db.execute("SELECT * FROM records WHERE kind='contacts'") if str(json.loads(r['body']).get('email','')).strip().lower()==recipient.lower() and recipient]
 if len(matches)==1:contact=matches[0]
 if contact:
  candidates=[]
  for ident in contact.get('links',[]):
   r=db.execute("SELECT body FROM records WHERE id=? AND kind='companies'",(ident,)).fetchone()
   if r:candidates.append(json.loads(r[0]))
  if len(candidates)==1:company=candidates[0]
 values={**{'contact.'+k:contact.get(k,'') for k in ('first_name','last_name','name','email','job_title')},'company.name':company.get('name',''),'company.domain':company.get('domain',''),'user.name':actor,'workspace.name':json.loads(db.execute('SELECT body FROM settings').fetchone()[0]).get('name','')}
 missing=set()
 def replace(match,html=False):
  key=match.group(1).strip();value=str(values.get(key) or '')
  if not value:missing.add(key);return match.group(0)
  return escape(value,quote=True) if html else value
 subject=re.sub(r'{{\s*([^{}]+?)\s*}}',lambda m:replace(m),row['subject'])
 body=re.sub(r'{{\s*([^{}]+?)\s*}}',lambda m:replace(m),row['body'])
 html=sanitize(re.sub(r'{{\s*([^{}]+?)\s*}}',lambda m:replace(m,True),row['html']))
 return dict(subject=subject,body=body,html=html,missing=sorted(missing),contact_matched=len(matches)==1)
