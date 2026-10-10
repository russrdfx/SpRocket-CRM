import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sso_config
from test_server import CRMTest, app

DATA={'issuer':'https://identity.example','client_id':'demo','origin':'http://127.0.0.1:8765','subjects':'demo-user'}
class ConfigTest(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(DATA,sso_config.validate(DATA))
        for change in [{'issuer':'http://identity.example'},{'origin':'http://public.example'},{'subjects':''},{'client_id':''},{'secret':'no'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):sso_config.validate({**DATA,**change})
    def test_file_and_environment_override(self):
        with tempfile.TemporaryDirectory() as d,patch.object(sso_config,'CONFIG',Path(d)/'sso.json'):
            sso_config.save(DATA)
            self.assertEqual(DATA,sso_config.read())
            self.assertEqual(0o600,sso_config.CONFIG.stat().st_mode & 0o777)
            with patch.dict('os.environ',{'OIDC_CLIENT_ID':'server-override'}):self.assertEqual('server-override',sso_config.effective()['client_id'])

class SetupHTTPTest(CRMTest):
    def setUp(self):
        super().setUp()
        self.config_patch=patch.object(sso_config,'CONFIG',Path(self.temp.name)/'sso.json');self.config_patch.start()
    def tearDown(self):
        self.config_patch.stop();super().tearDown()
    def test_setup_save_requires_origin(self):
        self.assertEqual(403,self.request('/api/sso',DATA)[0])
        self.assertEqual(200,self.request('/api/sso',DATA,self.url)[0])
        self.assertFalse(app.AUTH.enabled)
        self.assertEqual(DATA,self.request('/api/sso')[1]['config'])
    def test_discovery_mock(self):
        with patch.object(app.OIDC,'discover',return_value={'id_token_signing_alg_values_supported':['RS256']}):
            self.assertEqual(200,self.request('/api/sso/test',DATA,self.url)[0])
        self.assertFalse(sso_config.CONFIG.exists())
    def test_protected_admin(self):
        with patch.object(app.AUTH,'enabled',True),patch.object(app.AUTH,'user',return_value={'subject':'ordinary-user'}):
            self.assertEqual(403,self.request('/api/sso')[0])

if __name__=='__main__':unittest.main()
