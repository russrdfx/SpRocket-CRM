"""Run with SPROCKET_TEST_DATABASE_URL pointing to a disposable PostgreSQL database."""
import io,json,os,unittest
from unittest.mock import patch

@unittest.skipUnless(os.environ.get('SPROCKET_TEST_DATABASE_URL'),'Disposable PostgreSQL test database not configured')
class WebDeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=patch.dict(os.environ,{'DATABASE_URL':os.environ['SPROCKET_TEST_DATABASE_URL'],'SPROCKET_ORIGIN':'http://127.0.0.1:18766','SPROCKET_SETUP_TOKEN':'sample-setup-code','MAIL_TOKEN_KEY':'R0hFVTdNbHIybFY3WEt1bHloSXd1cEV0eTBha0g1VEo=','SPROCKET_WEB_JOBS':'0'})
        cls.env.start()
        import web_server
        cls.web=web_server
    @classmethod
    def tearDownClass(cls):cls.env.stop()
    def setUp(self):
        with self.web.server.connect() as db:
            db.execute('TRUNCATE web_users,web_invites,web_attempts,records,user_profiles,mail_accounts,calendar_accounts,calendar_logs,web_provider_config,saved_views CASCADE')
    def request(self,path,data=None,cookie='',host='127.0.0.1:18766',origin='http://127.0.0.1:18766'):
        raw=json.dumps(data).encode() if data is not None else b''
        env=dict(PATH_INFO=path,REQUEST_METHOD='POST' if data is not None else 'GET',HTTP_HOST=host,HTTP_ORIGIN=origin,HTTP_COOKIE=cookie,CONTENT_TYPE='application/json',CONTENT_LENGTH=str(len(raw)),REMOTE_ADDR='127.0.0.1',**{'wsgi.input':io.BytesIO(raw)})
        result={}
        body=b''.join(self.web.application(env,lambda status,headers:result.update(status=int(status.split()[0]),headers=headers)))
        result['body']=json.loads(body) if any(k=='Content-Type' and 'json' in v for k,v in result['headers']) else body.decode()
        return result
    def setup_admin(self):
        data=dict(email='admin@example.com',name='SAMPLE — Admin',password='SamplePassword123!',token='sample-setup-code',workspace='SAMPLE — Web workspace')
        self.assertEqual(self.request('/api/web/setup',data)['status'],200)
        login=self.request('/api/web/login',dict(email=data['email'],password=data['password']))
        self.assertEqual(login['status'],200)
        return next(v.split(';')[0] for k,v in login['headers'] if k=='Set-Cookie')
    def test_fail_closed_and_origin(self):
        self.assertEqual(self.request('/api/state')['status'],401)
        self.assertEqual(self.request('/api/state',host='evil.example')['status'],400)
        self.assertEqual(self.request('/api/web/setup',{},origin='https://evil.example')['status'],403)
        self.assertEqual(self.request('/api/desktop/health')['status'],404)
    def test_bootstrap_persistent_login_and_logout(self):
        cookie=self.setup_admin()
        self.assertEqual(self.request('/api/auth',cookie=cookie)['body']['user']['role'],'admin')
        from web_accounts import Accounts
        restarted=Accounts(self.web.server.connect,self.web.origin,'sample-setup-code')
        self.assertEqual(restarted.user({'Cookie':cookie})['email'],'admin@example.com')
        self.assertEqual(self.request('/api/web/setup',dict(email='other@example.com',name='Other',password='SamplePassword123!',token='sample-setup-code'))['status'],400)
        self.assertEqual(self.request('/auth/logout',{},cookie)['status'],303)
        self.assertEqual(self.request('/api/state',cookie=cookie)['status'],401)
    def test_invitation_private_records_and_permissions(self):
        admin=self.setup_admin()
        invite=self.request('/api/web/invite',dict(email='member@example.com',role='member'),admin)
        token=invite['body']['url'].split('token=')[1]
        data=dict(email='member@example.com',name='SAMPLE — Member',password='SamplePassword123!',token=token)
        self.assertEqual(self.request('/api/web/join',data)['status'],200)
        self.assertEqual(self.request('/api/web/join',data)['status'],400)
        login=self.request('/api/web/login',dict(email=data['email'],password=data['password']))
        member=next(v.split(';')[0] for k,v in login['headers'] if k=='Set-Cookie')
        self.assertEqual(self.request('/api/web/invite',dict(email='other@example.com'),member)['status'],403)
        self.assertEqual(self.request('/api/settings',{},member)['status'],403)
        self.assertEqual(self.request('/api/record',dict(kind='contacts',body={'name':'SAMPLE — Web contact','email':'contact@example.com','phone':'4165550123','phone_country':'CA','links':[]}),member)['status'],200)
        state=self.request('/api/state',cookie=admin)['body'];self.assertEqual(state['records'][0]['phone'],'+1 416-555-0123')
        self.assertFalse(state['deployment']['background_jobs'])
        users=self.request('/api/web/users',cookie=admin)['body']['users'];self.assertNotIn('password',users[0])
        self.assertEqual(self.request('/api/tools/view',dict(name='Private',kind='contacts',filters={}),member)['status'],200)
        self.assertEqual(self.request('/api/state',cookie=admin)['body']['views'],[])
    def test_brute_force_limit_and_query_parameters(self):
        self.setup_admin()
        for _ in range(10):self.assertEqual(self.request('/api/web/login',dict(email='admin@example.com',password='WrongPassword123'))['status'],400)
        self.assertEqual(self.request('/api/web/login',dict(email='admin@example.com',password='SamplePassword123!'))['status'],400)
        with self.web.server.connect() as db:
            self.assertEqual(db.execute("SELECT '?' AS literal,? AS value",('value',)).fetchone()['literal'],'?')

    def test_migration_preview_and_apply(self):
        import sqlite3,tempfile,importlib.util
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/desktop.db';source=sqlite3.connect(path)
            source.executescript('CREATE TABLE settings(id INTEGER,body TEXT);CREATE TABLE records(id TEXT,kind TEXT,body TEXT,updated TEXT);CREATE TABLE activities(id TEXT,record_id TEXT,body TEXT,created TEXT);')
            with self.web.server.connect() as db:settings=db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]
            source.execute('INSERT INTO settings VALUES (1,?)',(settings,));source.execute('INSERT INTO records VALUES (?,?,?,?)',('sample','contacts',json.dumps(dict(name='SAMPLE — Migration',email='migration@example.com',links=[])),'2026-10-12T00:00:00+00:00'));source.execute('INSERT INTO activities VALUES (?,?,?,?)',('activity','sample',json.dumps(dict(type='Note',text='SAMPLE — History')),'2026-10-12T00:00:00+00:00'));source.commit();source.close()
            spec=importlib.util.spec_from_file_location('migrate',__import__('pathlib').Path(__file__).parent/'deploy/migrate_desktop.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            result=module.migrate(path,os.environ['DATABASE_URL']);self.assertEqual(result,dict(records=1,activities=1))
            with self.web.server.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM records').fetchone())
            module.migrate(path,os.environ['DATABASE_URL'],True)
            with self.web.server.connect() as db:self.assertEqual(db.execute('SELECT body FROM activities').fetchone()[0],json.dumps(dict(type='Note',text='SAMPLE — History')))
            with self.assertRaises(ValueError):module.migrate(path,os.environ['DATABASE_URL'],True)
    def test_background_work_uses_private_owner(self):
        from unittest.mock import patch
        self.setup_admin()
        with patch.object(self.web.server.MAIL,'auto_tick') as mail,patch.object(self.web.server.automation,'inactive') as rules:
            self.web.background_tick();self.assertEqual(mail.call_count,1);self.assertEqual(rules.call_count,1)
            self.assertEqual(json.loads(mail.call_args[0][0])[0],'sprocket-web')

    def test_calendar_job_is_opt_in_and_owner_scoped(self):
        from unittest.mock import patch
        admin=self.setup_admin()
        user=self.request('/api/auth',cookie=admin)['body']['user'];owner=json.dumps([self.web.accounts.issuer,user['subject']])
        with self.web.server.connect() as db:db.execute('INSERT INTO calendar_accounts VALUES (?,?,?,?)',('calendar',owner,'admin@example.com','sample-encrypted-token'))
        data=dict(account_id='calendar',start='2026-10-01',end='2026-10-31',enabled=True)
        self.assertEqual(self.request('/api/web/calendar-auto',data,admin)['status'],200)
        with patch.object(self.web.server.CALENDAR,'sync',return_value={'next_page':''}) as sync,patch.object(self.web.server.MAIL,'auto_tick'),patch.object(self.web.server.automation,'inactive'):
            self.web.background_tick();self.assertEqual(sync.call_count,1)
            self.web.background_tick();self.assertEqual(sync.call_count,1)
        self.assertEqual(self.request('/api/web/calendar-auto',dict(data,enabled=False),admin)['status'],200)
        self.assertEqual(self.request('/api/web/calendar-auto',dict(data,account_id='other'),admin)['status'],400)
    def test_provider_secret_not_returned_and_persists(self):
        import tempfile
        admin=self.setup_admin()
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'SPROCKET_WEB_PROVIDER_CONFIG':folder+'/google.json','GOOGLE_MAIL_CLIENT_ID':'','GOOGLE_MAIL_CLIENT_SECRET':''}):
            client='sample-client.apps.googleusercontent.com';secret='sample-provider-secret'
            self.assertEqual(self.request('/api/web/provider',dict(client_id=client,client_secret=secret),admin)['status'],200)
            result=self.request('/api/web/provider',cookie=admin)['body'];self.assertEqual(result['client_id'],client);self.assertTrue(result['secret_configured']);self.assertNotIn(secret,json.dumps(result))
            from pathlib import Path
            with self.web.server.connect() as db:encrypted=db.execute('SELECT body FROM web_provider_config WHERE id=1').fetchone()[0]
            self.assertNotIn(secret,encrypted)
            self.assertFalse(Path(folder+'/google.json').exists())
            os.environ['GOOGLE_MAIL_CLIENT_SECRET']='';self.web.web_provider.apply();self.assertEqual(os.environ['GOOGLE_MAIL_CLIENT_SECRET'],secret)

    def test_infrastructure_health_and_render_origin(self):
        self.assertEqual(self.request('/health',host='internal-health-probe')['status'],200)
        self.assertEqual(self.request('/api/state',host='internal-health-probe')['status'],400)
        admin=self.setup_admin()
        self.assertFalse(self.request('/api/state',cookie=admin)['body']['deployment']['background_jobs'])
    def test_database_provider_configuration_survives_new_connection(self):
        admin=self.setup_admin()
        with patch.dict(os.environ,{'GOOGLE_MAIL_CLIENT_ID':'','GOOGLE_MAIL_CLIENT_SECRET':''}):
            self.assertEqual(self.request('/api/web/provider',dict(client_id='render-test.apps.googleusercontent.com',client_secret='sample-render-secret'),admin)['status'],200)
            os.environ['GOOGLE_MAIL_CLIENT_ID']='';os.environ['GOOGLE_MAIL_CLIENT_SECRET']=''
            self.web.web_provider.apply()
            self.assertEqual(os.environ['GOOGLE_MAIL_CLIENT_SECRET'],'sample-render-secret')
