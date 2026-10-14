"""Sprocket CRM local development server. Python 3.9+, no dependencies."""
import json
import math
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from auth import OIDC
from desktop_bridge import DesktopBridge
import sso_config
import record_forms
import navigation_preferences
import dashboard_preferences
import crm_tools
import workspace_tools
import phone_numbers
import enrichment
from enrichment_service import EnrichmentService, linkedin_url
import automation
import followups
import notifications
from app_version import release_info
from updates import Updates
from calendar_service import CalendarService
from recovery import Recovery
from mail_service import MailService, MailError

AUTH = OIDC()
DESKTOP = DesktopBridge()

ROOT = Path(__file__).parent
DB = Path(os.environ.get('SPROCKET_DB', str(ROOT / 'data' / 'sprocket.db')))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


MAIL = MailService(connect)
ENRICHMENT = EnrichmentService(lambda:connect(), MAIL.cipher)
CALENDAR = CalendarService(connect)
RECOVERY = Recovery(connect,lambda:DB)

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activities (id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE, body TEXT NOT NULL, created TEXT NOT NULL);
        ''')
        MAIL.initialize(db)
        navigation_preferences.initialize(db)
        dashboard_preferences.initialize(db)
        crm_tools.initialize(db)
        workspace_tools.initialize(db)
        CALENDAR.initialize(db)
        enrichment.initialize(db)
        ENRICHMENT.initialize(db)
        automation.initialize(db)
        followups.initialize(db)
        notifications.initialize(db)
        if not db.execute('SELECT 1 FROM settings').fetchone():
            kinds = [
                ('contacts', 'Contacts', [{'key': 'email', 'label': 'Email', 'type': 'email'}, {'key': 'phone', 'label': 'Phone', 'type': 'text'}]),
                ('companies', 'Companies', [{'key': 'domain', 'label': 'Website', 'type': 'text'}]),
                ('deals', 'Deals', [{'key': 'amount', 'label': 'Amount', 'type': 'number'}, {'key': 'close_date', 'label': 'Close date', 'type': 'date'}]),
                ('tasks', 'Tasks', [{'key': 'due_date', 'label': 'Due date', 'type': 'date'}, {'key': 'priority', 'label': 'Priority', 'type': 'select', 'options': ['Low', 'Medium', 'High']}]),
                ('tickets', 'Tickets', [{'key': 'priority', 'label': 'Priority', 'type': 'select', 'options': ['Low', 'Medium', 'High', 'Urgent']}])]
            settings = {'name': 'Sprocket CRM', 'currency': 'USD', 'types': [{'id': k, 'name': n, 'fields': f} for k, n, f in kinds], 'pipelines': [{'id': 'sales-pipeline', 'name': 'Sales Pipeline', 'kind': 'deals', 'stages': [{'id': ident, 'name': name, 'probability': probability} for ident, name, probability in [('lead', 'Lead', 0.10), ('demo-booked', 'Demo Booked', 0.20), ('demo-completed', 'Demo Completed', 0.40), ('proposal-sent', 'Proposal Sent', 0.65), ('closed-won', 'Closed Won', 1.0), ('closed-lost', 'Closed Lost', 0.0)]]}], 'owners': []}
            db.execute('INSERT INTO settings VALUES (1, ?)', (json.dumps(settings),))
        settings = load_settings(db)
        if record_forms.upgrade(settings):
            db.execute('UPDATE settings SET body=? WHERE id=1', (json.dumps(settings),))


def load_settings(db):
    return json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])


def validate_settings(data, previous, records):
    if not isinstance(data, dict) or not isinstance(data.get('types'), list) or not data['types']:
        raise ValueError('At least one record type is required.')
    if not isinstance(data.get('pipelines'), list) or not isinstance(data.get('owners'), list):
        raise ValueError('Pipelines and owners must be lists.')
    if len(str(data.get('currency', ''))) != 3 or not str(data['currency']).isascii() or not str(data['currency']).isalpha():
        raise ValueError('Use a three-letter currency code.')
    phone_numbers.country(data.get('phone_country'))
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
    if isinstance(body,dict) and kind in ('contacts','companies') and body.get('linkedin_url'):
        body['linkedin_url']=linkedin_url(body['linkedin_url'],kind)
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
    phone_numbers.normalize_fields(body,[f['key'] for f in typ['fields'] if f['key'] in ('phone','mobile_phone','mobile_number')],phone_numbers.country(settings.get('phone_country')))
    if kind == 'deals' and 'line_items' in body:
        items = body['line_items']
        if not isinstance(items, list) or len(items)>100:
            raise ValueError('Use up to 100 deal line items.')
        for item in items:
            if not isinstance(item, dict) or not str(item.get('description','')).strip():
                raise ValueError('Line items require a description.')
            for key in ('quantity','unit_price'):
                value = item.get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key=='quantity' and value==0):
                    raise ValueError('Line item quantity must be positive and unit price cannot be negative.')
    links = body.get('links', [])
    if not isinstance(links, list):
        raise ValueError('Relationships must be a list.')
    for link in links:
        if not db.execute('SELECT 1 FROM records WHERE id=?', (link,)).fetchone():
            raise ValueError('Related record does not exist.')


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, cookies=()):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        for cookie in cookies:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def redirect(self, location, cookies=()):
        self.send_response(303)
        self.send_header('Location', location)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        for cookie in cookies:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, fmt, *args):
        # Callback URLs contain authorization codes; never log request URLs.
        pass

    def sso_admin(self):
        if not AUTH.enabled:
            return True  # Unconfigured loopback demo: local operator setup.
        user = AUTH.user(self.headers)
        admins = {x.strip() for x in os.getenv('OIDC_ADMIN_SUBJECTS', '').split(',') if x.strip()}
        return bool(user and user['subject'] in admins)

    def mail_owner(self):
        user = AUTH.user(self.headers) if AUTH.enabled else None
        if AUTH.enabled and not user:
            raise MailError('Sign in again before connecting email.')
        return json.dumps([AUTH.issuer, user['subject']]) if user else 'local-operator'

    def tracking_pixel(self,head=False):
        from mail_tracking import PIXEL
        token=urlparse(self.path).path.removeprefix('/email-open/').removesuffix('.gif') if hasattr(str,'removeprefix') else urlparse(self.path).path[len('/email-open/'):-4]
        if not head:
            try:MAIL.tracking.hit(token)
            except Exception:pass # Return the same image even if storage is temporarily unavailable.
        self.send_response(200);self.send_header('Content-Type','image/gif');self.send_header('Content-Length',str(len(PIXEL)));self.send_header('Cache-Control','no-store, max-age=0');self.send_header('Referrer-Policy','no-referrer');self.end_headers()
        if not head:self.wfile.write(PIXEL)

    def do_HEAD(self):
        if urlparse(self.path).path.startswith('/email-open/'):return self.tracking_pixel(True)
        self.send_error(405)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/email-open/'):return self.tracking_pixel()
        if path == '/api/desktop/health':
            if not DESKTOP.trusted(self.headers):
                return self.reply(403, {'error': 'Desktop access required'})
            return self.reply(200, {'ready': True})
        if path == '/api/desktop/login':
            if not DESKTOP.trusted(self.headers) or not AUTH.enabled:
                return self.reply(403, {'error': 'Desktop access required'})
            ticket = DESKTOP.create(kind='login')
            return self.reply(200, {'ticket': ticket})
        if path == '/api/desktop/result':
            if not DESKTOP.trusted(self.headers):
                return self.reply(403, {'error': 'Desktop access required'})
            return self.reply(200, DESKTOP.result(parse_qs(urlparse(self.path).query).get('ticket', [''])[0]))
        if path == '/desktop/start' and DESKTOP.token:
            try:
                ticket = parse_qs(urlparse(self.path).query).get('ticket', [''])[0]
                item = DESKTOP.consume_start(ticket)
                if item['kind'] == 'login':
                    location, cookie = AUTH.begin()
                    state = parse_qs(urlparse(location).query)['state'][0]
                    with AUTH.lock:
                        AUTH.pending[state]['desktop_ticket'] = ticket
                    return self.redirect(location, [cookie])
                return self.redirect(item['location'], item['cookies'])
            except Exception:
                return self.reply(400, {'error': 'Sign-in expired. Start again from the desktop app.'})
        if path == '/desktop/done' and DESKTOP.token:
            return self.reply(200, {'message': 'Sign-in complete. Return to SpRocket CRM.'})
        if path == '/api/auth':
            user = AUTH.user(self.headers) if AUTH.enabled else None
            profile = MAIL.profile(self.mail_owner()) if user or not AUTH.enabled else None
            return self.reply(200, {'enabled': AUTH.enabled, 'user': user, 'profile': profile, 'is_admin': self.sso_admin()})
        if path == '/auth/login' and AUTH.enabled:
            try:
                location, cookie = AUTH.begin()
                return self.redirect(location, [cookie])
            except Exception:
                return self.reply(503, {'error': 'Sign-in is unavailable. Check provider configuration.'})
        if path == '/auth/callback' and AUTH.enabled:
            try:
                query = parse_qs(urlparse(self.path).query)
                with AUTH.lock:
                    ticket = AUTH.pending.get(query.get('state', [''])[0], {}).get('desktop_ticket')
                cookie = AUTH.finish(query, self.headers)
                if ticket:
                    DESKTOP.complete(ticket, cookie)
                    return self.redirect('/desktop/done', [cookie, AUTH.cookie('sprocket_login', '', 0)])
                return self.redirect('/', [cookie, AUTH.cookie('sprocket_login', '', 0)])
            except Exception:
                return self.reply(401, {'error': 'Sign-in failed or this identity is not allowed. Start a new login.'})
        if path == '/calendar/callback/google':
            try:
                CALENDAR.finish('google',self.mail_owner(),parse_qs(urlparse(self.path).query),self.headers)
                return self.redirect('/?calendar=connected',['sprocket_calendar=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'])
            except (MailError,ValueError,KeyError,TypeError):
                return self.redirect('/?calendar=failed',['sprocket_calendar=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'])
        if path.startswith('/mail/callback/'):

            try:
                MAIL.finish(path.split('/')[-1], self.mail_owner(), parse_qs(urlparse(self.path).query), self.headers)
                return self.redirect('/?mail=connected', ['sprocket_mail=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'])
            except (MailError, KeyError, TypeError, ValueError):
                return self.redirect('/?mail=failed', ['sprocket_mail=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'])
        if AUTH.enabled and not AUTH.user(self.headers) and path not in ('/login', '/style.css', '/login.js') and not path.startswith('/assets/brand/'):
            if path.startswith('/api/'):
                return self.reply(401, {'error': 'Sign-in required'})
            return self.redirect('/login')
        if path=='/api/notifications':
            try:
                owner=self.mail_owner();profile=MAIL.profile(owner);identity=AUTH.user(self.headers) if AUTH.enabled else {}
                with connect() as db:
                    aliases=[profile.get('name'),(identity or {}).get('name'),(identity or {}).get('email'),'Local operator' if owner=='local-operator' else owner]+[r[0] for r in db.execute('SELECT email FROM mail_accounts WHERE owner=?',(owner,))]
                    offset=int(parse_qs(urlparse(self.path).query).get('offset',['0'])[0])
                    return self.reply(200,notifications.feed(db,owner,aliases,offset))
            except (ValueError,TypeError) as error:return self.reply(400,{'error':str(error)})
        if path=='/api/templates':
            with connect() as db:return self.reply(200,followups.templates(db,self.mail_owner(),self.sso_admin()))
        if path=='/api/tracking/opens':return self.reply(200,MAIL.tracking.visible_opens(self.mail_owner()))
        if path=='/api/tracking':return self.reply(200,MAIL.tracking.status(self.mail_owner(),self.sso_admin()))
        if path in ('/api/enrichment/status','/api/enrichment/history'):
            try:
                result=ENRICHMENT.status(self.sso_admin()) if path.endswith('/status') else ENRICHMENT.history(self.mail_owner(),parse_qs(urlparse(self.path).query).get('record_id',[''])[0],self.sso_admin())
                return self.reply(200,result)
            except ValueError as error:return self.reply(400,{'error':str(error)})
        if path=='/api/calendar':
            return self.reply(200,CALENDAR.status(self.mail_owner()))
        if path=='/api/automation':
            with connect() as db:return self.reply(200,automation.status(db))
        if path in ('/api/cleanup','/api/reminders'):

            with connect() as db:
                return self.reply(200,crm_tools.review(db) if path=='/api/cleanup' else crm_tools.reminders(db,self.mail_owner()))
        if path in ('/api/mail', '/api/mail/messages'):
            try:
                owner = self.mail_owner()
                if path == '/api/mail':
                    return self.reply(200, MAIL.status(owner))
                ident = parse_qs(urlparse(self.path).query).get('account_id', [''])[0]
                return self.reply(200, {'messages': MAIL.messages(owner, ident)})
            except MailError as error:
                return self.reply(400, {'error': str(error)})
        if path == '/api/sso':
            if not self.sso_admin():
                return self.reply(403, {'error': 'SSO configuration requires an administrator subject configured on the server.'})
            return self.reply(200, {'config': sso_config.effective(), 'enabled': AUTH.enabled, 'secret_configured': bool(os.getenv('OIDC_CLIENT_SECRET')), 'overrides': [k for k,env in sso_config.FIELDS.items() if env in os.environ]})
        if path == '/api/updates':
            if not self.sso_admin():return self.reply(403, {'error':'Administrator access required.'})
            updater=Updates(connect);updater.initialize();return self.reply(200,updater.status())
        if path == '/api/state':
            with connect() as db:
                records = [dict(json.loads(r['body']), id=r['id'], kind=r['kind'], updated=r['updated']) for r in db.execute('SELECT * FROM records ORDER BY updated DESC')]
                activities = [dict(json.loads(r['body']), id=r['id'], record_id=r['record_id'], created=r['created']) for r in db.execute('SELECT * FROM activities ORDER BY created DESC')]
                MAIL.tracking.decorate(db,activities)
                return self.reply(200, {'release': release_info(), 'settings': load_settings(db), 'records': records, 'activities': activities, 'navigation': navigation_preferences.load(db,self.mail_owner(),load_settings(db)), 'dashboard': dashboard_preferences.load(db,self.mail_owner()), 'views': workspace_tools.views(db,self.mail_owner())['views'], 'phone': {'countries':phone_numbers.countries()}})
        file = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/login': 'login.html', '/login.js': 'login.js', '/mail.js': 'mail.js', '/create.js': 'create.js', '/productivity.js': 'productivity.js', '/workspace.js':'workspace.js', '/features.js':'features.js', '/phone.js':'phone.js', '/updates.js':'updates.js', '/dashboard.js':'dashboard.js', '/navigation.js':'navigation.js', '/enrichment.js':'enrichment.js', '/tracking.js':'tracking.js', '/followups.js':'followups.js', '/notifications.js':'notifications.js'}.get(path)
        if path.startswith('/assets/brand/'):
            candidate = (ROOT / 'web' / path.lstrip('/')).resolve()
            asset_root = (ROOT / 'web/assets/brand').resolve()
            if asset_root in candidate.parents and candidate.is_file() and candidate.suffix in ('.svg', '.png'):
                file = str(candidate.relative_to(ROOT / 'web'))
        if not file:
            return self.reply(404, {'error': 'Not found'})
        raw = (ROOT / 'web' / file).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'svg': 'image/svg+xml', 'png': 'image/png'}[file.split('.')[-1]])
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        # Only same-origin JSON requests can write. No CORS or cross-site form writes.
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'JSON required'})
        origin = self.headers.get('Origin')
        if origin and origin != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host', '')):
            return self.reply(403, {'error': 'Invalid origin'})
        if AUTH.enabled:
            if self.headers.get('Origin') != AUTH.origin:
                return self.reply(403, {'error': 'Invalid origin'})
            if not AUTH.user(self.headers):
                return self.reply(401, {'error': 'Sign-in required'})
            if urlparse(self.path).path == '/auth/logout':
                return self.redirect('/login', [AUTH.logout(self.headers)])
        if urlparse(self.path).path=='/api/updates/check':
            if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
            if origin != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host', '')):return self.reply(403,{'error':'Invalid origin'})
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=1000:raise ValueError('Invalid request.')
                data=json.loads(self.rfile.read(length));updater=Updates(connect);updater.initialize()
                return self.reply(200,updater.check(data['channel']))
            except (ValueError,KeyError,TypeError):return self.reply(400,{'error':'Choose a valid update channel.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            limit=33000000 if urlparse(self.path).path=='/api/backup/preview' and self.sso_admin() else 1000000
            if not 0 < length <= limit:
                raise ValueError('Request size must be between 1 byte and 1 MB.')
            data = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            now = datetime.now(timezone.utc).isoformat()
            if path=='/api/navigation/preferences':
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):
                    return self.reply(403,{'error':'Same-origin browser request required.'})
                with connect() as db:
                    return self.reply(200,navigation_preferences.save(db,self.mail_owner(),load_settings(db),data))
            if path=='/api/dashboard/preferences':
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):
                    return self.reply(403,{'error':'Same-origin browser request required.'})
                with connect() as db:
                    return self.reply(200,dashboard_preferences.save(db,self.mail_owner(),data))
            if path=='/api/notifications':
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):return self.reply(403,{'error':'Same-origin browser request required.'})
                with connect() as db:return self.reply(200,notifications.save(db,self.mail_owner(),data))
            if path=='/api/phone':
                if not isinstance(data,dict):raise ValueError('Phone request must be an object.')
                return self.reply(200,phone_numbers.format_phone(data.get('value',''),data.get('country') or phone_numbers.DEFAULT_COUNTRY,data.get('typing') is True))
            if path in ('/api/followups/create','/api/followups/reschedule','/api/templates/save','/api/templates/render'):
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):return self.reply(403,{'error':'Same-origin browser request required.'})
                if not isinstance(data,dict):raise ValueError('Invalid request.')
                owner=self.mail_owner();user=AUTH.user(self.headers) if AUTH.enabled else {}
                actor=MAIL.profile(owner).get('name') or (user or {}).get('name') or 'Local operator'
                with connect() as db:
                    if path.endswith('/create'):result=followups.schedule(db,owner,actor,data,validate_record,MAIL)
                    elif path.endswith('/reschedule'):result=followups.reschedule(db,data,validate_record)
                    elif path.endswith('/save'):result=followups.save_template(db,owner,data,self.sso_admin(),__import__('mail_service').safe_email_html)
                    else:result=followups.render_template(db,owner,actor,data,__import__('mail_service').safe_email_html)
                return self.reply(200,result)
            if path.startswith('/api/tracking/'):
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):return self.reply(403,{'error':'Same-origin browser request required.'})
                if not isinstance(data,dict):raise ValueError('Invalid tracking request.')
                if path=='/api/tracking/configure':
                    if not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
                    result=MAIL.tracking.configure(data)
                elif path=='/api/tracking/preference':result=MAIL.tracking.preference(self.mail_owner(),data)
                else:raise ValueError('Unknown tracking action.')
                return self.reply(200,result)
            if path.startswith(('/api/calendar/','/api/backup/','/api/automation/','/api/enrichment/')):
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host','')):
                    return self.reply(403,{'error':'Same-origin browser request required.'})
                if not isinstance(data,dict):raise ValueError('Request must be an object.')
                if path.startswith(('/api/backup/','/api/automation/')) and not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
                owner=self.mail_owner();action=path.rsplit('/',1)[-1]
                if path.startswith('/api/calendar/'):
                    if action=='connect':
                        location,cookie=CALENDAR.begin('google',owner)
                        if DESKTOP.trusted(self.headers):
                            cookies=[cookie];session=AUTH.cookie_value(self.headers,'sprocket_session')
                            if session:cookies.append(AUTH.cookie('sprocket_session',session,600))
                            location='/desktop/start?ticket='+DESKTOP.create(kind='calendar',location=location,cookies=cookies)
                        return self.reply(200,{'url':location},[cookie])
                    handlers={'sync':CALENDAR.sync,'log':CALENDAR.log,'disconnect':CALENDAR.disconnect}
                    if action not in handlers:raise ValueError('Unknown calendar action.')
                    return self.reply(200,handlers[action](owner,data))
                if path.startswith('/api/backup/'):
                    if action=='download':result=RECOVERY.download()
                    elif action=='preview':result=RECOVERY.preview(owner,data,validate_settings,validate_record)
                    elif action=='restore':
                        with MAIL.lock,CALENDAR.lock:
                            result=RECOVERY.apply(owner,data);MAIL.imports.clear();CALENDAR.imports.clear()
                    else:raise ValueError('Unknown backup action.')
                    return self.reply(200,result)
                if path.startswith('/api/enrichment/') and action not in ('preview','apply'):
                    if action in ('configure','verify') and not self.sso_admin():return self.reply(403,{'error':'Administrator access required.'})
                    actor=MAIL.profile(owner).get('name') or 'Workspace user'
                    if action=='configure':result=ENRICHMENT.configure(data)
                    elif action=='verify':result=ENRICHMENT.verify()
                    elif action=='lookup':result=ENRICHMENT.lookup(owner,data,validate_record)
                    elif action=='csv-preview':result=ENRICHMENT.csv_preview(owner,data,validate_record)
                    elif action=='commit':result=ENRICHMENT.apply(owner,actor,data,validate_record)
                    elif action=='undo':result=ENRICHMENT.undo(owner,actor,data,validate_record,self.sso_admin())
                    else:raise ValueError('Unknown enrichment action.')
                    return self.reply(200,result)
                with connect() as db:
                    if path.startswith('/api/enrichment/'):
                        if action=='preview':result=enrichment.preview(db,owner,data)
                        elif action=='apply':result=enrichment.apply(db,owner,data,validate_record)
                        else:raise ValueError('Unknown enrichment action.')
                    elif action=='save':result=automation.save(db,data)
                    elif action in ('run','preview'):result=automation.inactive(db,validate_record,preview=action=='preview')
                    else:raise ValueError('Unknown automation action.')
                return self.reply(200,result)
            if path == '/api/profile':
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host', '')):
                    return self.reply(403, {'error': 'Same-origin browser request required.'})
                if not isinstance(data,dict):raise MailError('Profile must be an object.')
                return self.reply(200, MAIL.save_profile(self.mail_owner(),data))
            if path.startswith('/api/mail/'):
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host', '')):
                    return self.reply(403, {'error': 'Same-origin browser request required.'})
                if not isinstance(data, dict):
                    raise MailError('Email request must be an object.')
                action = path.rsplit('/', 1)[-1]
                owner = self.mail_owner()
                if action == 'connect':
                    location, cookie = MAIL.begin(data.get('provider'), owner)
                    if DESKTOP.trusted(self.headers):
                        cookies = [cookie]
                        session = AUTH.cookie_value(self.headers, 'sprocket_session')
                        if session:
                            cookies.append(AUTH.cookie('sprocket_session', session, 600))
                        ticket = DESKTOP.create(kind='mail', location=location, cookies=cookies)
                        location = '/desktop/start?ticket=' + ticket
                    return self.reply(200, {'url': location}, [cookie])
                user = AUTH.user(self.headers) if AUTH.enabled else None
                data['_crm_owner'] = user['name'] if user else None
                return self.reply(200, MAIL.post(action, owner, data))

            if path in ('/api/sso', '/api/sso/test'):
                if not self.sso_admin():
                    return self.reply(403, {'error': 'SSO administrator access required.'})
                if self.headers.get('Origin') != (AUTH.origin if AUTH.enabled else 'http://' + self.headers.get('Host', '')):
                    return self.reply(403, {'error': 'Same-origin browser request required.'})
                config = sso_config.validate(data)
                if path == '/api/sso':
                    sso_config.save(config)
                    return self.reply(200, {'ok': True, 'restart_required': True})
                # Discovery only; no credentials are transmitted and no access is enabled.
                try:
                    probe = OIDC.__new__(OIDC)
                    probe.issuer = config['issuer']; probe.metadata = None
                    metadata = probe.discover()
                    if 'RS256' not in metadata.get('id_token_signing_alg_values_supported', []):
                        raise ValueError('Provider must support RS256 ID tokens.')
                    return self.reply(200, {'ok': True, 'message': 'Provider discovery verified. Client credentials and real sign-in still require an integration test.'})
                except Exception:
                    return self.reply(400, {'error': 'Provider discovery failed. Check the issuer, HTTPS connectivity and RS256/client_secret_basic support.'})
            result={'ok':True}
            with connect() as db:
                if path == '/api/tools/view':
                    result=workspace_tools.save_view(db,self.mail_owner(),data)
                elif path == '/api/tools/csv-preview':
                    result=workspace_tools.preview_import(db,self.mail_owner(),data,validate_record)
                elif path == '/api/tools/csv-apply':
                    result=workspace_tools.apply_import(db,self.mail_owner(),data,validate_record)
                elif path == '/api/tools/csv-export':
                    result=workspace_tools.export_csv(db,data)
                elif path == '/api/merge':
                    result=crm_tools.merge(db,data)
                elif path == '/api/task/complete':
                    result=crm_tools.complete_task(db,data)
                elif path == '/api/reminder':
                    result=crm_tools.reminder(db,self.mail_owner(),data)
                elif path == '/api/settings':
                    validate_settings(data, load_settings(db), db.execute('SELECT * FROM records').fetchall())
                    db.execute('UPDATE settings SET body=? WHERE id=1', (json.dumps(data),))
                elif path == '/api/record':
                    body = data['body']
                    validate_record(db, data['kind'], body)
                    ident = data.get('id') or str(uuid.uuid4())
                    old = db.execute('SELECT kind,body FROM records WHERE id=?', (ident,)).fetchone()
                    if old and old['kind'] != data['kind']:
                        raise ValueError('Record type cannot be changed.')
                    db.execute('INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body, updated=excluded.updated', (ident, data['kind'], json.dumps(body), now))
                    if data['kind']=='deals':automation.stage_changed(db,ident,json.loads(old['body']) if old else None,body,now,validate_record)
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
            self.reply(200, result)
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', metavar='DESTINATION')
    args = parser.parse_args()
    initialize()
    if args.backup:
        with connect() as source, sqlite3.connect(args.backup) as target:
            source.backup(target)
        raise SystemExit(0)
    port = int(os.environ.get('PORT', '8765'))
    print('Sprocket CRM: http://127.0.0.1:' + str(port), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
