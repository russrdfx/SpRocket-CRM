"""Exercise new routes against an isolated server; no live account access."""
import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server as app

class FeatureRoutes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=app.DB;app.DB=Path(self.temp.name)/'routes.db';app.initialize();self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();app.DB=self.previous;self.temp.cleanup()
    def request(self,path,data=None,origin=True):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=self.url
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_admin_and_origin_enforced(self):
        self.assertEqual(self.request('/api/backup/download',{},False)[0],403)
        with patch.object(app.Handler,'sso_admin',return_value=False):
            self.assertEqual(self.request('/api/backup/download',{})[0],403);self.assertEqual(self.request('/api/automation/save',{})[0],403)
    def test_backup_routes_round_trip(self):
        code,backup=self.request('/api/backup/download',{});self.assertEqual(code,200)
        code,preview=self.request('/api/backup/preview',backup);self.assertEqual(code,200)
        self.assertEqual(self.request('/api/backup/restore',dict(id=preview['id'],confirm='RESTORE'))[0],200)
    def test_calendar_setup_and_static_scripts(self):
        code,status=self.request('/api/calendar');self.assertEqual(code,200);self.assertEqual(status['accounts'],[])
        for script in ('workspace.js','features.js'):
            with urllib.request.urlopen(self.url+'/'+script) as response:self.assertEqual(response.status,200)
        self.assertEqual(self.request('/api/calendar/log',dict(account_id='other',event_id='event'))[0],400)
    def test_stage_change_route_creates_task(self):
        settings=self.request('/api/state')[1]['settings'];settings['pipelines']=[dict(id='p',kind='deals',name='SAMPLE',stages=[dict(id='a',name='Qualified',probability=.4),dict(id='b',name='Proposal',probability=.7)])];self.assertEqual(self.request('/api/settings',settings)[0],200)
        rule=dict(name='SAMPLE rule',title='Call {deal}',pipeline='p',stage='b',trigger='stage',days=7,due=3,enabled=True);self.assertEqual(self.request('/api/automation/save',rule)[0],200)
        self.assertEqual(self.request('/api/record',dict(id='deal',kind='deals',body=dict(name='SAMPLE deal',pipeline='p',stage='a')))[0],200)
        self.assertEqual(self.request('/api/record',dict(id='deal',kind='deals',body=dict(name='SAMPLE deal',pipeline='p',stage='b')))[0],200)
        records=self.request('/api/state')[1]['records'];self.assertEqual(len([r for r in records if r['kind']=='tasks']),1)
        self.assertEqual(len(self.request('/api/automation')[1]['runs']),1)
    def test_csv_routes_and_saved_view_state(self):
        preview=self.request('/api/tools/csv-preview',dict(kind='contacts',csv='Email,Name\nsample@example.test,SAMPLE person',mapping={'Email':'email','Name':'name'}))[1]
        self.assertEqual(self.request('/api/tools/csv-apply',{'id':preview['id']})[0],200)
        self.assertIn('sample@example.test',self.request('/api/tools/csv-export',{'kind':'contacts'})[1]['csv'])
        self.assertEqual(self.request('/api/tools/view',dict(kind='contacts',name='SAMPLE view',filters={'query':'SAMPLE'}))[0],200)
        self.assertEqual(len(self.request('/api/state')[1]['views']),1)

    def test_provider_permissions_review_and_history(self):
        from enrichment_service import defaults
        self.assertEqual(self.request('/api/enrichment/status')[0],200)
        self.assertEqual(self.request('/api/enrichment/configure',defaults(),False)[0],403)
        with patch.object(app.Handler,'sso_admin',return_value=False):
            self.assertEqual(self.request('/api/enrichment/configure',defaults())[0],403)
            self.assertEqual(self.request('/api/enrichment/verify',{})[0],403)
            self.assertFalse(self.request('/api/enrichment/status')[1]['can_configure'])
        self.assertEqual(self.request('/api/enrichment/lookup',{'id':'c'})[0],400)
        self.assertEqual(self.request('/api/record',dict(id='c',kind='contacts',body=dict(name='SAMPLE',email='sample@example.com')))[0],200)
        code,p=self.request('/api/enrichment/csv-preview',dict(kind='contacts',csv='email,job_title\nsample@example.com,Designer',mapping={'email':'email','job_title':'job_title'}));self.assertEqual(code,200)
        self.assertEqual(self.request('/api/enrichment/commit',dict(selections=[dict(preview_id=p['preview_id'],record_id='c',fields=['job_title'])],match_confirmed=True))[0],200)
        history=self.request('/api/enrichment/history?record_id=c')[1]['history'];self.assertEqual(len(history),1)
        self.assertEqual(self.request('/api/enrichment/undo',dict(id=history[0]['id'],confirmed=True))[0],200)
        with urllib.request.urlopen(self.url+'/enrichment.js') as response:self.assertEqual(response.status,200)
    def test_tracking_routes_require_admin_and_origin(self):
        self.assertEqual(self.request('/api/tracking')[0],200)
        self.assertEqual(self.request('/api/tracking/configure',{'enabled':False},False)[0],403)
        with patch.object(app.Handler,'sso_admin',return_value=False):self.assertEqual(self.request('/api/tracking/configure',{'enabled':False})[0],403)
        with urllib.request.urlopen(urllib.request.Request(self.url+'/email-open/unknown.gif',method='HEAD')) as response:
            self.assertEqual(response.status,200);self.assertEqual(response.read(),b'')
        with urllib.request.urlopen(self.url+'/email-open/unknown.gif') as response:
            from mail_tracking import PIXEL
            self.assertEqual(response.read(),PIXEL);self.assertEqual(response.headers['Content-Type'],'image/gif')
