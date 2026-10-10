"""Optional OIDC authorization code login; opaque in-memory sessions."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from sso_config import effective


class OIDC:
    def __init__(self):
        config = effective()
        self.issuer = config['issuer']
        self.client = config['client_id']
        self.secret = os.getenv('OIDC_CLIENT_SECRET', '')
        self.origin = (config['origin'] or 'http://127.0.0.1:8765').rstrip('/')
        self.allowed = set(filter(None, (x.strip() for x in config['subjects'].split(','))))
        self.enabled = bool(self.issuer)
        self.sessions = {}
        self.pending = {}
        self.lock = threading.Lock()
        self.metadata = None
        if any([self.client, self.secret, self.allowed]) and not self.enabled:
            raise ValueError('OIDC_ISSUER is required when SSO settings are present.')
        if self.enabled:
            import jwt
            self.jwt = jwt
            if not self.client or not self.secret or not self.allowed:
                raise ValueError('SSO requires client ID, secret and an explicit subject allowlist.')
            self.https(self.issuer)
            u = urlparse(self.origin)
            if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost')):
                raise ValueError('SPROCKET_ORIGIN requires HTTPS except on localhost.')
            if u.path or u.query or u.fragment or u.username:
                raise ValueError('SPROCKET_ORIGIN must be an origin without a path.')

    @staticmethod
    def https(url):
        u = urlparse(url)
        if u.scheme != 'https' or not u.hostname or u.username or u.fragment:
            raise ValueError('OIDC provider URLs must use HTTPS.')

    def fetch(self, url, data=None, headers=None):
        self.https(url)
        with urlopen(Request(url, data=data, headers=headers or {}), timeout=10) as response:
            self.https(response.url)
            return json.loads(response.read(1000000))

    def discover(self):
        if self.metadata is None:
            m = self.fetch(self.issuer.rstrip('/') + '/.well-known/openid-configuration')
            if m.get('issuer') != self.issuer:
                raise ValueError('Provider issuer mismatch.')
            for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                self.https(m[key])
            if 'client_secret_basic' not in m.get('token_endpoint_auth_methods_supported', ['client_secret_basic']):
                raise ValueError('Provider must support client_secret_basic.')
            self.metadata = m
        return self.metadata

    def cookie(self, name, value, age):
        return f'{name}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}' + ('; Secure' if self.origin.startswith('https:') else '')

    @staticmethod
    def cookie_value(headers, name):
        try:
            c = SimpleCookie(); c.load(headers.get('Cookie', ''))
            return c[name].value if name in c else ''
        except Exception:
            return ''

    def prune(self):
        now = time.time()
        for collection in (self.pending, self.sessions):
            for key in list(collection):
                if collection[key]['expires'] <= now:
                    del collection[key]

    def begin(self):
        m = self.discover()
        state, nonce, verifier, browser = [secrets.token_urlsafe(32) for _ in range(4)]
        with self.lock:
            self.prune()
            if len(self.pending) >= 1000:
                raise ValueError('Too many pending logins.')
            self.pending[state] = dict(nonce=nonce, verifier=verifier, browser=browser, expires=time.time()+600)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params = dict(client_id=self.client, response_type='code', scope='openid profile', redirect_uri=self.origin+'/auth/callback', state=state, nonce=nonce, code_challenge=challenge, code_challenge_method='S256')
        return m['authorization_endpoint'] + ('&' if '?' in m['authorization_endpoint'] else '?') + urlencode(params), self.cookie('sprocket_login', browser, 600)

    def finish(self, query, headers):
        state = query.get('state', [''])[0]
        with self.lock:
            self.prune()
            attempt = self.pending.pop(state, None)
        if not attempt or not hmac.compare_digest(attempt['browser'], self.cookie_value(headers, 'sprocket_login')):
            raise ValueError('Invalid or expired login attempt.')
        if 'error' in query or not query.get('code'):
            raise ValueError('Provider declined login.')
        m = self.discover()
        credentials = base64.b64encode((urlencode({'x':self.client})[2:]+':'+urlencode({'x':self.secret})[2:]).encode()).decode()
        tokens = self.fetch(m['token_endpoint'], urlencode(dict(grant_type='authorization_code', code=query['code'][0], redirect_uri=self.origin+'/auth/callback', code_verifier=attempt['verifier'])).encode(), {'Content-Type':'application/x-www-form-urlencoded','Authorization':'Basic '+credentials})
        token = tokens['id_token']
        key = self.jwt.PyJWKClient(m['jwks_uri'], timeout=10).get_signing_key_from_jwt(token).key
        claims = self.jwt.decode(token, key, algorithms=['RS256'], audience=self.client, issuer=self.issuer, options={'require':['exp','iat','iss','aud','sub','nonce']})
        if not hmac.compare_digest(str(claims['nonce']), attempt['nonce']):
            raise ValueError('Nonce mismatch.')
        if ('azp' in claims and claims['azp'] != self.client) or (isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != self.client):
            raise ValueError('Authorized party mismatch.')
        if claims['sub'] not in self.allowed:
            raise ValueError('This identity is not allowed into this workspace.')
        ident = secrets.token_urlsafe(32)
        with self.lock:
            old = self.cookie_value(headers, 'sprocket_session')
            self.sessions.pop(old, None)
            self.sessions[ident] = dict(expires=min(time.time()+28800, claims['exp']), user={'subject':claims['sub'], 'name':claims.get('name', claims['sub'])})
        return self.cookie('sprocket_session', ident, max(0,int(min(28800,claims['exp']-time.time()))))

    def user(self, headers):
        with self.lock:
            self.prune()
            session = self.sessions.get(self.cookie_value(headers, 'sprocket_session'))
            return session['user'] if session else None

    def logout(self, headers):
        with self.lock:
            self.sessions.pop(self.cookie_value(headers, 'sprocket_session'), None)
        return self.cookie('sprocket_session', '', 0)
