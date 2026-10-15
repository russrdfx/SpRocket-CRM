"""Private web workspace accounts, invitations and persistent opaque sessions."""
import hashlib,hmac,json,secrets,time,uuid
from auth import OIDC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

def digest(token):return hashlib.sha256(token.encode()).hexdigest()
def password_hash(password,salt=None):
    if not isinstance(password,str) or not 12<=len(password)<=128:raise ValueError('Use a password with 12–128 characters.')
    salt=salt or secrets.token_hex(16)
    return salt+':'+Scrypt(salt=bytes.fromhex(salt),length=64,n=32768,r=8,p=3).derive(password.encode()).hex()
def email_address(value):
    from email.utils import parseaddr
    value=str(value).strip().lower()
    if len(value)>254 or parseaddr(value)[1]!=value or '@' not in value or any(c.isspace() for c in value):raise ValueError('Enter a valid email address.')
    return value
class Accounts:
    enabled=True;issuer='sprocket-web'
    def __init__(self,connect,origin,setup_token):self.connect=connect;self.origin=origin;self.setup_token=setup_token
    def initialize(self):
        with self.connect() as db:db.executescript('''
        CREATE TABLE IF NOT EXISTS web_users(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS web_sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,expires DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS web_invites(token TEXT PRIMARY KEY,email TEXT NOT NULL,role TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS web_recovery(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,expires DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS web_account_audit(id TEXT PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,created DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS web_attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
        ''');db.execute("ALTER TABLE web_sessions ADD COLUMN IF NOT EXISTS method TEXT NOT NULL DEFAULT 'password'")
    cookie=OIDC.cookie
    cookie_value=staticmethod(OIDC.cookie_value)
    def ready(self):
        with self.connect() as db:return bool(db.execute('SELECT 1 FROM web_users LIMIT 1').fetchone())
    def user(self,headers):
        token=self.cookie_value(headers,'sprocket_session')
        if not token:return None
        with self.connect() as db:
            row=db.execute('SELECT u.id,u.email,u.name,u.role,s.method FROM web_sessions s JOIN web_users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),time.time())).fetchone()
        return dict(subject=row['id'],email=row['email'],name=row['name'],role=row['role'],method=row['method']) if row else None
    def logout(self,headers):
        with self.connect() as db:db.execute('DELETE FROM web_sessions WHERE token=?',(digest(self.cookie_value(headers,'sprocket_session')),))
        return self.cookie('sprocket_session','',0)
    def login(self,data,ip):
        email=email_address(data.get('email',''));password=data.get('password','');key=digest(ip+'|'+email);now=time.time()
        with self.connect() as db:
            db.execute('INSERT INTO web_attempts VALUES (?,0,?) ON CONFLICT(key) DO NOTHING',(key,now+900))
            row=db.execute('SELECT * FROM web_attempts WHERE key=? FOR UPDATE',(key,)).fetchone()
            if row['reset_at']<now:db.execute('UPDATE web_attempts SET count=0,reset_at=? WHERE key=?',(now+900,key))
            elif row['count']>=10:raise ValueError('Too many sign-in attempts. Try again in 15 minutes.')
            db.execute('UPDATE web_attempts SET count=count+1 WHERE key=?',(key,))
        with self.connect() as db:row=db.execute('SELECT * FROM web_users WHERE email=? AND active=1',(email,)).fetchone()
        stored=row['password'] if row else '00'*16+':'+ '00'*64
        try:valid=hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)
        except (ValueError,TypeError):valid=False
        if not row or not valid:raise ValueError('Email or password is incorrect.')
        token=secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('DELETE FROM web_attempts WHERE key=?',(key,));db.execute('DELETE FROM web_sessions WHERE expires<?',(now,));db.execute('INSERT INTO web_sessions(token,user_id,expires) VALUES (?,?,?)',(digest(token),row['id'],now+28800))
        return self.cookie('sprocket_session',token,28800)
    def session(self,db,ident,headers,method='password'):
        token=secrets.token_urlsafe(32);now=time.time()
        db.execute('DELETE FROM web_sessions WHERE token=? OR expires<?',(digest(self.cookie_value(headers,'sprocket_session')),now))
        db.execute('INSERT INTO web_sessions(token,user_id,expires,method) VALUES (?,?,?,?)',(digest(token),ident,now+28800,method))
        return self.cookie('sprocket_session',token,28800)
    def register(self,data,setup=False):
        email=email_address(data.get('email',''));name=str(data.get('name','')).strip();password=password_hash(data.get('password',''))
        if not 1<=len(name)<=100:raise ValueError('Enter a display name up to 100 characters.')
        token=str(data.get('token',''));ident=str(uuid.uuid4());role='admin'
        with self.connect() as db:
            if setup:
                # Serialize bootstrap across requests; exactly one initial administrator.
                db.execute('LOCK TABLE web_users IN EXCLUSIVE MODE')
                if db.execute('SELECT 1 FROM web_users LIMIT 1').fetchone() or not self.setup_token or not hmac.compare_digest(token,self.setup_token):raise ValueError('Setup is unavailable or the setup code is incorrect.')
            else:
                invite=db.execute('DELETE FROM web_invites WHERE token=? AND email=? AND expires>? RETURNING role',(digest(token),email,time.time())).fetchone()
                if not invite:raise ValueError('Invitation is invalid or expired.')
                role=invite['role']
            db.execute('INSERT INTO web_users VALUES (?,?,?,?,?,1)',(ident,email,name,password,role))
            owner=json.dumps([self.issuer,ident]);db.execute('INSERT INTO user_profiles VALUES (?,?)',(owner,json.dumps(dict(name=name,job_title='',phone=''))))
            if setup:
                settings=json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]);settings['name']=str(data.get('workspace','SpRocket CRM')).strip()[:100] or 'SpRocket CRM';db.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(settings),))
        return ident
    def invite(self,data,actor=None):
        email=email_address(data.get('email',''));role=data.get('role','member')
        if role not in ('admin','member'):raise ValueError('Choose Administrator or Member.')
        token=secrets.token_urlsafe(32)
        with self.connect() as db:
            if actor:self.administrator(db,actor)
            if db.execute('SELECT 1 FROM web_users WHERE email=?',(email,)).fetchone():raise ValueError('This user already exists.')
            db.execute('DELETE FROM web_invites WHERE email=? OR expires<?',(email,time.time()))
            db.execute('INSERT INTO web_invites VALUES (?,?,?,?)',(digest(token),email,role,time.time()+86400))
            if actor:self.audit(db,actor,'invitation_created:'+role,email)
        return dict(url=self.origin+'/join?token='+token,email=email,expires_in=86400)
    def users(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT id,email,name,role,active FROM web_users ORDER BY name')]

    def audit(self,db,actor,action,target):
        db.execute('INSERT INTO web_account_audit VALUES (?,?,?,?,?)',(str(uuid.uuid4()),actor,action,target,time.time()))
    def administrator(self,db,actor):
        # Serialize all role/access changes; concurrent demotions cannot remove the last admin.
        db.execute('LOCK TABLE web_users IN EXCLUSIVE MODE')
        user=db.execute("SELECT id FROM web_users WHERE id=? AND role='admin' AND active=1",(actor,)).fetchone()
        if not user:raise ValueError('Administrator access required.')
    def administration(self):
        with self.connect() as db:
            invites=[dict(r) for r in db.execute('SELECT token AS id,email,role,expires FROM web_invites WHERE expires>? ORDER BY email',(time.time(),))]
            audit=[dict(r) for r in db.execute('SELECT actor,action,target,created FROM web_account_audit ORDER BY created DESC LIMIT 100')]
        return dict(users=self.users(),invitations=invites,audit=audit)
    def manage(self,actor,data):
        action=data.get('action');ident=data.get('id','')
        with self.connect() as db:
            self.administrator(db,actor)
            if action=='revoke_invite':
                invite=db.execute('DELETE FROM web_invites WHERE token=? RETURNING email',(ident,)).fetchone()
                if not invite:raise ValueError('Invitation no longer exists.')
                self.audit(db,actor,action,invite['email']);return dict(ok=True)
            user=db.execute('SELECT * FROM web_users WHERE id=?',(ident,)).fetchone()
            if not user:raise ValueError('User no longer exists.')
            if action in ('role','active'):
                if actor==ident:raise ValueError('Ask another administrator to change your own access.')
                role=data.get('role',user['role']) if action=='role' else user['role']
                active=data.get('active') if action=='active' else bool(user['active'])
                if role not in ('admin','member') or not isinstance(active,bool):raise ValueError('Choose valid access settings.')
                if user['role']=='admin' and user['active'] and (role!='admin' or not active):
                    if db.execute("SELECT COUNT(*) FROM web_users WHERE active=1 AND role='admin'").fetchone()[0]<=1:raise ValueError('Keep at least one active administrator.')
                db.execute('UPDATE web_users SET role=?,active=? WHERE id=?',(role,int(active),ident))
                db.execute('DELETE FROM web_sessions WHERE user_id=?',(ident,))
                db.execute('DELETE FROM web_recovery WHERE user_id=?',(ident,))
                self.audit(db,actor,'role:'+role if action=='role' else ('reactivated' if active else 'deactivated'),user['email'])
                return dict(ok=True)
            if action=='recovery':
                if not user['active']:raise ValueError('Reactivate this user before creating a recovery link.')
                token=secrets.token_urlsafe(32)
                db.execute('DELETE FROM web_recovery WHERE user_id=? OR expires<?',(ident,time.time()))
                db.execute('INSERT INTO web_recovery VALUES (?,?,?)',(digest(token),ident,time.time()+1800))
                self.audit(db,actor,'recovery_link_created',user['email'])
                return dict(url=self.origin+'/recover?token='+token,email=user['email'],expires_in=1800)
            raise ValueError('Choose a supported account action.')
    def recover(self,data):
        email=email_address(data.get('email',''));token=str(data.get('token',''))
        if len(token)>200:raise ValueError('Recovery link is invalid or expired.')
        with self.connect() as db:
            db.execute('LOCK TABLE web_users IN EXCLUSIVE MODE')
            row=db.execute('SELECT r.user_id FROM web_recovery r JOIN web_users u ON u.id=r.user_id WHERE r.token=? AND r.expires>? AND u.email=? AND u.active=1 FOR UPDATE',(digest(token),time.time(),email)).fetchone()
            if not row:raise ValueError('Recovery link is invalid or expired.')
            password=password_hash(data.get('password',''))
            db.execute('UPDATE web_users SET password=? WHERE id=?',(password,row['user_id']))
            db.execute('DELETE FROM web_recovery WHERE user_id=?',(row['user_id'],))
            db.execute('DELETE FROM web_sessions WHERE user_id=?',(row['user_id'],))
            self.audit(db,row['user_id'],'password_recovered',email)
        return dict(ok=True)
