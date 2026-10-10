"""Add clearly fictional sample records to the configured local database."""
import importlib.util,json,uuid
from datetime import datetime,timezone,date,timedelta
from pathlib import Path
spec=importlib.util.spec_from_file_location('sprocket',Path(__file__).resolve().parent / 'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
now=datetime.now(timezone.utc).isoformat()
note='SAMPLE DATA — fictional demonstration record. Not a real customer or business.'
with s.connect() as db:
    settings=s.load_settings(db)
    owner='SAMPLE — Demo Owner'
    if owner not in settings['owners']:settings['owners'].append(owner)
    pid='sample_sales_pipeline'
    if not any(p['id']==pid for p in settings['pipelines']):
        settings['pipelines'].append({'id':pid,'name':'SAMPLE — Demo Sales Pipeline','kind':'deals','stages':[{'id':'sample_discovery','name':'SAMPLE — Discovery','probability':.2},{'id':'sample_proposal','name':'SAMPLE — Proposal','probability':.6},{'id':'sample_won','name':'SAMPLE — Won','probability':1}]})
    s.validate_settings(settings,s.load_settings(db),db.execute('SELECT * FROM records').fetchall())
    db.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(settings),))
    rows=[
      ('company1','companies','SAMPLE — Paper Kite Studio',{'domain':'paper-kite.example'}),
      ('company2','companies','SAMPLE — Lantern Grove Labs',{'domain':'lantern-grove.example'}),
      ('contact1','contacts','SAMPLE — Alex Demo',{'email':'alex@paper-kite.example','phone':'202-555-0101','links':['company1']}),
      ('contact2','contacts','SAMPLE — Jamie Example',{'email':'jamie@lantern-grove.example','phone':'202-555-0102','links':['company2']}),
      ('contact3','contacts','SAMPLE — Taylor Sample',{'email':'taylor@paper-kite.example','phone':'202-555-0103','links':['company1']}),
      ('deal1','deals','SAMPLE — Studio Starter Project',{'amount':2500,'close_date':str(date.today()+timedelta(days=14)),'pipeline':pid,'stage':'sample_discovery','links':['company1','contact1']}),
      ('deal2','deals','SAMPLE — Labs Service Package',{'amount':7200,'close_date':str(date.today()+timedelta(days=7)),'pipeline':pid,'stage':'sample_proposal','links':['company2','contact2']}),
      ('deal3','deals','SAMPLE — Studio Onboarding',{'amount':1200,'close_date':str(date.today()-timedelta(days=2)),'pipeline':pid,'stage':'sample_won','links':['company1','contact3']}),
      ('task3','tasks','SAMPLE — Arrange a studio discovery call',{'priority':'Medium','due_date':str(date.today()+timedelta(days=3)),'links':['deal1','contact1']}),
      ('task1','tasks','SAMPLE — Prepare a demo proposal',{'priority':'High','due_date':str(date.today()+timedelta(days=2)),'links':['deal2','contact2']}),
      ('task2','tasks','SAMPLE — Schedule a fictional kickoff',{'priority':'Medium','due_date':str(date.today()+timedelta(days=4)),'links':['deal3','contact3']}),
      ('ticket1','tickets','SAMPLE — Demo login question',{'priority':'Low','links':['contact1','company1']}),
      ('ticket2','tickets','SAMPLE — Example report request',{'priority':'Medium','links':['contact2','company2']})]
    ids={key:'sprocket_sample_'+key for key,_,_,_ in rows}
    for key,kind,name,extras in rows:
        ident=ids[key]
        if db.execute('SELECT 1 FROM records WHERE id=?',(ident,)).fetchone():continue
        body={'name':name,'notes':note,'owner':owner,'links':[]}|extras
        body['links']=[ids[x] for x in body['links']]
        s.validate_record(db,kind,body)
        db.execute('INSERT INTO records VALUES (?,?,?,?)',(ident,kind,json.dumps(body),now))
    for key,typ,text in [('contact1','Call','SAMPLE — Fictional discovery call: discussed goals for a demo project.'),('deal2','Meeting','SAMPLE — Fictional proposal review scheduled for demonstration.'),('deal3','Note','SAMPLE — Demo onboarding completed; no real work or payment took place.'),('ticket1','Email','SAMPLE — Fictional support email logged for the timeline preview.')]:
        ident='sprocket_sample_activity_'+key
        if not db.execute('SELECT 1 FROM activities WHERE id=?',(ident,)).fetchone():
            db.execute('INSERT INTO activities VALUES (?,?,?,?)',(ident,ids[key],json.dumps({'type':typ,'text':text}),now))
    counts=db.execute("SELECT kind,COUNT(*) FROM records WHERE id LIKE 'sprocket_sample_%' GROUP BY kind").fetchall()
    print(json.dumps({r[0]:r[1] for r in counts}))
