"""Single-use browser handoffs for the desktop launcher; disabled in web installs."""
import hmac
import os
import secrets
import threading
import time

class DesktopBridge:
    def __init__(self):
        self.token = os.getenv('SPROCKET_DESKTOP_TOKEN', '')
        self.items = {}
        self.lock = threading.Lock()

    def trusted(self, headers):
        return bool(self.token) and hmac.compare_digest(self.token, headers.get('X-SpRocket-Desktop', ''))

    def create(self, **data):
        with self.lock:
            self.items = {k:v for k,v in self.items.items() if v['expires'] > time.time()}
            if len(self.items) >= 100:
                raise ValueError('Too many pending desktop sign-ins.')
            ticket = secrets.token_urlsafe(32)
            self.items[ticket] = dict(data, expires=time.time()+600)
            return ticket

    def consume_start(self, ticket):
        with self.lock:
            item = self.items.get(ticket)
            if not item or item['expires'] <= time.time() or item.get('started'):
                raise ValueError('Expired desktop handoff.')
            item['started'] = True
            return dict(item)

    def complete(self, ticket, cookie):
        with self.lock:
            item = self.items.get(ticket)
            if item and item['expires'] > time.time():
                item['cookie'] = cookie

    def result(self, ticket):
        with self.lock:
            item = self.items.get(ticket)
            if not item or item['expires'] <= time.time():
                return {'expired': True}
            if 'cookie' not in item:
                return {'pending': True}
            self.items.pop(ticket)
            return {'cookie': item['cookie']}
