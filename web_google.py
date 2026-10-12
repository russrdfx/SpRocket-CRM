"""Google OIDC sign-in with explicit account linking and invitation-only admission."""
import base64,hashlib,hmac,json,os,secrets,time,uuid
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import jwt
from cryptography.fernet import Fernet
from web_accounts import digest,email_address

class GoogleSignInError(ValueError):pass

class GoogleSignIn:
    callback='/auth/google/callback'
    def __init__(self,accounts):
        self.accounts=accounts;self.connect=accounts.connect
        self.keys=jwt.PyJWKClient('https://www.googleapis.com/oauth2/v3/certs',timeout=10)
    def initialize(self):
        with self.connect() as db:db.executescript('''
        CREATE TABLE IF NOT EXISTS web_google_identities(subject TEXT PRIMARY KEY,user_id TEXT NOT NULL UNIQUE REFERENCES web_users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS web_google_pending(state TEXT PRIMARY KEY,body TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL);
        ''')
    def available(self):return bool(os.getenv('GOOGLE_MAIL_CLIENT_ID') and os.getenv('GOOGLE_MAIL_CLIENT_SECRET'))
    def linked(self,user):
        if not user:return False
        with self.connect() as db:return bool(db.execute('SELECT 1 FROM web_google_identities WHERE user_id=?',(user['subject'],)).fetchone())
    def cipher(self):return Fernet(os.environ['MAIL_TOKEN_KEY'].encode())
    def begin(self,headers,invite=''):
        if not self.available() or not self.accounts.ready():raise GoogleSignInError('Google sign-in is unavailable.')
        user=self.accounts.user(headers);invitation=''
        if invite:
            with self.connect() as db:row=db.execute('SELECT email FROM web_invites WHERE token=? AND expires>?',(digest(invite),time.time())).fetchone()
            if not row:raise GoogleSignInError('Invitation is invalid or expired.')
            invitation=digest(invite)
        state,nonce,verifier,browser=[secrets.token_urlsafe(32) for _ in range(4)]
        data=dict(nonce=nonce,verifier=verifier,browser=digest(browser),user_id=user['subject'] if user and not invitation else '',invite=invitation,client=os.environ['GOOGLE_MAIL_CLIENT_ID'])
        with self.connect() as db:
            db.execute('DELETE FROM web_google_pending WHERE expires<?',(time.time(),))
            if db.execute('SELECT COUNT(*) FROM web_google_pending').fetchone()[0]>=1000:raise GoogleSignInError('Too many pending sign-ins.')
            db.execute('INSERT INTO web_google_pending VALUES (?,?,?)',(digest(state),self.cipher().encrypt(json.dumps(data).encode()).decode(),time.time()+600))
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params=dict(client_id=data['client'],redirect_uri=self.accounts.origin+self.callback,response_type='code',scope='openid email profile',state=state,nonce=nonce,code_challenge=challenge,code_challenge_method='S256',prompt='select_account')
        return 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params),self.accounts.cookie('sprocket_google_login',browser,600)
    def exchange(self,code,attempt):
        if attempt['client']!=os.environ.get('GOOGLE_MAIL_CLIENT_ID'):raise GoogleSignInError('Google configuration changed. Start again.')
        body=urlencode(dict(client_id=attempt['client'],client_secret=os.environ['GOOGLE_MAIL_CLIENT_SECRET'],code=code,code_verifier=attempt['verifier'],grant_type='authorization_code',redirect_uri=self.accounts.origin+self.callback)).encode()
        with urlopen(Request('https://oauth2.googleapis.com/token',data=body,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=10) as response:tokens=json.loads(response.read(1000000))
        token=tokens['id_token'];key=self.keys.get_signing_key_from_jwt(token).key
        return jwt.decode(token,key,algorithms=['RS256'],audience=attempt['client'],issuer=['https://accounts.google.com','accounts.google.com'],options={'require':['exp','iat','iss','aud','sub','nonce','email','email_verified']})
    def finish(self,query,headers):
        state=query.get('state',[''])[0]
        with self.connect() as db:
            row=db.execute('DELETE FROM web_google_pending WHERE state=? AND expires>? RETURNING body',(digest(state),time.time())).fetchone()
            if not row:raise GoogleSignInError('Invalid or expired sign-in.')
            attempt=json.loads(self.cipher().decrypt(row['body'].encode()))
            if not hmac.compare_digest(attempt['browser'],digest(self.accounts.cookie_value(headers,'sprocket_google_login'))):raise GoogleSignInError('Invalid browser session.')
        if 'error' in query or not query.get('code'):raise GoogleSignInError('Google sign-in was cancelled.')
        claims=self.exchange(query['code'][0],attempt)
        if claims.get('email_verified') is not True or not isinstance(claims.get('sub'),str) or not claims['sub'] or not hmac.compare_digest(str(claims.get('nonce','')),attempt['nonce']):raise GoogleSignInError('Google identity could not be verified.')
        if ('azp' in claims and claims['azp']!=attempt['client']) or (isinstance(claims.get('aud'),list) and len(claims['aud'])>1 and claims.get('azp')!=attempt['client']):raise GoogleSignInError('Invalid authorized party.')
        email=email_address(claims['email']);current=self.accounts.user(headers)
        with self.connect() as db:
            # Serialize first-time identity linking and invitation acceptance.
            db.execute('LOCK TABLE web_users IN EXCLUSIVE MODE')
            identity=db.execute('SELECT user_id FROM web_google_identities WHERE subject=?',(claims['sub'],)).fetchone()
            if attempt['user_id']:
                if not current or current['subject']!=attempt['user_id'] or current['email']!=email:raise GoogleSignInError('Sign in to your workspace account and choose the matching Google email to link it.')
                ident=current['subject']
                if identity and identity['user_id']!=ident:raise GoogleSignInError('This Google identity is already linked.')
                existing=db.execute('SELECT subject FROM web_google_identities WHERE user_id=?',(ident,)).fetchone()
                if existing and existing['subject']!=claims['sub']:raise GoogleSignInError('A different Google identity is already linked.')
                if not identity:db.execute('INSERT INTO web_google_identities VALUES (?,?)',(claims['sub'],ident))
            elif identity:ident=identity['user_id']
            elif attempt['invite']:
                invite=db.execute('DELETE FROM web_invites WHERE token=? AND email=? AND expires>? RETURNING role',(attempt['invite'],email,time.time())).fetchone()
                if not invite:raise GoogleSignInError('Use a valid invitation and its matching Google email.')
                if db.execute('SELECT 1 FROM web_users WHERE email=?',(email,)).fetchone():raise GoogleSignInError('Sign in with your password first, then link Google in Security.')
                ident=str(uuid.uuid4());name=str(claims.get('name') or email)[:100]
                db.execute('INSERT INTO web_users VALUES (?,?,?,?,?,1)',(ident,email,name,'!',invite['role']))
                db.execute('INSERT INTO web_google_identities VALUES (?,?)',(claims['sub'],ident))
                db.execute('INSERT INTO user_profiles VALUES (?,?)',(json.dumps([self.accounts.issuer,ident]),json.dumps(dict(name=name,job_title='',phone=''))))
            else:raise GoogleSignInError('Ask for a workspace invitation, or sign in with your password and link Google in Security.')
            user=db.execute('SELECT id FROM web_users WHERE id=? AND active=1',(ident,)).fetchone()
            if not user:raise GoogleSignInError('This workspace account is unavailable.')
            cookie=self.accounts.session(db,ident,headers,'google')
        return cookie
