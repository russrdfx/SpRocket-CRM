"""Single private workspace behind a trusted HTTPS proxy; WSGI entry point."""
import base64,hashlib,io,json,os,sqlite3,threading,time
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from web_accounts import Accounts
from web_database import Database

origin=(os.environ.get('SPROCKET_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL','')).rstrip('/')
parsed=urlsplit(origin)
if not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or (parsed.scheme!='https' and not(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost'))):raise ValueError('Set SPROCKET_ORIGIN to your HTTPS domain (localhost HTTP is allowed for testing).')
if not os.environ.get('DATABASE_URL'):raise ValueError('DATABASE_URL is required for the web version.')
if not os.environ.get('MAIL_TOKEN_KEY') and os.environ.get('SPROCKET_TOKEN_SECRET'):
    os.environ['MAIL_TOKEN_KEY']=base64.urlsafe_b64encode(hashlib.sha256(os.environ['SPROCKET_TOKEN_SECRET'].encode()).digest()).decode()
if not os.environ.get('MAIL_TOKEN_KEY'):raise ValueError('MAIL_TOKEN_KEY or SPROCKET_TOKEN_SECRET is required for the web version.')
# Disable local-only demo/desktop entry points; imported CRM handlers are never bound to a public socket.
os.environ['SPROCKET_WEB']='1'
os.environ['SPROCKET_ORIGIN']=origin
import web_provider
web_provider.connect=lambda:Database(os.environ['DATABASE_URL'])
with web_provider.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS web_provider_config(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)')
web_provider.apply()
import server
server.connect=lambda:Database(os.environ['DATABASE_URL'])
server.MAIL.connect=server.connect
server.CALENDAR.connect=server.connect
from web_migrations import migrate
migrate(server.connect)
server.initialize()
server.Updates(server.connect).initialize()
accounts=Accounts(server.connect,origin,os.environ.get('SPROCKET_SETUP_TOKEN',''));accounts.initialize()
from web_google import GoogleSignIn,GoogleSignInError
google=GoogleSignIn(accounts);google.initialize()
with server.connect() as db:db.execute("CREATE TABLE IF NOT EXISTS web_calendar_auto(account_id TEXT PRIMARY KEY REFERENCES calendar_accounts(id) ON DELETE CASCADE,start_date TEXT NOT NULL,end_date TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,checked DOUBLE PRECISION NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '')")
server.AUTH=accounts

class WebHandler(server.Handler):
    def sso_admin(self):
        user=accounts.user(self.headers);return bool(user and user['role']=='admin')
    def send_response(self,code,message=None):self.status=code
    def send_header(self,key,value):self.response_headers.append((key,str(value)))
    def end_headers(self):pass
    def reply(self,status,body,cookies=None):
        if self.path.split('?')[0]=='/api/state' and status==200:body['deployment']={'web':True,'background_jobs':os.environ.get('SPROCKET_WEB_JOBS','1')=='1'}
        super().reply(status,body,cookies or [])
    def html(self,name):
        raw=(server.ROOT/'web'/name).read_bytes();self.status=200;self.send_header('Content-Type','text/html; charset=utf-8');self.wfile.write(raw)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/email-open/'):return self.tracking_pixel()
        if path=='/health':return self.reply(200,{'ready':True})
        if path.startswith(('/desktop/','/api/desktop/')):return self.reply(404,{'error':'Not available in the web version.'})
        if path in ('/setup','/join'):return self.html('web-login.html')
        if path in ('/web-login.js','/web-admin.js'):
            self.status=200;self.send_header('Content-Type','text/javascript');self.wfile.write((server.ROOT/'web'/path[1:]).read_bytes());return
        if path=='/login':return self.html('web-login.html')
        if path=='/auth/login':return self.redirect('/login')
        if path=='/api/web/status':return self.reply(200,{'setup_required':not accounts.ready(),'google_available':google.available()})
        if path=='/auth/google':
            try:
                query=parse_qs(urlsplit(self.path).query);location,cookie=google.begin(self.headers,query.get('invite',[''])[0])
                return self.redirect(location,[cookie])
            except Exception:return self.redirect('/login?google_error=unavailable')
        if path=='/auth/google/callback':
            try:
                cookie=google.finish(parse_qs(urlsplit(self.path).query),self.headers)
                return self.redirect('/',[cookie,accounts.cookie('sprocket_google_login','',0)])
            except GoogleSignInError as error:
                # Return only our own admission guidance, never provider payloads or credentials.
                self.status=200;self.send_header('Content-Type','text/html; charset=utf-8')
                from html import escape
                self.wfile.write(('<!doctype html><html lang="en"><meta charset="utf-8"><title>Google sign-in</title><link rel="stylesheet" href="/style.css"><body class="login-page"><section class="panel"><h1>Google sign-in</h1><p>'+escape(str(error))+'</p><a href="/login">Return to sign in</a></section></body></html>').encode());return
            except Exception:return self.redirect('/login?google_error=failed')

        if not accounts.user(self.headers) and path not in ('/api/auth','/style.css') and not path.startswith('/assets/brand/'):
            return self.reply(401,{'error':'Sign-in required'}) if path.startswith('/api/') else self.redirect('/setup' if not accounts.ready() else '/login')
        if path=='/api/web/google':return self.reply(200,{'available':google.available(),'linked':google.linked(accounts.user(self.headers))})
        if path=='/api/web/calendar-auto':
            owner=self.mail_owner()
            with server.connect() as db:rows=[dict(r) for r in db.execute('SELECT s.* FROM web_calendar_auto s JOIN calendar_accounts a ON a.id=s.account_id WHERE a.owner=?',(owner,))]
            return self.reply(200,{'settings':rows})
        if path=='/api/web/provider':
            if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
            return self.reply(200,web_provider.status())
        if path=='/api/web/users':
            if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
            return self.reply(200,{'users':accounts.users()})
        if path=='/api/sso':return self.reply(200,{'web_accounts':True})
        super().do_GET()
        if path=='/' and self.status==200:
            value=self.wfile.getvalue().replace(b'</body>',b'<script src="/web-admin.js"></script></body>');self.wfile=io.BytesIO(value)
            self.response_headers=[(k,str(len(value)) if k.lower()=='content-length' else v) for k,v in self.response_headers]
    def do_POST(self):
        path=urlsplit(self.path).path
        if self.headers.get('Origin')!=origin:return self.reply(403,{'error':'Invalid origin'})
        if path.startswith(('/desktop/','/api/desktop/')):return self.reply(404,{'error':'Not available in the web version.'})
        if path in ('/api/web/login','/api/web/setup','/api/web/join','/api/web/invite','/api/web/provider','/api/web/calendar-auto'):
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'JSON required'})
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=10000:raise ValueError('Request is too large or empty.')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Invalid request.')
                if path=='/api/web/login':return self.reply(200,{'ok':True},[accounts.login(data,self.client_address[0])])
                if path=='/api/web/setup':accounts.register(data,setup=True);return self.reply(200,{'ok':True})
                if path=='/api/web/join':accounts.register(data);return self.reply(200,{'ok':True})
                if path=='/api/web/calendar-auto':
                    from datetime import date
                    user=accounts.user(self.headers)
                    if not user:return self.reply(401,{'error':'Sign-in required'})
                    if not isinstance(data.get('enabled'),bool):raise ValueError('Choose enable or pause.')
                    start=date.fromisoformat(data['start']);end=date.fromisoformat(data['end'])
                    if not 0<=(end-start).days<366:raise ValueError('Choose up to a year.')
                    with server.connect() as db:
                        server.CALENDAR.account(db,self.mail_owner(),data['account_id'])
                        db.execute('INSERT INTO web_calendar_auto(account_id,start_date,end_date,enabled) VALUES (?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET start_date=excluded.start_date,end_date=excluded.end_date,enabled=excluded.enabled,checked=0,error=\'\'',(data['account_id'],data['start'],data['end'],int(data['enabled'])))
                    return self.reply(200,{'ok':True})
                if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
                if path=='/api/web/provider':return self.reply(200,web_provider.save(data))
                return self.reply(200,accounts.invite(data))
            except (ValueError,KeyError,TypeError,sqlite3.IntegrityError,server.MailError):return self.reply(400,{'error':'Check the entered details, invitation, setup code, or sign-in attempt. Passwords need 12–128 characters.'})
        if not accounts.user(self.headers):return self.reply(401,{'error':'Sign-in required'})
        if path in ('/api/settings','/api/sso','/api/sso/test','/api/automation/rule','/api/updates/check') and not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
        if path.startswith('/api/sso'):return self.reply(400,{'error':'This web preview uses workspace accounts. OIDC web sign-in is a future integration.'})
        if path.startswith('/api/backup/'):
            if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
            return self.reply(400,{'error':'Use the PostgreSQL backup and restore commands in WEB.md. SQLite backup files are for the desktop edition.'})
        super().do_POST()

