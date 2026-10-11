"""Reviewed CSV changes, personal saved views and deliberate database recovery."""
import base64,csv,hashlib,io,json,math,os,re,sqlite3,tempfile,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from crm_tools import domain

MAX_CSV=500000

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS saved_views(id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_previews(id TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_receipts(owner TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(owner,digest));
    ''')

def filters(value):
    if not isinstance(value,dict):raise ValueError('Invalid filters.')
    allowed={'query','owner','stage','company','pipeline','inactive_days','completed'}
    if set(value)-allowed:raise ValueError('Unknown view filter.')
    out={}
    for key,val in value.items():
        if key=='inactive_days':
            if not isinstance(val,int) or not 0<=val<=3650:raise ValueError('Inactivity must be 0–3650 days.')
        elif not isinstance(val,str) or len(val)>300:raise ValueError('Invalid view filter value.')
        out[key]=val
    return out

def views(db,owner):return {'views':[dict(id=r['id'],kind=r['kind'],name=r['name'],filters=json.loads(r['body'])) for r in db.execute('SELECT * FROM saved_views WHERE owner=? ORDER BY name',(owner,))]}

def save_view(db,owner,data):
    if data.get('delete'):
        db.execute('DELETE FROM saved_views WHERE id=? AND owner=?',(data.get('id'),owner));return {'ok':True}
    kind=data.get('kind');name=data.get('name','').strip()
    settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0])
    if kind not in {t['id'] for t in settings['types']} or not name or len(name)>100:raise ValueError('Choose a record type and a view name up to 100 characters.')
    ident=data.get('id') or str(uuid.uuid4());existing=db.execute('SELECT owner FROM saved_views WHERE id=?',(ident,)).fetchone()
    if existing and existing[0]!=owner:raise ValueError('View not found.')
    db.execute('INSERT INTO saved_views VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,body=excluded.body',(ident,owner,kind,name,json.dumps(filters(data.get('filters',{})))))
    return {'ok':True,'id':ident}

def csv_columns(db,kind):
    settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);typ=next((t for t in settings['types'] if t['id']==kind),None)
    if not typ:raise ValueError('Choose a valid record type.')
    return ['_record_id','name','owner','pipeline','stage','notes']+[f['key'] for f in typ['fields']]+['company_domain','contact_email']

def export_csv(db,data):
    kind=data.get('kind');columns=csv_columns(db,kind);selected=data.get('ids')
    if selected is not None and (not isinstance(selected,list) or len(selected)>10000):raise ValueError('Invalid record selection.')
    writer_file=io.StringIO(newline='');writer=csv.writer(writer_file);writer.writerow(columns)
    all_records={r['id']:dict(json.loads(r['body']),kind=r['kind']) for r in db.execute('SELECT * FROM records')}
    for ident,body in all_records.items():
        if body['kind']!=kind or (selected is not None and ident not in selected):continue
        linked=[all_records[x] for x in body.get('links',[]) if x in all_records]
        row=dict(body,_record_id=ident,company_domain=';'.join(r.get('domain','') for r in linked if r['kind']=='companies'),contact_email=';'.join(r.get('email','') for r in linked if r['kind']=='contacts'))
        values=[]
        for key in columns:
            value=row.get(key,'')
            if isinstance(value,bool):value='true' if value else 'false'
            # CSV opened by a spreadsheet must never execute user-entered formulas.
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):value="'"+value
            values.append(value)
        writer.writerow(values)
    return {'csv':writer_file.getvalue(),'filename':kind+'-'+datetime.now().date().isoformat()+'.csv','columns':columns}

def csv_read(text):
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_CSV:raise ValueError('Use a UTF-8 CSV up to 500 KB.')
    try:
        rows=list(csv.reader(io.StringIO(text.lstrip('\ufeff')),strict=True))
    except csv.Error:raise ValueError('Invalid CSV formatting.') from None
    if not rows or not rows[0] or len(set(rows[0]))!=len(rows[0]) or any(not x.strip() for x in rows[0]):raise ValueError('CSV needs unique, nonempty column headers.')
    rows=[r for r in rows[1:] if any(x.strip() for x in r)]
    if len(rows)>1000:raise ValueError('Import up to 1,000 rows at a time.')
    return rows

def preview_import(db,owner,data,validate):
    kind=data.get('kind');columns=csv_columns(db,kind);text=data.get('csv','');mapping=data.get('mapping')
    rows=csv_read(text);headers=next(csv.reader(io.StringIO(text.lstrip('\ufeff'))));settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);typ=next(t for t in settings['types'] if t['id']==kind)
    if not isinstance(mapping,dict) or not mapping or set(mapping)-set(headers):raise ValueError('Map CSV columns before importing.')
    targets=[v for v in mapping.values() if v]
    if len(set(targets))!=len(targets) or set(targets)-set(columns):raise ValueError('Map each CRM field only once.')
    mode=data.get('mode','fill');
    if mode not in ('fill','update','skip'):raise ValueError('Choose duplicate handling.')
    records=[dict(json.loads(r['body']),id=r['id'],kind=r['kind'],updated=r['updated']) for r in db.execute('SELECT * FROM records')];plans=[];errors=[];seen=set();warnings=[]
    for number,row in enumerate(rows,2):
        if len(row)!=len(headers):errors.append({'row':number,'error':'Column count differs from header.'});continue
        raw={mapping[h]:v.strip() for h,v in zip(headers,row) if mapping.get(h)};external_id=raw.pop('_record_id','');relations={key:raw.pop(key,'') for key in ('company_domain','contact_email')}
        try:
            for f in typ['fields']:
                key=f['key'];value=raw.get(key,'')
                if value=='':raw.pop(key,None);continue
                if f['type']=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError(f['label']+' must be a valid email address.')
                if f['type']=='number':
                    raw[key]=float(value)
                    if not math.isfinite(raw[key]):raise ValueError(f['label']+' must be finite.')
                if f['type']=='checkbox':
                    if value.lower() not in ('true','false','1','0','yes','no'):raise ValueError(f['label']+' must be true or false.')
                    raw[key]=value.lower() in ('true','1','yes')
            if kind=='contacts':
                if raw.get('email'):raw['email']=raw['email'].lower()
                if not raw.get('name'):raw['name']=' '.join(filter(None,[raw.get('first_name'),raw.get('last_name')])) or raw.get('email','')
            if kind=='companies':
                if raw.get('domain'):raw['domain']=domain(raw['domain'])
                if not raw.get('name'):raw['name']=raw.get('domain','')
            key=raw.get('email','').lower() if kind=='contacts' else domain(raw.get('domain','')) if kind=='companies' else ''
            matches=[r for r in records if r['kind']==kind and ((external_id and r['id']==external_id) or (not external_id and key and (r.get('email','').lower()==key if kind=='contacts' else domain(r.get('domain',''))==key)))]
            if external_id and not matches:raise ValueError('Record ID does not match a record of this type.')
            if len(matches)>1:raise ValueError('Several existing records match; resolve duplicates first.')
            duplicate_key=external_id or key
            if duplicate_key and duplicate_key in seen:raise ValueError('Duplicate identity appears earlier in this file.')
            if duplicate_key:seen.add(duplicate_key)
            existing=matches[0] if matches else None
            body={k:v for k,v in (existing or {}).items() if k not in ('id','kind','updated')}
            if not existing:body.update(record_source='CSV import',links=[])
            for k,v in raw.items():
                if v!='' and (not existing or mode=='update' or body.get(k) in (None,'',[])):body[k]=v
            links=list(body.get('links',[]))
            for relation,target_kind,target_field in [('company_domain','companies','domain'),('contact_email','contacts','email')]:
                for value in filter(None,[v.strip().lower() for v in relations[relation].split(';')]):
                    normalized=domain(value) if relation=='company_domain' else value
                    linked=[r for r in records if r['kind']==target_kind and (domain(r.get(target_field,'')) if relation=='company_domain' else r.get(target_field,'').lower())==normalized]
                    if len(linked)!=1:raise ValueError('Associated '+relation.replace('_',' ')+' must match one existing record: '+value)
                    links.append(linked[0]['id'])
            body['links']=list(dict.fromkeys(links));validate(db,kind,body)
            action='skip' if existing and mode=='skip' else 'update' if existing else 'create'
            changes={k:{'before':(existing or {}).get(k,''),'after':v} for k,v in body.items() if (existing or {}).get(k)!=v}
            plans.append({'row':number,'id':existing['id'] if existing else str(uuid.uuid4()),'action':action,'body':body,'changes':changes,'expected_updated':existing['updated'] if existing else None,'identity':key})
        except (ValueError,TypeError) as error:errors.append({'row':number,'error':str(error)})
    ident=str(uuid.uuid4());digest=hashlib.sha256(json.dumps(dict(csv=text,mapping=mapping,mode=mode,kind=kind),sort_keys=True).encode()).hexdigest();job=dict(kind=kind,plans=plans,errors=errors,digest=digest,mode=mode)
    db.execute('DELETE FROM import_previews WHERE expires<?',(time.time(),));db.execute('INSERT INTO import_previews VALUES(?,?,?,?)',(ident,owner,time.time()+900,json.dumps(job)))
    return {'id':ident,'rows':plans,'errors':errors,'counts':{action:sum(p['action']==action for p in plans) for action in ('create','update','skip')},'ready':bool(plans) and not errors,'expires_minutes':15}

def apply_import(db,owner,data,validate):
    row=db.execute('SELECT * FROM import_previews WHERE id=? AND owner=?',(data.get('id'),owner)).fetchone()
    if not row or row['expires']<time.time():raise ValueError('Preview expired. Preview the file again.')
    job=json.loads(row['body']);receipt=db.execute('SELECT result FROM import_receipts WHERE owner=? AND digest=?',(owner,job['digest'])).fetchone()
    if receipt:return dict(json.loads(receipt[0]),existing=True)
    if job['errors'] or not job['plans']:raise ValueError('Fix all preview errors before importing.')
    now=datetime.now(timezone.utc).isoformat();counts={'create':0,'update':0,'skip':0}
    for p in job['plans']:
        old=db.execute('SELECT updated FROM records WHERE id=?',(p['id'],)).fetchone()
        if (old[0] if old else None)!=p['expected_updated']:raise ValueError('Records changed after preview. Preview again.')
        if p['action']=='create' and p['identity']:
            for candidate in db.execute('SELECT body FROM records WHERE kind=?',(job['kind'],)):
                body=json.loads(candidate[0]);key=body.get('email','').lower() if job['kind']=='contacts' else domain(body.get('domain',''))
                if key==p['identity']:raise ValueError('A matching record was added after preview. Preview again.')
        validate(db,job['kind'],p['body']);counts[p['action']]+=1
        if p['action']!='skip':db.execute('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated',(p['id'],job['kind'],json.dumps(p['body']),now))
    result={'ok':True,'counts':counts};db.execute('INSERT INTO import_receipts VALUES(?,?,?)',(owner,job['digest'],json.dumps(result)));return result
