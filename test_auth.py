import os
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from types import SimpleNamespace
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from auth import OIDC
from test_server import CRMTest, app

ENV={'OIDC_ISSUER':'https://identity.example','OIDC_CLIENT_ID':'demo-client','OIDC_CLIENT_SECRET':'test-only-secret','OIDC_ALLOWED_SUBJECTS':'allowed-user','SPROCKET_ORIGIN':'http://127.0.0.1:8765'}

class OIDCTest(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, ENV):self.auth=OIDC()
        self.auth.metadata={'issuer':self.auth.issuer,'authorization_endpoint':'https://identity.example/authorize','token_endpoint':'https://identity.example/token','jwks_uri':'https://identity.example/keys'}
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    def attempt(self):
        url,cookie=self.auth.begin();q=parse_qs(urlparse(url).query)
        self.assertEqual(['S256'],q['code_challenge_method'])
        self.assertIn('HttpOnly',cookie)
        return q,{'Cookie':cookie.split(';')[0]}
    def finish(self, changes=None, headers=None):
        q,h=self.attempt();now=int(time.time())
        claims={'iss':self.auth.issuer,'aud':self.auth.client,'sub':'allowed-user','iat':now,'exp':now+3600,'nonce':q['nonce'][0]}
        claims.update(changes or {})
        token=jwt.encode(claims,self.key,algorithm='RS256')
        with patch.object(self.auth,'fetch',return_value={'id_token':token}),patch.object(jwt,'PyJWKClient') as client:
            client.return_value.get_signing_key_from_jwt.return_value=SimpleNamespace(key=self.key.public_key())
            return self.auth.finish({'state':q['state'],'code':['demo-code']},headers if headers is not None else h)
    def test_session_and_logout(self):
        cookie=self.finish();h={'Cookie':cookie.split(';')[0]}
        self.assertEqual('allowed-user',self.auth.user(h)['subject'])
        self.auth.logout(h);self.assertIsNone(self.auth.user(h))
    def test_invalid_tokens_and_admission(self):
        for changes in [{'nonce':'wrong'},{'iss':'https://wrong.example'},{'aud':'other-client'},{'sub':'outsider'},{'exp':int(time.time())-10},{'azp':'other-client'}]:
            with self.subTest(changes=changes),self.assertRaises(Exception):self.finish(changes)
    def test_browser_binding_and_single_use(self):
        q,h=self.attempt()
        with self.assertRaises(ValueError):self.auth.finish({'state':q['state'],'code':['code']},{'Cookie':'sprocket_login=wrong'})
        with self.assertRaises(ValueError):self.auth.finish({'state':q['state'],'code':['code']},h)
    def test_expired_session(self):
        self.auth.sessions['old']={'expires':time.time()-1,'user':{'subject':'allowed-user'}}
        self.assertIsNone(self.auth.user({'Cookie':'sprocket_session=old'}))
    def test_fail_closed_config(self):
        with patch.dict(os.environ,{**ENV,'OIDC_CLIENT_SECRET':''}),self.assertRaises(ValueError):OIDC()

class ProtectedHTTPTest(CRMTest):
    def setUp(self):
        self.previous=app.AUTH
        with patch.dict(os.environ,ENV):app.AUTH=OIDC()
        super().setUp()
        app.AUTH.origin=self.url
    def tearDown(self):
        super().tearDown();app.AUTH=self.previous
    # Override inherited demo-mode tests; these validate the protected transport.
    def test_configuration_records_and_references(self):
        self.assertEqual(401,self.request('/api/state')[0])
        self.assertEqual(401,self.request('/api/record',{'kind':'contacts','body':{'name':'Blocked'}},self.url)[0])
    def test_cross_origin_write_blocked(self):
        app.AUTH.sessions['demo-session']={'expires':time.time()+60,'user':{'subject':'allowed-user'}}
        self.assertEqual(403,self.request('/api/record',{'kind':'contacts','body':{'name':'Blocked'}},'https://other.example')[0])
    def test_persistence(self):
        self.assertEqual(True,self.request('/api/auth')[1]['enabled'])
        self.assertIsNone(self.request('/api/auth')[1]['user'])

if __name__=='__main__':unittest.main()
