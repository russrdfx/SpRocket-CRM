import unittest
from unittest.mock import patch
from desktop_bridge import DesktopBridge

class DesktopTests(unittest.TestCase):
    def test_disabled_without_launcher_secret(self):
        with patch.dict('os.environ', {}, clear=True):
            bridge = DesktopBridge()
            self.assertFalse(bridge.trusted({'X-SpRocket-Desktop': ''}))

    def test_trust_and_single_use_handoff(self):
        with patch.dict('os.environ', {'SPROCKET_DESKTOP_TOKEN': 'test-secret'}):
            bridge = DesktopBridge()
        self.assertFalse(bridge.trusted({'X-SpRocket-Desktop': 'wrong'}))
        self.assertTrue(bridge.trusted({'X-SpRocket-Desktop': 'test-secret'}))
        ticket = bridge.create(kind='login')
        self.assertEqual(bridge.result(ticket), {'pending': True})
        self.assertEqual(bridge.consume_start(ticket)['kind'], 'login')
        with self.assertRaises(ValueError): bridge.consume_start(ticket)
        bridge.complete(ticket, 'sprocket_session=secret')
        self.assertEqual(bridge.result(ticket), {'cookie': 'sprocket_session=secret'})
        self.assertEqual(bridge.result(ticket), {'expired': True})

    def test_expired_tickets_cannot_release_cookies(self):
        bridge = DesktopBridge()
        ticket = bridge.create(kind='mail')
        bridge.items[ticket]['expires'] = 0
        bridge.complete(ticket, 'secret')
        self.assertEqual(bridge.result(ticket), {'expired': True})
        with self.assertRaises(ValueError): bridge.consume_start(ticket)


class DesktopHTTPTests(unittest.TestCase):
    def test_protected_handoff_and_sso_return(self):
        import server, threading, json, urllib.request, urllib.error
        from http.server import ThreadingHTTPServer
        from unittest.mock import MagicMock
        auth = MagicMock(enabled=True)
        auth.lock = threading.RLock()
        auth.pending = {'state123': {}}
        auth.begin.return_value = ('https://provider.example/authorize?state=state123', 'sprocket_login=binding; Path=/; HttpOnly')
        auth.finish.return_value = 'sprocket_session=verified; Path=/; HttpOnly; Max-Age=600'
        auth.cookie.side_effect = lambda name, value, age: f'{name}={value}; Path=/; Max-Age={age}'
        with patch.dict('os.environ', {'SPROCKET_DESKTOP_TOKEN': 'launcher'}): bridge = DesktopBridge()
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args): return None
        opener = urllib.request.build_opener(NoRedirect)
        with patch.object(server, 'DESKTOP', bridge), patch.object(server, 'AUTH', auth):
            http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
            origin = 'http://127.0.0.1:'+str(http.server_port)
            def get(route): return urllib.request.urlopen(urllib.request.Request(origin+route, headers={'X-SpRocket-Desktop':'launcher'}))
            try:
                self.assertTrue(json.load(get('/api/desktop/health'))['ready'])
                for route in ['/api/desktop/health','/api/desktop/login','/api/desktop/result?ticket=x']:
                    with self.assertRaises(urllib.error.HTTPError) as failed: urllib.request.urlopen(origin+route)
                    self.assertEqual(failed.exception.code,403)
                ticket = json.load(get('/api/desktop/login'))['ticket']
                with self.assertRaises(urllib.error.HTTPError) as start: opener.open(origin+'/desktop/start?ticket='+ticket)
                self.assertEqual(start.exception.code,303)
                self.assertIn('sprocket_login=binding',start.exception.headers['Set-Cookie'])
                self.assertEqual(auth.pending['state123']['desktop_ticket'],ticket)
                with self.assertRaises(urllib.error.HTTPError) as callback: opener.open(origin+'/auth/callback?state=state123&code=code')
                self.assertEqual(callback.exception.headers['Location'],'/desktop/done')
                auth.finish.assert_called_once()
                self.assertEqual(json.load(get('/api/desktop/result?ticket='+ticket))['cookie'],auth.finish.return_value)
                self.assertEqual(json.load(get('/api/desktop/result?ticket='+ticket)),{'expired':True})
            finally: http.shutdown(); http.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
