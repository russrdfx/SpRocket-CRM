"""Observed deal stage history and daily pipeline snapshots; no invented historical dates."""
import json,uuid,math
from datetime import datetime,timezone

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS deal_observations(deal_id TEXT PRIMARY KEY,pipeline TEXT NOT NULL,stage TEXT NOT NULL,entered TEXT NOT NULL,baseline INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS deal_transitions(id TEXT PRIMARY KEY,deal_id TEXT NOT NULL,created TEXT NOT NULL,from_pipeline TEXT NOT NULL,from_stage TEXT NOT NULL,to_pipeline TEXT NOT NULL,to_stage TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sales_snapshots(day TEXT PRIMARY KEY,created TEXT NOT NULL,body TEXT NOT NULL);
    ''')
    now=datetime.now(timezone.utc).isoformat()
    for r in db.execute("SELECT id,body FROM records WHERE kind='deals'").fetchall():observe(db,r['id'],json.loads(r['body']),now,baseline=True)

def observe(db,ident,body,now,baseline=False):
    pipeline=body.get('pipeline') or '';stage=body.get('stage') or ''
    old=db.execute('SELECT * FROM deal_observations WHERE deal_id=?',(ident,)).fetchone()
    if old and (old['pipeline'],old['stage'])==(pipeline,stage):return
    db.execute('INSERT INTO deal_observations VALUES(?,?,?,?,?) ON CONFLICT(deal_id) DO UPDATE SET pipeline=excluded.pipeline,stage=excluded.stage,entered=excluded.entered,baseline=excluded.baseline',(ident,pipeline,stage,now,int(baseline and not old)))
    if old:db.execute('INSERT INTO deal_transitions VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),ident,now,old['pipeline'],old['stage'],pipeline,stage))

def outcome(stage):
    if stage.get('outcome') in ('open','won','lost'):return stage['outcome']
    name=' '.join(stage.get('name','').lower().replace('_',' ').replace('-',' ').split())
    return 'won' if name in ('won','closed won') else 'lost' if name in ('lost','closed lost') else 'open'

def insights(db,settings,now=None):
    now=now or datetime.now(timezone.utc);rows=[];counts=dict(open=0,won=0,lost=0);groups={};reasons={};weighted=0
    pipes={p['id']:p for p in settings['pipelines'] if p['kind']=='deals'}
    for row in db.execute("SELECT id,body FROM records WHERE kind='deals'").fetchall():
        r=json.loads(row['body']);observe(db,row['id'],r,now.isoformat(),baseline=True)
        p=pipes.get(r.get('pipeline'));s=next((s for s in p['stages'] if s['id']==r.get('stage')),None) if p else None
        result=outcome(s or {});counts[result]+=1
        amount=r.get('amount');amount=float(amount) if isinstance(amount,(float,int)) and not isinstance(amount,bool) and math.isfinite(amount) else 0
        if result=='open' and s:weighted+=amount*float(s.get('probability',0))
        key=(r.get('pipeline',''),r.get('stage',''));group=groups.setdefault(key,dict(pipeline=p['name'] if p else 'No pipeline',stage=s['name'] if s else 'No stage',outcome=result,count=0,ages=[],baseline_count=0));group['count']+=1
        observed=db.execute('SELECT * FROM deal_observations WHERE deal_id=?',(row['id'],)).fetchone()
        if observed:
            group['ages'].append(max(0,(now-datetime.fromisoformat(observed['entered'])).total_seconds()/86400));group['baseline_count']+=int(observed['baseline'])
        if result=='lost':
            reason=str(r.get('loss_reason') or 'Not recorded').strip() or 'Not recorded';reasons[reason]=reasons.get(reason,0)+1
    for group in groups.values():
        ages=group.pop('ages');group['average_days_observed']=round(sum(ages)/len(ages),1) if ages else None
    closed=counts['won']+counts['lost'];summary=dict(**counts,win_rate=round(100*counts['won']/closed,1) if closed else None,weighted_open=weighted,currency=settings.get('currency','USD'))
    day=now.date().isoformat()
    db.execute('INSERT INTO sales_snapshots VALUES(?,?,?) ON CONFLICT(day) DO NOTHING',(day,now.isoformat(),json.dumps(summary)))
    snapshots=[dict(day=r['day'],created=r['created'],**json.loads(r['body'])) for r in db.execute('SELECT * FROM sales_snapshots ORDER BY day DESC LIMIT 90')]
    return dict(summary=summary,stages=list(groups.values()),loss_reasons=[dict(reason=k,count=v) for k,v in sorted(reasons.items(),key=lambda x:-x[1])],snapshots=snapshots)
