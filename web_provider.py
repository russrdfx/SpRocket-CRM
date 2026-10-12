"""Administrator-owned Google credentials, encrypted with the deployment key."""
import json,os,re,tempfile
from pathlib import Path
from cryptography.fernet import Fernet

connect=None

def path():return Path(os.environ.get('SPROCKET_WEB_PROVIDER_CONFIG','data/web-provider.json'))
def load():
    if connect:
        with connect() as db:row=db.execute('SELECT body FROM web_provider_config WHERE id=1').fetchone()
        if row:return json.loads(Fernet(os.environ['MAIL_TOKEN_KEY'].encode()).decrypt(row[0].encode()))
    if not path().exists():return {}
    return json.loads(Fernet(os.environ['MAIL_TOKEN_KEY'].encode()).decrypt(path().read_bytes()))
def apply():
    stored=load()
    for key,env in [('client_id','GOOGLE_MAIL_CLIENT_ID'),('client_secret','GOOGLE_MAIL_CLIENT_SECRET')]:
        if stored.get(key):os.environ[env]=stored[key]
def status():return dict(client_id=os.getenv('GOOGLE_MAIL_CLIENT_ID',''),secret_configured=bool(os.getenv('GOOGLE_MAIL_CLIENT_SECRET')))
def save(data):
    client=str(data.get('client_id','')).strip();secret=str(data.get('client_secret','')).strip()
    if not re.fullmatch(r'[A-Za-z0-9-]+\.apps\.googleusercontent\.com',client):raise ValueError('Enter your Google OAuth web client ID.')
    if not secret:
        if client!=os.getenv('GOOGLE_MAIL_CLIENT_ID'):raise ValueError('Enter the secret for the new client.')
        secret=os.getenv('GOOGLE_MAIL_CLIENT_SECRET','')
    if not 1<=len(secret)<=300 or any(c.isspace() for c in secret):raise ValueError('Enter your Google client secret.')
    values=dict(client_id=client,client_secret=secret)
    if connect:
        encrypted=Fernet(os.environ['MAIL_TOKEN_KEY'].encode()).encrypt(json.dumps(values).encode()).decode()
        with connect() as db:db.execute('INSERT INTO web_provider_config VALUES (1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(encrypted,))
        os.environ['GOOGLE_MAIL_CLIENT_ID']=client;os.environ['GOOGLE_MAIL_CLIENT_SECRET']=secret
        return dict(ok=True)
    target=path();target.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as file:file.write(Fernet(os.environ['MAIL_TOKEN_KEY'].encode()).encrypt(json.dumps(values).encode()))
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    os.environ['GOOGLE_MAIL_CLIENT_ID']=client;os.environ['GOOGLE_MAIL_CLIENT_SECRET']=secret
    return dict(ok=True)
