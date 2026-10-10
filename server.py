"""Sprocket CRM local development server. Python 3.9+, no dependencies."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DB = Path(os.environ.get('SPROCKET_DB', str(ROOT / 'data' / 'sprocket.db')))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activities (id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE, body TEXT NOT NULL, created TEXT NOT NULL);
        ''')
        if not db.execute('SELECT 1 FROM settings').fetchone():
            kinds = [
                ('contacts', 'Contacts', [{'key': 'email', 'label': 'Email', 'type': 'email'}, {'key': 'phone', 'label': 'Phone', 'type': 'text'}]),
                ('companies', 'Companies', [{'key': 'domain', 'label': 'Website', 'type': 'text'}]),
                ('deals', 'Deals', [{'key': 'amount', 'label': 'Amount', 'type': 'number'}, {'key': 'close_date', 'label': 'Close date', 'type': 'date'}]),
                ('tasks', 'Tasks', [{'key': 'due_date', 'label': 'Due date', 'type': 'date'}, {'key': 'priority', 'label': 'Priority', 'type': 'select', 'options': ['Low', 'Medium', 'High']}]),
                ('tickets', 'Tickets', [{'key': 'priority', 'label': 'Priority', 'type': 'select', 'options': ['Low', 'Medium', 'High', 'Urgent']}])]
            settings = {'name': 'Sprocket CRM', 'currency': 'USD', 'types': [{'id': k, 'name': n, 'fields': f} for k, n, f in kinds], 'pipelines': [], 'owners': []}
            db.execute('INSERT INTO settings VALUES (1, ?)', (json.dumps(settings),))


def load_settings(db):
    return json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])


def validate_settings(data, previous, records):
    if not isinstance(data, dict) or not isinstance(data.get('types'), list) or not data['types']:
        raise ValueError('At least one record type is required.')
    if not isinstance(data.get('pipelines'), list) or not isinstance(data.get('owners'), list):
        raise ValueError('Pipelines and owners must be lists.')
    if len(str(data.get('currency', ''))) != 3 or not str(data['currency']).isascii() or not str(data['currency']).isalpha():
        raise ValueError('Use a three-letter currency code.')
    ids = set()
    for typ in data['types']:
        ident = typ.get('id', '')
        if not ident or not ident.replace('_', '').isalnum() or ident in ids or not typ.get('name'):
            raise ValueError('Record types need unique IDs and names.')
        ids.add(ident)
        keys = set()
        for field in typ.get('fields', []):
            key = field.get('key', '')
            if key in ('name', 'owner', 'pipeline', 'stage', 'notes', 'links') or not key or not key.replace('_', '').isalnum() or key in keys:
                raise ValueError('Custom field keys must be unique and cannot use reserved keys.')
            keys.add(key)
            if field.get('type') not in ('text', 'email', 'number', 'date', 'checkbox', 'select') or not field.get('label'):
                raise ValueError('Invalid custom field definition.')
            if field['type'] == 'select' and (not isinstance(field.get('options'), list) or not field['options']):
                raise ValueError('Select fields need options.')
    pipe_ids = set()
    for pipe in data['pipelines']:
        if not pipe.get('id') or pipe['id'] in pipe_ids or pipe.get('kind') not in ids or not pipe.get('name') or not pipe.get('stages'):
            raise ValueError('Pipelines need a unique ID, name, record type and stages.')
        pipe_ids.add(pipe['id'])
        stage_ids = set()
        for stage in pipe['stages']:
            if not stage.get('id') or stage['id'] in stage_ids or not stage.get('name') or not 0 <= float(stage.get('probability', 0)) <= 1:
                raise ValueError('Stages need unique IDs, names and probabilities from 0 to 1.')
            stage_ids.add(stage['id'])
    # Prevent configuration changes that would strand existing records.
    for row in records:
        if row['kind'] not in ids:
            raise ValueError('Cannot remove a record type while it contains records.')
        record = json.loads(row['body'])
        if record.get('pipeline'):
            pipe = next((p for p in data['pipelines'] if p['id'] == record['pipeline'] and p['kind'] == row['kind']), None)
            if not pipe or record.get('stage') not in {s['id'] for s in pipe['stages']}:
                raise ValueError('Move records before removing their pipeline or stage.')


def validate_record(db, kind, body):
    settings = load_settings(db)
    typ = next((t for t in settings['types'] if t['id'] == kind), None)
    if not typ or not isinstance(body, dict) or not str(body.get('name', '')).strip():
        raise ValueError('A valid record type and name are required.')
    body['name'] = str(body['name']).strip()
    if body.get('pipeline'):
        pipe = next((p for p in settings['pipelines'] if p['id'] == body['pipeline'] and p['kind'] == kind), None)
        if not pipe or body.get('stage') not in {s['id'] for s in pipe['stages']}:
            raise ValueError('Select a valid pipeline and stage.')
    elif body.get('stage'):
        raise ValueError('A stage requires a pipeline.')
    for field in typ['fields']:
        value = body.get(field['key'])
        if value in (None, ''):
            continue
        if field['type'] == 'number' and (isinstance(value, bool) or not isinstance(value, (float, int))):
            raise ValueError(field['label'] + ' must be a number.')
        if field['type'] == 'select' and value not in field['options']:
            raise ValueError('Invalid option for ' + field['label'])
        if field['type'] == 'date':
            datetime.strptime(value, '%Y-%m-%d')
    links = body.get('links', [])
    if not isinstance(links, list):
        raise ValueError('Relationships must be a list.')
    for link in links:
        if not db.execute('SELECT 1 FROM records WHERE id=?', (link,)).fetchone():
            raise ValueError('Related record does not exist.')


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/state':
            with connect() as db:
                records = [dict(json.loads(r['body']), id=r['id'], kind=r['kind'], updated=r['updated']) for r in db.execute('SELECT * FROM records ORDER BY updated DESC')]
                activities = [dict(json.loads(r['body']), id=r['id'], record_id=r['record_id'], created=r['created']) for r in db.execute('SELECT * FROM activities ORDER BY created DESC')]
                return self.reply(200, {'settings': load_settings(db), 'records': records, 'activities': activities})
        file = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}.get(path)
        if not file:
            return self.reply(404, {'error': 'Not found'})
        raw = (ROOT / 'web' / file).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[file.split('.')[-1]])
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        # Only same-origin JSON requests can write. No CORS or cross-site form writes.
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'JSON required'})
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, {'error': 'Invalid origin'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 1000000:
                raise ValueError('Request size must be between 1 byte and 1 MB.')
            data = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            now = datetime.now(timezone.utc).isoformat()
            with connect() as db:
                if path == '/api/settings':
                    validate_settings(data, load_settings(db), db.execute('SELECT * FROM records').fetchall())
                    db.execute('UPDATE settings SET body=? WHERE id=1', (json.dumps(data),))
                elif path == '/api/record':
                    body = data['body']
                    validate_record(db, data['kind'], body)
                    ident = data.get('id') or str(uuid.uuid4())
                    old = db.execute('SELECT kind FROM records WHERE id=?', (ident,)).fetchone()
                    if old and old['kind'] != data['kind']:
                        raise ValueError('Record type cannot be changed.')
                    db.execute('INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body, updated=excluded.updated', (ident, data['kind'], json.dumps(body), now))
                elif path == '/api/delete':
                    db.execute('DELETE FROM records WHERE id=?', (data['id'],))
                    for row in db.execute('SELECT * FROM records').fetchall():
                        body = json.loads(row['body'])
                        if data['id'] in body.get('links', []):
                            body['links'].remove(data['id'])
                            db.execute('UPDATE records SET body=? WHERE id=?', (json.dumps(body), row['id']))
                elif path == '/api/activity':
                    if not str(data.get('text', '')).strip() or data.get('type') not in ('Note', 'Call', 'Email', 'Meeting'):
                        raise ValueError('An activity type and text are required.')
                    db.execute('INSERT INTO activities VALUES (?,?,?,?)', (str(uuid.uuid4()), data['record_id'], json.dumps({'type': data['type'], 'text': data['text']}), now))
                else:
                    return self.reply(404, {'error': 'Not found'})
            self.reply(200, {'ok': True})
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', '8765'))
    print('Sprocket CRM: http://127.0.0.1:' + str(port), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
