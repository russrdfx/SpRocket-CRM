"""Opt-in deal follow-up rules; no outbound communications or closed-app scheduling."""
import hashlib,json,uuid
from datetime import datetime,timezone,timedelta

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS automation_rules(id TEXT PRIMARY KEY,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS automation_runs(id TEXT PRIMARY KEY,rule_id TEXT NOT NULL,event_key TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(rule_id,event_key));''')

def status(db):
    return dict(rules=[dict(json.loads(r['body']),id=r['id']) for r in db.execute('SELECT * FROM automation_rules')],runs=[dict(json.loads(r['body']),created=r['created']) for r in db.execute('SELECT * FROM automation_runs ORDER BY created DESC LIMIT 50')])

def save(db,data):
    ident=data.get('id') or str(uuid.uuid4())
    if data.get('delete'):
        db.execute('DELETE FROM automation_rules WHERE id=?',(ident,));return {'ok':True}
    settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);pipeline=next((p for p in settings['pipelines'] if p['id']==data.get('pipeline') and p['kind']=='deals'),None)
    if not pipeline:raise ValueError('Choose a Deals pipeline.')
    trigger=data.get('trigger');stage=data.get('stage','')
    if trigger not in ('stage','inactive'):raise ValueError('Choose a stage-change or inactivity trigger.')
    if trigger=='stage' and stage not in {s['id'] for s in pipeline['stages']}:raise ValueError('Choose a pipeline stage.')
    name=str(data.get('name','')).strip();title=str(data.get('title','')).strip();owner=str(data.get('owner','')).strip()
    if not name or len(name)>100 or not title or len(title)>200 or len(owner)>200:raise ValueError('Enter a rule name and task title.')
    days=data.get('days',7);due=data.get('due',3)
    if type(days)!=int or not 1<=days<=365 or type(due)!=int or not 0<=due<=365:raise ValueError('Use 1–365 inactive days and 0–365 days until due.')
    body=dict(name=name,title=title,owner=owner,pipeline=pipeline['id'],trigger=trigger,stage=stage,days=days,due=due,enabled=data.get('enabled') is True)
    if not any(t['id']=='tasks' for t in settings['types']):raise ValueError('Tasks record type is required.')
    db.execute('INSERT INTO automation_rules VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(ident,json.dumps(body)));return dict(ok=True,id=ident)

def create_task(db,rule,record,key,validate):
    if db.execute('SELECT 1 FROM automation_runs WHERE rule_id=? AND event_key=?',(rule['id'],key)).fetchone():return False
    now=datetime.now(timezone.utc);task_id=str(uuid.uuid4());body=dict(name=rule['title'].replace('{deal}',record['name']),owner=rule['owner'] or record.get('owner',''),links=[record['id']],notes='Created by rule: '+rule['name'],task_type='To-do',due_date=(now+timedelta(days=rule['due'])).date().isoformat(),completed=False,record_source='Automation')
    validate(db,'tasks',body)
    db.execute('INSERT INTO records VALUES(?,?,?,?)',(task_id,'tasks',json.dumps(body),now.isoformat()))
    db.execute('INSERT INTO automation_runs VALUES(?,?,?,?,?)',(str(uuid.uuid4()),rule['id'],key,json.dumps(dict(rule=rule['name'],record=record['name'],task_id=task_id,result='Task created')),now.isoformat()));return True

def stage_changed(db,ident,old,body,updated,validate):
    if not old or (old.get('pipeline'),old.get('stage'))==(body.get('pipeline'),body.get('stage')):return
    record=dict(body,id=ident)
    for row in db.execute('SELECT * FROM automation_rules').fetchall():
        rule=dict(json.loads(row['body']),id=row['id'])
        if rule['enabled'] and rule['trigger']=='stage' and rule['pipeline']==body.get('pipeline') and rule['stage']==body.get('stage'):create_task(db,rule,record,ident+':'+updated,validate)

def inactive(db,validate,preview=False):
    settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);now=datetime.now(timezone.utc);matches=[]
    for row in db.execute('SELECT * FROM automation_rules').fetchall():
        rule=dict(json.loads(row['body']),id=row['id'])
        if not rule['enabled'] or rule['trigger']!='inactive':continue
        pipeline=next((p for p in settings['pipelines'] if p['id']==rule['pipeline']),None)
        if not pipeline:continue
        for candidate in db.execute("SELECT * FROM records WHERE kind='deals'").fetchall():
            record=dict(json.loads(candidate['body']),id=candidate['id']);stage=next((s for s in pipeline['stages'] if s['id']==record.get('stage')),None)
            if record.get('pipeline')!=pipeline['id'] or not stage or stage['probability']==1 or 'lost' in stage['name'].lower() or 'won' in stage['name'].lower():continue
            latest=db.execute('SELECT MAX(created) FROM activities WHERE record_id=?',(record['id'],)).fetchone()[0];last=max(latest or '',candidate['updated']);when=datetime.fromisoformat(last.replace('Z','+00:00'))
            if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
            if (now-when).total_seconds()<rule['days']*86400:continue
            key=record['id']+':'+last
            if db.execute('SELECT 1 FROM automation_runs WHERE rule_id=? AND event_key=?',(rule['id'],key)).fetchone():continue
            matches.append(dict(rule=rule['name'],record=record['name']))
            if not preview:create_task(db,rule,record,key,validate)
    return dict(ok=True,count=len(matches),matches=matches)
