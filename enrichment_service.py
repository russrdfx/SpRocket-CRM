"""Provider enrichment: explicit lookups, reviewed changes, provenance and guarded undo."""
import copy,csv,hashlib,io,json,math,re,time,uuid
from datetime import datetime,timezone
from urllib.parse import urlparse,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from crm_tools import domain
from workspace_tools import csv_read

FIELDS={
 'contacts':{'name':'Name','first_name':'First name','last_name':'Last name','job_title':'Job title','email':'Business email','email_status':'Email status','phone':'Business phone','linkedin_url':'LinkedIn profile','city':'City','region':'State / region','country':'Country','employer_name':'Employer','employer_domain':'Employer domain','seniority':'Seniority','department':'Department'},
 'companies':{'name':'Company name','domain':'Company domain','description':'Description','industry_text':'Industry detail','phone':'Company phone','linkedin_url':'LinkedIn company page','city':'City','region':'State / region','country':'Country','employees':'Estimated employee count','employee_range':'Employee range','estimated_annual_revenue':'Estimated annual revenue','revenue_range':'Revenue range'}
}
NUMBERS={'employees','estimated_annual_revenue'}
ESTIMATES=NUMBERS|{'employee_range','revenue_range'}
PROTECTED={'owner','pipeline','stage','links','id','kind','updated','record_source'}


def linkedin_url(value,kind):
    value=str(value or '').strip()
    if not value:return ''
    parsed=urlparse(value if '://' in value else 'https://'+value)
    host=parsed.hostname or ''
    prefix='/in/' if kind=='contacts' else '/company/'
    if (parsed.scheme not in ('http','https') or parsed.username or parsed.password or parsed.port
            or not(host=='linkedin.com' or host.endswith('.linkedin.com'))
            or not parsed.path.startswith(prefix) or not parsed.path[len(prefix):].strip('/')
            or len(value)>1000):
        raise ValueError('Use a valid LinkedIn '+('person profile' if kind=='contacts' else 'company page')+' URL.')
    return 'https://www.linkedin.com'+parsed.path.rstrip('/')


