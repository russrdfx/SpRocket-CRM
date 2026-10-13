"""On-demand, edition-specific public release checks. No hosting credentials needed."""
import json,re,time
from urllib.request import Request,urlopen
from app_version import release_info
REPO='russrdfx/SpRocket-CRM'
VERSION=re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$')
def version_key(value):
    match=VERSION.fullmatch(value)
    if not match:raise ValueError('Invalid release version.')
    major,minor,patch,pre=match.groups()
    identifiers=tuple((0,int(x)) if x.isdigit() else (1,x) for x in (pre or '').split('.'))
    return (int(major),int(minor),int(patch),1 if pre is None else 0,identifiers)
def release_tag(tag,edition):
    prefix='web-v' if edition=='web' else 'v'
    if not isinstance(tag,str) or not tag.startswith(prefix):return None
    value=tag[len(prefix):]
    return value if VERSION.fullmatch(value) else None

def select_release(releases,edition,channel):
    selected=[]
    for release in releases:
        value=release_tag(release.get('tag_name'),edition)
        if not value or release.get('draft'):continue
        if channel=='stable' and (release.get('prerelease') or '-' in value):continue
        selected.append((version_key(value),release,value))
    if not selected:return None
    _,release,value=max(selected,key=lambda entry:entry[0]);tag=release['tag_name']
    return dict(version=value,tag=tag,url='https://github.com/'+REPO+'/releases/tag/'+tag,notes=str(release.get('body') or '')[:20000],published_at=release.get('published_at',''),prerelease=bool(release.get('prerelease') or '-' in value))

def fetch_releases():
    request=Request('https://api.github.com/repos/'+REPO+'/releases?per_page=100',headers={'Accept':'application/vnd.github+json','User-Agent':'SpRocket-CRM-update-check'})
    with urlopen(request,timeout=10) as response:
        if response.url.split('?')[0]!='https://api.github.com/repos/'+REPO+'/releases':raise ValueError('Unexpected update source.')
        data=json.loads(response.read(2000000))
    if not isinstance(data,list):raise ValueError('Invalid release response.')
    return data

class Updates:
    def __init__(self,connect):self.connect=connect
    def initialize(self):
        with self.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS update_status(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)')
    def status(self):
        installed=release_info();edition=installed['edition'];channel='beta' if '-' in installed['version'] else 'stable'
        with self.connect() as db:row=db.execute('SELECT body FROM update_status WHERE id=1').fetchone()
        stored=json.loads(row[0]) if row else {}
        if stored.get('edition')!=edition:stored={}
        latest=stored.get('latest');available=bool(latest and version_key(latest['version'])>version_key(installed['version']))
        return dict(installed=installed,channel=stored.get('channel',channel),checked_at=stored.get('checked_at'),latest=latest,error=stored.get('error',''),update_available=available)
    def check(self,channel):
        if channel not in ('stable','beta'):raise ValueError('Choose Stable or Beta.')
        edition=release_info()['edition']
        if edition=='source':raise ValueError('This is a source checkout. Choose a packaged desktop or web release for deployment.')
        previous=self.status()
        if previous.get('checked_at') and previous['channel']==channel and time.time()-previous['checked_at']<60:return previous
        body=dict(edition=edition,channel=channel,checked_at=time.time(),latest=None,error='')
        try:body['latest']=select_release(fetch_releases(),edition,channel)
        except Exception:body['error']='Release check failed. Try again later. Your installed version is unchanged.'
        with self.connect() as db:db.execute('INSERT INTO update_status VALUES (1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(json.dumps(body),))
        return self.status()
