"""Company website facts with pinned public HTTPS connections and reviewed application."""
import http.client,ipaddress,json,socket,ssl,time,uuid
from html.parser import HTMLParser
from urllib.parse import urlparse,urljoin
from datetime import datetime,timezone
from crm_tools import domain,PERSONAL_DOMAINS

class PublicHTTPS(http.client.HTTPSConnection):
    def connect(self):
        addresses=socket.getaddrinfo(self.host,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Website must resolve only to public internet addresses.')
        address=addresses[0][4][0]
        sock=socket.create_connection((address,443),timeout=8)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:sock.close();raise

def website(url):
    for _ in range(4):
        u=urlparse(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):raise ValueError('Use a public HTTPS company website.')
        connection=PublicHTTPS(u.hostname,timeout=8,context=ssl.create_default_context())
        try:
            connection.request('GET',(u.path or '/')+('?' +u.query if u.query else ''),headers={'User-Agent':'SpRocket-CRM/website-enrichment','Accept':'text/html'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200 or 'text/html' not in response.getheader('Content-Type','').lower():raise ValueError('Website did not return a readable HTML page.')
            raw=response.read(1000001)
            if len(raw)>1000000:raise ValueError('Website page exceeds 1 MB.')
            return url,raw.decode('utf-8',errors='replace')
        finally:connection.close()
    raise ValueError('Website redirected too many times.')

def facts(html):
    class Structured(HTMLParser):
        def __init__(self):super().__init__();self.in_script=False;self.parts=[];self.documents=[]
        def handle_starttag(self,tag,attrs):
            if tag=='script' and dict(attrs).get('type','').lower()=='application/ld+json':self.in_script=True;self.parts=[]
        def handle_data(self,text):
            if self.in_script:self.parts.append(text)
        def handle_endtag(self,tag):
            if tag=='script' and self.in_script:
                self.in_script=False
                try:self.documents.append(json.loads(''.join(self.parts)))
                except (ValueError,RecursionError):pass
    parser=Structured();parser.feed(html);organizations=[]
    def walk(value,depth=0):
        if depth>20:return
        if isinstance(value,list):
            for item in value:walk(item,depth+1)
        elif isinstance(value,dict):
            kinds=value.get('@type',[]);kinds=[kinds] if isinstance(kinds,str) else kinds
            if isinstance(kinds,list) and any(k in ('Organization','Corporation','LocalBusiness','ProfessionalService') for k in kinds):organizations.append(value)
            if '@graph' in value:walk(value['@graph'],depth+1)
    for doc in parser.documents:walk(doc)
    if not organizations:raise ValueError('No supported company facts were published on this page. Nothing was inferred.')
    # Multiple distinct organizations need a source choice rather than a guessed identity.
    names={o.get('name') for o in organizations if isinstance(o.get('name'),str)}
    if len(names)>1:raise ValueError('Website publishes several organizations. Use a company-specific page.')
    org=organizations[0];out={}
    for source,target in [('name','name'),('description','notes')]:
        value=org.get(source)
        if isinstance(value,str) and value.strip():out[target]=value.strip()[:5000]
    address=org.get('address',{})
    if isinstance(address,dict):
        for source,target in [('addressLocality','city'),('addressRegion','region'),('postalCode','postal_code')]:
            if isinstance(address.get(source),str):out[target]=address[source][:300]
    links=org.get('sameAs',[]);links=[links] if isinstance(links,str) else links
    if isinstance(links,list):
        for link in links:
            if isinstance(link,str) and urlparse(link).scheme=='https' and urlparse(link).hostname in ('linkedin.com','www.linkedin.com') and urlparse(link).path.startswith('/company/'):out['linkedin_url']=link[:1000];break
    if not out:raise ValueError('No supported company fields were published.')
    return out

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS enrichment_previews(id TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL,body TEXT NOT NULL)')

def preview(db,owner,data):
    row=db.execute('SELECT * FROM records WHERE id=?',(data.get('id'),)).fetchone()
    if not row or row['kind'] not in ('contacts','companies'):raise ValueError('Choose a contact or company.')
    record=json.loads(row['body']);contact=row if row['kind']=='contacts' else None;company=row if row['kind']=='companies' else None
    if contact:
        matches=[r for r in db.execute("SELECT * FROM records WHERE kind='companies'") if r['id'] in record.get('links',[])]
        if len(matches)>1:raise ValueError('Choose a company directly when this contact has multiple companies.')
        company=matches[0] if matches else None
    body=json.loads(company['body']) if company else {};host=domain(body.get('domain','') or record.get('email','').rsplit('@',1)[-1])
    if not host or host in PERSONAL_DOMAINS or '.' not in host:raise ValueError('A business website domain is required. Personal email domains are excluded.')
    url=data.get('url') or 'https://'+host+'/'
    if domain(url)!=host:raise ValueError('Source page must belong to this company domain.')
    try:source,html=website(url);suggestions=facts(html)
    except (OSError,http.client.HTTPException):raise ValueError('The company website could not be read. No changes were made.') from None
    settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);typ=next((t for t in settings['types'] if t['id']=='companies'),None)
    if not typ:raise ValueError('The Companies record type is required.')
    allowed={'name','notes'}|{f['key'] for f in typ['fields']};suggestions={k:v for k,v in suggestions.items() if k in allowed and v!=body.get(k)}
    if not company:
        matches=[r for r in db.execute("SELECT * FROM records WHERE kind='companies'") if domain(json.loads(r['body']).get('domain',''))==host]
        if matches:raise ValueError('Associate the existing domain company before enriching this contact.')
    job=dict(id=company['id'] if company else str(uuid.uuid4()),expected=company['updated'] if company else None,contact=contact['id'] if contact else '',contact_updated=contact['updated'] if contact else None,domain=host,source=source,suggestions=suggestions,before=body,checked=datetime.now(timezone.utc).isoformat())
    ident=str(uuid.uuid4());db.execute('DELETE FROM enrichment_previews WHERE expires<?',(time.time(),));db.execute('INSERT INTO enrichment_previews VALUES(?,?,?,?)',(ident,owner,time.time()+900,json.dumps(job)))
    return dict(preview_id=ident,source=source,checked=job['checked'],suggestions=suggestions,before=body,creates_company=not bool(company),domain=host)

def apply(db,owner,data,validate):
    row=db.execute('SELECT * FROM enrichment_previews WHERE id=? AND owner=?',(data.get('preview_id'),owner)).fetchone()
    if not row or row['expires']<time.time():raise ValueError('Preview expired. Review suggestions again.')
    job=json.loads(row['body']);fields=data.get('fields')
    if not isinstance(fields,list) or not fields or set(fields)-set(job['suggestions']):raise ValueError('Select suggested fields.')
    current=db.execute('SELECT updated,body FROM records WHERE id=?',(job['id'],)).fetchone()
    if (current['updated'] if current else None)!=job['expected']:raise ValueError('Company changed after preview. Review again.')
    if job['contact']:
        contact=db.execute('SELECT * FROM records WHERE id=?',(job['contact'],)).fetchone()
        if not contact or contact['updated']!=job['contact_updated']:raise ValueError('Contact changed after preview. Review again.')
    if not current:
        if data.get('create_company') is not True:raise ValueError('Confirm creation of the company.')
        if any(domain(json.loads(r[0]).get('domain',''))==job['domain'] for r in db.execute("SELECT body FROM records WHERE kind='companies'")):raise ValueError('A matching company was added. Review again.')
    body=json.loads(current['body']) if current else dict(name=job['domain'],domain=job['domain'],links=[job['contact']] if job['contact'] else [],record_source='Website enrichment')
    for key in fields:
        if current and body.get(key) not in (None,'',[]) and data.get('overwrite') is not True:raise ValueError('Replacing populated fields requires explicit confirmation.')
        body[key]=job['suggestions'][key]
    body['enrichment_source']=job['source'];body['enrichment_checked']=job['checked'];validate(db,'companies',body);now=datetime.now(timezone.utc).isoformat()
    db.execute('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated',(job['id'],'companies',json.dumps(body),now))
    if job['contact']:
        contact_body=json.loads(contact['body']);contact_body['links']=list(dict.fromkeys(contact_body.get('links',[])+[job['id']]));db.execute('UPDATE records SET body=?,updated=? WHERE id=?',(json.dumps(contact_body),now,job['contact']))
    db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),job['id'],json.dumps(dict(type='Note',text='Reviewed website enrichment: '+', '.join(fields)+'\nSource: '+job['source'])),now));db.execute('DELETE FROM enrichment_previews WHERE id=?',(row['id'],))
    return {'ok':True,'id':job['id']}
