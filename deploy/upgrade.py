"""Approved host-side Docker upgrade. Retains the existing project, env and volumes."""
import argparse,fcntl,json,os,re,shutil,stat,subprocess,tempfile,time,urllib.request,zipfile
from pathlib import Path
REPO='russrdfx/SpRocket-CRM'
TAG=re.compile(r'^web-v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$')
SHA=re.compile(r'^[a-f0-9]{40}$')
def request_json(path):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers={'User-Agent':'SpRocket-approved-upgrade','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def resolve(tag):
    if not TAG.fullmatch(tag):raise ValueError('Choose an exact web release tag, such as web-v0.2.0-beta.2.')
    release=request_json('releases/tags/'+tag)
    if release.get('draft') or release.get('tag_name')!=tag:raise ValueError('Release is unavailable.')
    obj=request_json('git/ref/tags/'+tag)['object']
    for _ in range(3):
        if obj['type']=='commit' and SHA.fullmatch(obj['sha']):return obj['sha']
        if obj['type']!='tag' or not SHA.fullmatch(obj['sha']):break
        obj=request_json('git/tags/'+obj['sha'])['object']
    raise ValueError('Release commit could not be verified.')
def extract(archive,destination):
    with zipfile.ZipFile(archive) as package:
        entries=package.infolist()
        if len(entries)>10000 or sum(item.file_size for item in entries)>50000000:raise ValueError('Release archive is too large.')
        for item in entries:
            parts=Path(item.filename).parts
            if not parts or parts[0] in ('/','..') or '..' in parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise ValueError('Unsafe archive member.')
        for item in entries:
            relative=Path(*Path(item.filename).parts[1:])
            if str(relative)=='.':continue
            target=destination/relative
            if item.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with package.open(item) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
def contract(stage,current,tag):
    info=json.loads((stage/'upgrade.json').read_text())
    if info.get('version')!=tag[5:] or info.get('database_schema')!=1 or current not in info.get('compatible_from',[]) or info.get('app_only_rollback') is not True:raise ValueError('This upgrade needs a release-specific migration/recovery procedure. No app changes were made.')
    return info
def run(cmd,**kwargs):return subprocess.run(cmd,check=True,**kwargs)
def output(cmd):return subprocess.check_output(cmd,text=True).strip()
def compose(root,project=None,override=None):
    args=['docker','compose','--project-directory',str(root),'--env-file',str(root/'deploy/.env')]
    if project:args+=['--project-name',project]
    args+=['-f',str(root/'compose.yaml')]
    if override:args+=['-f',str(override)]
    return args
def write_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));os.chmod(temp,0o600);os.replace(temp,path)
def override(path,image,stage=None):
    # JSON is valid YAML; avoids shell interpolation or unsafe configuration parsing.
    app={'image':image}
    if stage:app['build']={'context':str(stage),'dockerfile':'deploy/Dockerfile'}
    path.write_text(json.dumps({'services':{'app':app}}));os.chmod(path,0o600)