def defaults():
    return {'enabled':False,'daily_limit':20,'fill_only':False,'mapping':{
        kind:{field:('notes' if field=='description' else field) for field in fields}
        for kind,fields in FIELDS.items()}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def apollo_request(secret,path,params=None):
    if path not in ('auth/health','people/match','organizations/enrich'):raise ValueError('Unsupported Apollo request.')
    url='https://api.apollo.io/api/v1/'+path
    if params:url+='?'+urlencode(params)
    req=Request(url,method='POST' if path=='people/match' else 'GET',
                headers={'x-api-key':secret,'Accept':'application/json','Content-Type':'application/json','User-Agent':'SpRocket-CRM/enrichment'})
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(1000001)
            if len(raw)>1000000:raise ValueError('Apollo returned too much data. No changes were made.')
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Unexpected Apollo response.')
            return result
    except HTTPError as error:
        messages={401:'Apollo rejected the API key.',403:'Your Apollo account or key does not have access to this endpoint.',
                  429:'Apollo rate or credit limit reached. Review your account before trying again.'}
        raise ValueError(messages.get(error.code,'Apollo could not complete the lookup. No changes were made.')) from None
    except (URLError,TimeoutError,OSError,json.JSONDecodeError):
        raise ValueError('Apollo could not be reached or returned unreadable data. No changes were made.') from None


def canonical(kind,result):
    raw=result.get('person' if kind=='contacts' else 'organization')
    if not isinstance(raw,dict) or not raw:return {},None
    if kind=='contacts':
        org=raw.get('organization') or {};org=org if isinstance(org,dict) else {}
        fields={k:raw.get(k) for k in ('name','first_name','last_name','email','email_status','linkedin_url','city','country','seniority')}
        fields.update(job_title=raw.get('title'),region=raw.get('state'),employer_name=org.get('name'),employer_domain=org.get('primary_domain'))
        departments=raw.get('departments');fields['department']=', '.join(str(v) for v in departments) if isinstance(departments,list) else raw.get('department')
        confidence=result.get('match_confidence') or raw.get('match_confidence') or 'not provided'
        if confidence=='none':return {},None
        company=org.get('name','');host=org.get('primary_domain','')
    else:
        fields={k:raw.get(k) for k in ('name','industry','city','country','linkedin_url','estimated_annual_revenue','revenue_range')}
        fields.update(domain=raw.get('primary_domain') or raw.get('website_url'),description=raw.get('short_description'),industry_text=raw.get('industry'),region=raw.get('state'),employees=raw.get('estimated_num_employees'),employee_range=raw.get('employee_range'),estimated_annual_revenue=raw.get('annual_revenue') or raw.get('estimated_annual_revenue'))
        phone=raw.get('primary_phone');fields['phone']=phone.get('number') if isinstance(phone,dict) else raw.get('phone')
        confidence=result.get('match_confidence') or 'not provided';company=raw.get('name','');host=fields.get('domain','')
    values={k:v for k,v in fields.items() if k in FIELDS[kind] and v not in (None,'',[])}
    candidate={'name':str(raw.get('name') or '').strip()[:300],'company':str(company or '')[:300],
               'domain':str(host or '')[:300],'confidence':confidence if confidence in ('high','medium','low','not provided') else 'not provided'}
    try:candidate['linkedin_url']=linkedin_url(raw.get('linkedin_url'),kind)
    except ValueError:candidate['linkedin_url']=''
    return values,candidate


class EnrichmentService:
    def __init__(self,connect,cipher):self.connect,self.cipher=connect,cipher

    def initialize(self,db):
        db.executescript('''
        CREATE TABLE IF NOT EXISTS enrichment_config(id INTEGER PRIMARY KEY CHECK(id=1),secret TEXT NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS provider_enrichment_jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS enrichment_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,record_id TEXT NOT NULL,created TEXT NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS enrichment_usage(day TEXT PRIMARY KEY,attempts INTEGER NOT NULL);
        ''')

    def config(self,db):
        row=db.execute('SELECT * FROM enrichment_config WHERE id=1').fetchone()
        return (json.loads(row['body']),row['secret']) if row else (defaults(),'')

    def targets(self,db,kind):
        settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0])
        typ=next((t for t in settings['types'] if t['id']==kind),None)
        if not typ:raise ValueError('Contact or company record type is unavailable.')
        return {'name':{'key':'name','label':'Name','type':'text'},'notes':{'key':'notes','label':'Notes / description','type':'text'},
                **{f['key']:f for f in typ['fields'] if f['key'] not in PROTECTED and not f['key'].startswith('enrichment_')}}

    def status(self,admin=False):
        with self.connect() as db:
            config,secret=self.config(db);day=datetime.now(timezone.utc).date().isoformat()
            usage=db.execute('SELECT attempts FROM enrichment_usage WHERE day=?',(day,)).fetchone()
            targets={kind:list(self.targets(db,kind).values()) for kind in FIELDS}
        try:self.cipher();encryption_ready=True
        except Exception:encryption_ready=False
        return dict(provider='apollo',configured=bool(secret),encryption_ready=encryption_ready,can_configure=admin,
                    config=config,fields=FIELDS,targets=targets,attempts_today=usage[0] if usage else 0,quota_day=day)

    def configure(self,data):
        if not isinstance(data,dict):raise ValueError('Invalid provider configuration.')
        enabled=data.get('enabled');limit=data.get('daily_limit');fill=data.get('fill_only');mapping=data.get('mapping')
        if type(enabled) is not bool or type(fill) is not bool or type(limit) is not int or not 1<=limit<=500:
            raise ValueError('Choose a valid lookup limit (1–500) and provider rules.')
        if not isinstance(mapping,dict) or set(mapping)!=set(FIELDS):raise ValueError('Map contact and company fields.')
        key=data.get('api_key','')
        if not isinstance(key,str) or len(key)>2048 or (key and any(c.isspace() or ord(c)<33 or ord(c)>126 for c in key)):
            raise ValueError('Enter a valid Apollo API key without spaces.')
        with self.connect() as db:
            previous,encrypted=self.config(db)
            for kind,values in mapping.items():
                allowed=self.targets(db,kind)
                if not isinstance(values,dict) or set(values)-set(FIELDS[kind]):raise ValueError('Unknown provider field.')
                if any(not isinstance(v,str) for v in values.values()):raise ValueError('Invalid field mapping.')
                selected=[v for v in values.values() if v]
                if any(not isinstance(v,str) or v not in allowed for v in selected) or len(set(selected))!=len(selected):raise ValueError('Map each allowed CRM property at most once.')
            if data.get('remove') is True:encrypted='';enabled=False
            elif key:encrypted=self.cipher().encrypt(key.encode()).decode()
            if enabled and not encrypted:raise ValueError('Add an Apollo API key before enabling lookups.')
            config=dict(enabled=enabled,daily_limit=limit,fill_only=fill,mapping=mapping,revision=str(uuid.uuid4()),verified_at='' if key or data.get('remove') else previous.get('verified_at',''))
            db.execute('INSERT INTO enrichment_config VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET secret=excluded.secret,body=excluded.body',(encrypted,json.dumps(config)))
        return self.status(True)

    def key(self,encrypted):
        if not encrypted:raise ValueError('Ask your administrator to connect Apollo in Configuration → Data Enrichment.')
        try:return self.cipher().decrypt(encrypted.encode()).decode()
        except Exception:raise ValueError('Provider credentials could not be decrypted. Check the installation encryption key.') from None

    def verify(self):
        with self.connect() as db:config,encrypted=self.config(db)
        result=apollo_request(self.key(encrypted),'auth/health')
        if result.get('healthy') is not True or result.get('is_logged_in') is not True:raise ValueError('Apollo could not verify this API key.')
        with self.connect() as db:
            current,current_secret=self.config(db)
            if current_secret!=encrypted:raise ValueError('Credentials changed while checking. Verify the new key.')
            current['verified_at']=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE enrichment_config SET body=? WHERE id=1',(json.dumps(current),))
        return self.status(True)

    def record(self,db,ident):
        row=db.execute('SELECT * FROM records WHERE id=?',(ident,)).fetchone()
        if not row or row['kind'] not in FIELDS:raise ValueError('Choose an existing contact or company.')
        return row,json.loads(row['body'])

    def inputs(self,kind,record,hints):
        if not isinstance(hints,dict) or set(hints)-{'email','name','domain','linkedin_url'}:raise ValueError('Invalid matching details.')
        for value in hints.values():
            if not isinstance(value,str) or len(value)>1000:raise ValueError('Matching details are too long.')
        url=linkedin_url(hints.get('linkedin_url',record.get('linkedin_url','')),kind)
        host=domain(hints.get('domain',record.get('domain') if kind=='companies' else record.get('employer_domain','')) or '')
        name=hints.get('name',record.get('name','')).strip()[:300]
        if kind=='companies':
            if not host and not url:raise ValueError('Enter a company domain or LinkedIn company URL.')
            return {k:v for k,v in dict(domain=host,linkedin_url=url,name=name).items() if v}
        email=hints.get('email',record.get('email','')).strip()
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Use a valid email address for matching.')
        if not email and not url and not(name and host):raise ValueError('Enter an email, a LinkedIn profile URL, or a name with company domain.')
        return {k:v for k,v in dict(email=email,linkedin_url=url,name=name,domain=host).items() if v}

    def mapped(self,db,kind,before,values,config,validate):
        targets=self.targets(db,kind);suggestions={};details={};warnings=[]
        for source,raw in values.items():
            target=config['mapping'].get(kind,{}).get(source)
            if not target:continue
            if target not in targets:warnings.append('Property no longer available: '+target);continue
            field=targets[target]
            try:
                if field['type']=='number':
                    value=float(str(raw).replace(',',''))
                    if not math.isfinite(value):raise ValueError('Invalid number')
                    if value.is_integer():value=int(value)
                elif field['type'] in ('text','email','select'):
                    if not isinstance(raw,(str,int,float)):raise ValueError('Unsupported value')
                    value=str(raw).strip()[:5000 if source=='description' else 1000]
                    if source=='linkedin_url':value=linkedin_url(value,kind)
                    if source in ('domain','employer_domain'):value=domain(value)
                    if source=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid email')
                    if field['type']=='select':value=next((v for v in field['options'] if v.lower()==value.lower()),None)
                else:raise ValueError('Unsupported property type')
                if value in (None,''):continue
                trial=dict(before,**{target:value});validate(db,kind,trial);value=trial[target]
                if value!=before.get(target):
                    suggestions[target]=value;details[target]={'label':field['label'],'provider_field':source,'estimated':source in ESTIMATES}
            except (ValueError,TypeError):warnings.append('Could not map '+FIELDS[kind].get(source,source)+' to '+field['label']+'.')
        return suggestions,details,warnings

    def store(self,db,owner,items,errors=None,signature=''):
        ident=str(uuid.uuid4());job=dict(items=items,errors=errors or [],signature=signature,checked=datetime.now(timezone.utc).isoformat())
        db.execute('DELETE FROM provider_enrichment_jobs WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO provider_enrichment_jobs VALUES(?,?,?,?)',(ident,owner,time.time()+900,json.dumps(job)))
        return dict(preview_id=ident,**job)

    def lookup(self,owner,data,validate):
        if data.get('confirmed') is not True:raise ValueError('Confirm sharing matching details with Apollo and possible credit usage.')
        with self.connect() as db:
            row,record=self.record(db,data.get('id'));kind=row['kind'];config,encrypted=self.config(db)
            if not config['enabled']:raise ValueError('Apollo lookups are disabled. Use CSV enrichment or ask your administrator to enable Apollo.')
            params=self.inputs(kind,record,data.get('hints',{}))
            signature=hashlib.sha256(json.dumps([row['id'],row['updated'],params,config.get('revision')],sort_keys=True).encode()).hexdigest()
            for saved in db.execute('SELECT * FROM provider_enrichment_jobs WHERE owner=? AND expires>?',(owner,time.time())):
                job=json.loads(saved['body'])
                if job.get('signature')==signature:return dict(preview_id=saved['id'],reused=True,**job)
            key=self.key(encrypted);day=datetime.now(timezone.utc).date().isoformat()
            quota=db.execute('INSERT INTO enrichment_usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET attempts=enrichment_usage.attempts+1 WHERE enrichment_usage.attempts<? RETURNING attempts',(day,config['daily_limit'])).fetchone()
            if not quota:raise ValueError('The installation’s daily Apollo lookup limit has been reached. CSV enrichment is still available.')
        if kind=='contacts':params.update(reveal_personal_emails='false',reveal_phone_number='false',run_waterfall_email='false',run_waterfall_phone='false')
        result=apollo_request(key,'people/match' if kind=='contacts' else 'organizations/enrich',params)
        values,candidate=canonical(kind,result)
        with self.connect() as db:
            suggestions,details,warnings=self.mapped(db,kind,record,values,config,validate)
            item=dict(record_id=row['id'],kind=kind,name=record['name'],expected=row['updated'],before=record,suggestions=suggestions,details=details,
                      candidate=candidate,source='Apollo',source_url='https://app.apollo.io/',match_inputs={k:v for k,v in params.items() if k not in ('reveal_personal_emails','reveal_phone_number','run_waterfall_email','run_waterfall_phone')},warnings=warnings)
            return self.store(db,owner,[item],signature=signature)

    def csv_preview(self,owner,data,validate):
        kind=data.get('kind');mapping=data.get('mapping');text=data.get('csv');source=data.get('source','Other provider')
        if kind not in FIELDS or source not in ('Apollo','ZoomInfo','Other provider'):raise ValueError('Choose a record type and CSV source.')
        rows=csv_read(text)
        if not rows or len(rows)>100:raise ValueError('Use 1–100 CSV rows for reviewed enrichment.')
        headers=next(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
        if not isinstance(mapping,dict) or set(mapping)-set(headers):raise ValueError('Map valid CSV columns.')
        if any(not isinstance(v,str) for v in mapping.values()):raise ValueError('Invalid CSV field mapping.')
        fields=[v for v in mapping.values() if v]
        if any(not isinstance(v,str) or v not in set(FIELDS[kind])|{'_record_id'} for v in fields) or len(set(fields))!=len(fields):raise ValueError('Map each enrichment field once.')
        errors=[];items=[];seen=set()
        with self.connect() as db:
            config,_=self.config(db)
            records=[dict(row,record=json.loads(row['body'])) for row in db.execute('SELECT * FROM records WHERE kind=?',(kind,))]
            for number,cells in enumerate(rows,2):
                if len(cells)!=len(headers):errors.append({'row':number,'message':'Column count differs from header.'});continue
                values={mapping[h]:cell.strip() for h,cell in zip(headers,cells) if mapping.get(h) and cell.strip()}
                ident=values.get('_record_id');email=values.get('email','').lower();host=domain(values.get('domain',''))
                try:link=linkedin_url(values.get('linkedin_url'),kind)
                except ValueError:errors.append({'row':number,'message':'Invalid LinkedIn URL.'});continue
                def matches(r):
                    if ident:return r['id']==ident
                    if kind=='contacts' and email:return str(r['record'].get('email','')).lower()==email
                    if kind=='companies' and host:return domain(r['record'].get('domain',''))==host
                    try:return bool(link) and linkedin_url(r['record'].get('linkedin_url'),kind)==link
                    except ValueError:return False
                candidates=[r for r in records if matches(r)]
                if len(candidates)!=1:errors.append({'row':number,'message':'No unique existing record matched. Use record ID, email, domain or LinkedIn URL.'});continue
                row=candidates[0]
                if row['id'] in seen:errors.append({'row':number,'message':'This record appears more than once.'});continue
                seen.add(row['id']);record=row['record']
                suggestions,details,warnings=self.mapped(db,kind,record,values,config,validate)
                basis='Record ID' if ident else 'Email' if kind=='contacts' and email else 'Company domain' if host else 'LinkedIn URL'
                items.append(dict(record_id=row['id'],kind=kind,name=record['name'],expected=row['updated'],before=record,suggestions=suggestions,details=details,
                                  candidate={'name':values.get('name',record['name']),'company':values.get('employer_name',''),'domain':host,'linkedin_url':link,'confidence':'CSV match by '+basis},source='CSV / '+source+' (user-selected source)',source_url='',csv_row=number,warnings=warnings))
            if not items:return dict(preview_id='',items=[],errors=errors)
            return self.store(db,owner,items,errors)

    def apply(self,owner,actor,data,validate):
        selections=data.get('selections');overwrite=data.get('overwrite') is True
        if data.get('match_confirmed') is not True or not isinstance(selections,list) or not 1<=len(selections)<=100:raise ValueError('Review the matches and select fields before applying.')
        with self.connect() as db:
            config,_=self.config(db);jobs={};chosen=[];seen=set()
            for selection in selections:
                if not isinstance(selection,dict):raise ValueError('Invalid selection.')
                ident=selection.get('preview_id')
                if not isinstance(ident,str):raise ValueError('Invalid preview.')
                if ident not in jobs:
                    saved=db.execute('SELECT * FROM provider_enrichment_jobs WHERE id=? AND owner=?',(ident,owner)).fetchone()
                    if not saved or saved['expires']<time.time():raise ValueError('Preview expired. Review suggestions again.')
                    jobs[ident]=json.loads(saved['body'])
                item=next((r for r in jobs[ident]['items'] if r['record_id']==selection.get('record_id')),None)
                fields=selection.get('fields')
                if not item or not isinstance(fields,list) or not fields or any(not isinstance(k,str) or k not in item['suggestions'] for k in fields) or len(set(fields))!=len(fields):raise ValueError('Select valid suggested fields.')
                if item['record_id'] in seen:raise ValueError('Select each record at most once.')
                if set(fields)-set(self.targets(db,item['kind'])):raise ValueError('A property changed after preview. Review again.')
                seen.add(item['record_id']);chosen.append((item,fields,jobs[ident]['checked']))
            receipts=[];now=datetime.now(timezone.utc).isoformat()
            for item,fields,checked in sorted(chosen,key=lambda c:c[0]['record_id']):
                row,before=self.record(db,item['record_id'])
                if row['updated']!=item['expected']:raise ValueError('A record changed after preview. Review again; no changes were applied.')
                body=copy.deepcopy(before);provenance=copy.deepcopy(body.get('enrichment_fields',{}));receipt_id=str(uuid.uuid4());old={}
                for key in fields:
                    if before.get(key) not in (None,'',[]) and (not overwrite or config['fill_only']):raise ValueError('Replacing populated fields requires permission and explicit confirmation.')
                    old[key]={'present':key in before,'value':before.get(key),'provenance':provenance.get(key)}
                    body[key]=item['suggestions'][key]
                    provenance[key]={'source':item['source'],'checked':checked,'receipt_id':receipt_id,'estimated':item['details'][key]['estimated']}
                body['enrichment_fields']=provenance;body['enrichment_source']=item['source'];body['enrichment_checked']=checked;body['enrichment_last_receipt']=receipt_id
                validate(db,item['kind'],body)
                updated=db.execute('UPDATE records SET body=?,updated=? WHERE id=? AND updated=?',(json.dumps(body),now,row['id'],row['updated']))
                if updated.rowcount!=1:raise ValueError('A record changed during application. Review again.')
                receipt={'source':item['source'],'source_url':item['source_url'],'checked':checked,'actor':actor,'kind':item['kind'],'fields':fields,'details':item['details'],'before':old,'after':{k:body[k] for k in fields},'previous_last':{k:before.get(k) for k in ('enrichment_source','enrichment_checked','enrichment_last_receipt')},'undone':False}
                db.execute('INSERT INTO enrichment_receipts VALUES(?,?,?,?,?)',(receipt_id,owner,row['id'],now,json.dumps(receipt)))
                activity=dict(type='Enrichment',text='Reviewed enrichment: '+', '.join(item['details'][k]['label'] for k in fields)+'\nSource: '+item['source'],enrichment_receipt_id=receipt_id)
                db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),row['id'],json.dumps(activity),now));receipts.append(receipt_id)
            for ident in jobs:db.execute('DELETE FROM provider_enrichment_jobs WHERE id=? AND owner=?',(ident,owner))
            return dict(ok=True,records=len(receipts),receipts=receipts)

    def history(self,owner,ident,admin=False):
        with self.connect() as db:
            self.record(db,ident)
            rows=db.execute('SELECT * FROM enrichment_receipts WHERE record_id=? ORDER BY created DESC',(ident,)).fetchall()
            return {'history':[dict(id=r['id'],created=r['created'],source=json.loads(r['body'])['source'],actor=json.loads(r['body'])['actor'],fields=json.loads(r['body'])['fields'],details=json.loads(r['body'])['details'],before={k:v.get('value') for k,v in json.loads(r['body'])['before'].items()},after=json.loads(r['body'])['after'],undone=json.loads(r['body']).get('undone',False),can_undo=admin or r['owner']==owner) for r in rows]}

    def undo(self,owner,actor,data,validate,admin=False):
        if data.get('confirmed') is not True:raise ValueError('Confirm reverting this enrichment.')
        with self.connect() as db:
            row=db.execute('SELECT * FROM enrichment_receipts WHERE id=?',(data.get('id'),)).fetchone()
            if not row or (row['owner']!=owner and not admin):raise ValueError('Enrichment change unavailable for this user.')
            receipt=json.loads(row['body'])
            if receipt.get('undone'):raise ValueError('This enrichment was already reverted.')
            record,body=self.record(db,row['record_id']);provenance=copy.deepcopy(body.get('enrichment_fields',{}))
            if set(receipt['fields'])-set(self.targets(db,record['kind'])):raise ValueError('A property was removed. Review the record manually.')
            for key in receipt['fields']:
                if body.get(key)!=receipt['after'][key] or provenance.get(key,{}).get('receipt_id')!=row['id']:raise ValueError('An enriched field was changed afterward. Undo would overwrite newer data; review it manually.')
            for key,previous in receipt['before'].items():
                if previous['present']:body[key]=previous['value']
                else:body.pop(key,None)
                if previous['provenance']:provenance[key]=previous['provenance']
                else:provenance.pop(key,None)
            body['enrichment_fields']=provenance
            if body.get('enrichment_last_receipt')==row['id']:
                remaining=db.execute('SELECT * FROM enrichment_receipts WHERE record_id=? AND id<>? ORDER BY created DESC',(record['id'],row['id'])).fetchall()
                latest=next((r for r in remaining if not json.loads(r['body']).get('undone')),None)
                if latest:
                    saved=json.loads(latest['body'])
                    body.update(enrichment_source=saved['source'],enrichment_checked=saved['checked'],enrichment_last_receipt=latest['id'])
                else:
                    for key in ('enrichment_source','enrichment_checked','enrichment_last_receipt'):body.pop(key,None)
            validate(db,record['kind'],body);now=datetime.now(timezone.utc).isoformat()
            updated=db.execute('UPDATE records SET body=?,updated=? WHERE id=? AND updated=?',(json.dumps(body),now,record['id'],record['updated']))
            if updated.rowcount!=1:raise ValueError('Record changed during undo. Review it again.')
            receipt.update(undone=True,undone_at=now,undone_by=actor)
            db.execute('UPDATE enrichment_receipts SET body=? WHERE id=?',(json.dumps(receipt),row['id']))
            db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),record['id'],json.dumps(dict(type='Enrichment',text='Reverted reviewed enrichment from '+receipt['source'],enrichment_receipt_id=row['id'])),now))
            return dict(ok=True,id=record['id'])