def application(environ,start_response):
    if environ.get('HTTP_HOST')!=parsed.netloc and not(environ.get('PATH_INFO')=='/health' and environ.get('REQUEST_METHOD')=='GET'):
        start_response('400 Bad Request',[('Content-Type','application/json')]);return [b'{"error":"Invalid host"}']
    handler=object.__new__(WebHandler);handler.path=environ.get('PATH_INFO','/')+('?' + environ['QUERY_STRING'] if environ.get('QUERY_STRING') else '')
    handler.client_address=(environ.get('REMOTE_ADDR',''),0);handler.headers=Message()
    for key,value in environ.items():
        if key.startswith('HTTP_'):handler.headers[key[5:].replace('_','-')]=value
    for key in ('CONTENT_TYPE','CONTENT_LENGTH'):
        if key in environ:handler.headers[key.replace('_','-')]=environ[key]
    handler.rfile=environ['wsgi.input'];handler.wfile=io.BytesIO();handler.response_headers=[];handler.status=200
    try:
        if environ['REQUEST_METHOD']=='GET':handler.do_GET()
        elif environ['REQUEST_METHOD']=='POST':handler.do_POST()
        elif environ['REQUEST_METHOD']=='HEAD' and environ.get('PATH_INFO','').startswith('/email-open/'):handler.do_HEAD()
        else:handler.reply(405,{'error':'Method not allowed'})
    except Exception:
        # Provider tokens, database URLs and submitted passwords never enter the response/logs.
        handler.wfile=io.BytesIO();handler.response_headers=[];handler.reply(500,{'error':'The request could not be completed. Please try again.'})
    handler.response_headers.extend([('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"),('Cache-Control','no-store')])
    start_response(str(handler.status)+' '+HTTPStatus(handler.status).phrase,handler.response_headers);return [handler.wfile.getvalue()]

job_lock=threading.Lock()
def background_tick():
    with job_lock:
        with server.connect() as db:
            active=db.execute('SELECT id,name FROM web_users WHERE active=1').fetchall()
        for user in active:
            try:
                owner=json.dumps([accounts.issuer,user['id']]);profile=server.MAIL.profile(owner)
                server.MAIL.auto_tick(owner,{'_crm_owner':profile.get('name') or user['name']})
            except Exception:pass # Account status records provider errors; do not log private payloads.
        with server.connect() as db:
            jobs=db.execute('SELECT s.*,a.owner FROM web_calendar_auto s JOIN calendar_accounts a ON a.id=s.account_id WHERE s.enabled=1 AND s.checked<?',(time.time()-600,)).fetchall()
        for job in jobs:
            error=''
            try:
                continuation=''
                while True:
                    result=server.CALENDAR.sync(job['owner'],dict(account_id=job['account_id'],start=job['start_date'],end=job['end_date'],page_token=continuation))
                    continuation=result['next_page']
                    if not continuation:break
            except server.MailError as exc:error=str(exc)
            except Exception:error='Calendar refresh failed. Try syncing manually.'
            with server.connect() as db:db.execute('UPDATE web_calendar_auto SET checked=?,error=? WHERE account_id=?',(time.time(),error,job['account_id']))
        with server.connect() as db:server.automation.inactive(db,server.validate_record)
def background_loop():
    while True:
        try:background_tick()
        except Exception:pass
        time.sleep(60)
if os.environ.get('SPROCKET_WEB_JOBS','1')=='1':threading.Thread(target=background_loop,daemon=True).start()
