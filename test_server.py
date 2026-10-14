import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('sprocket', Path(__file__).with_name('server.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class CRMTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.DB = Path(self.temp.name) / 'test.db'
        app.initialize()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()
    def request(self, route, data=None, origin=None):
        headers = {'Content-Type':'application/json'}
        if origin: headers['Origin'] = origin
        req = urllib.request.Request(self.url + route, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    def test_configuration_records_and_references(self):
        state = self.request('/api/state')[1]
        self.assertEqual([], state['records'])
        self.assertEqual('Sales Pipeline', state['settings']['pipelines'][0]['name'])
        settings = state['settings']
        settings['pipelines'] = [{'id':'demo', 'name':'Fictional test process', 'kind':'deals', 'stages':[{'id':'first', 'name':'User-defined stage', 'probability':0.5}]}]
        self.assertEqual(200, self.request('/api/settings', settings)[0])
        self.assertEqual(200, self.request('/api/record', {'kind':'deals','body':{'name':'Fictional example', 'pipeline':'demo','stage':'first','amount':120}})[0])
        row = self.request('/api/state')[1]['records'][0]
        self.assertEqual(400, self.request('/api/record', {'kind':'deals','body':{'name':'Invalid stage', 'pipeline':'demo','stage':'missing'}})[0])
        settings['pipelines'] = []
        self.assertEqual(400, self.request('/api/settings', settings)[0])
        self.assertEqual(200, self.request('/api/activity', {'record_id':row['id'],'type':'Note','text':'Fictional note'})[0])
        self.assertEqual(1, len(self.request('/api/state')[1]['activities']))
        self.assertEqual(200, self.request('/api/delete', {'id':row['id']})[0])
        self.assertEqual([], self.request('/api/state')[1]['activities'])
    def test_cross_origin_write_blocked(self):
        self.assertEqual(403, self.request('/api/record', {'kind':'contacts','body':{'name':'Test'}}, 'https://other.example')[0])
    def test_persistence(self):
        self.request('/api/record', {'kind':'companies','body':{'name':'Fictional example'}})
        app.initialize()
        self.assertEqual('Fictional example', self.request('/api/state')[1]['records'][0]['name'])

if __name__ == '__main__': unittest.main()