def verify(cmd,version=None):
    for _ in range(60):
        try:
            code="import json,urllib.request; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)); assert r.get('ready'); "+("from app_version import release_info; print(release_info()['version'])" if version else "print('ready')")
            raw=output(cmd+['exec','-T','app','python','-c',code])
            if raw==(version or 'ready'):return
        except subprocess.CalledProcessError:pass
        time.sleep(2)
    raise ValueError('The updated app did not pass its health/version check.')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--version');parser.add_argument('--approve',action='store_true');parser.add_argument('--rollback',action='store_true');parser.add_argument('--from-version',help='Required only for the first upgrade from an app with no version metadata.');parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));args=parser.parse_args()
    root=Path(args.root).resolve();folder=root/'.updates';folder.mkdir(mode=0o700,exist_ok=True)
    if not(root/'deploy/.env').is_file():parser.error('Existing deploy/.env is required. Do not generate replacement secrets.')
    with (folder/'lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        journal=folder/'last-upgrade.json';base=compose(root);config=json.loads(output(base+['config','--format','json']));project=config['name'];base=compose(root,project)
        if args.rollback:
            if not args.approve:parser.error('Use --rollback --approve after reviewing the last upgrade and backup.')
            previous=json.loads(journal.read_text())
            if previous['project']!=project:raise ValueError('The upgrade belongs to a different Docker project.')
            previous_image=previous['previous_image'];fallback=folder/'rollback.json';override(fallback,previous_image)
            run(compose(root,project,fallback)+['up','-d','--no-deps','--no-build','app']);verify(compose(root,project,fallback));previous['status']='app_rolled_back';write_json(journal,previous)
            print('Previous app image restored. Database retained. Check the app; full database restoration is a separate recovery operation.');return
        sha=resolve(args.version or '');stage=folder/sha
        if not stage.exists():
            with tempfile.TemporaryDirectory(dir=folder) as temp:
                temp=Path(temp);archive=temp/'source.zip'
                req=urllib.request.Request('https://codeload.github.com/'+REPO+'/zip/'+sha,headers={'User-Agent':'SpRocket-approved-upgrade'})
                with urllib.request.urlopen(req,timeout=60) as response,archive.open('wb') as target:
                    if response.url!='https://codeload.github.com/'+REPO+'/zip/'+sha:raise ValueError('Unexpected archive source.')
                    size=0
                    while True:
                        chunk=response.read(65536)
                        if not chunk:break
                        size+=len(chunk)
                        if size>25000000:raise ValueError('Release download is too large.')
                        target.write(chunk)
                unpack=temp/'source';unpack.mkdir();extract(archive,unpack);os.replace(unpack,stage)
        cid=output(base+['ps','-q','app'])
        if not cid:raise ValueError('The existing app must be running before an upgrade.')
        previous_image=output(['docker','inspect','--format','{{.Image}}',cid])
        try:current=output(base+['exec','-T','app','python','-c',"from app_version import release_info; print(release_info()['version'])"])
        except subprocess.CalledProcessError:current=args.from_version or ''
        info=contract(stage,current,args.version)
        print('Approved target:',args.version,'commit',sha,'from',current)
        if not args.approve:print('Preview complete. Re-run with --approve to build, back up, upgrade and verify.');return
        target_image='sprocket-approved:'+sha;target_override=folder/'target.json';override(target_override,target_image,stage);target=compose(root,project,target_override)
        run(target+['build','app']) # Build before stopping the current app.
        backups=root/'backups';backups.mkdir(mode=0o700,exist_ok=True);backup=backups/('SpRocket-pre-upgrade-'+str(time.time_ns())+'.dump');partial=backup.with_suffix('.partial')
        record=dict(project=project,from_version=current,to_version=info['version'],commit=sha,previous_image=previous_image,backup=str(backup),status='prepared');write_json(journal,record)
        run(base+['stop','app'])
        try:
            with partial.open('wb') as file:
                os.chmod(partial,0o600);run(base+['exec','-T','db','pg_dump','-U','sprocket','-d','sprocket','--format=custom'],stdout=file);file.flush();os.fsync(file.fileno())
            with partial.open('rb') as file:
                if file.read(5)!=b'PGDMP':raise ValueError('Backup archive is incomplete.')
            with partial.open('rb') as file:run(base+['exec','-T','db','pg_restore','--list'],stdin=file,stdout=subprocess.DEVNULL)
            os.replace(partial,backup);record['status']='backed_up';write_json(journal,record)
            run(target+['up','-d','--no-deps','--no-build','app']);verify(target,info['version']);record['status']='verified';write_json(journal,record)
        except BaseException:
            fallback=folder/'rollback.json';override(fallback,previous_image);run(compose(root,project,fallback)+['up','-d','--no-deps','--no-build','app']);verify(compose(root,project,fallback));record['status']='app_rolled_back';write_json(journal,record);raise
        print('Upgrade verified. Workspace and volumes retained. Backup:',backup)
if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit('Upgrade stopped: '+str(error))
