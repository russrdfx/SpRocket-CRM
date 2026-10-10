"""Personal Google/Microsoft mail adapters, encrypted tokens and bounded manual sync."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import getaddresses
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from auth import OIDC

GOOGLE_SCOPES = 'https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send'
MICROSOFT_SCOPES = 'offline_access https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send'
PROVIDERS = {
    'google': dict(label='Google / Gmail', auth='https://accounts.google.com/o/oauth2/v2/auth', token='https://oauth2.googleapis.com/token', scopes=GOOGLE_SCOPES),
    'microsoft': dict(label='Microsoft 365 / Outlook', auth='https://login.microsoftonline.com/common/oauth2/v2.0/authorize', token='https://login.microsoftonline.com/common/oauth2/v2.0/token', scopes=MICROSOFT_SCOPES),
}

class MailError(ValueError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MailError('Mail provider redirected unexpectedly. No credentials were forwarded.')


def remote(url, data=None, headers=None, method=None):
    """Fixed provider URLs only; never follow redirects carrying credentials."""
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in {'accounts.google.com', 'oauth2.googleapis.com', 'gmail.googleapis.com', 'login.microsoftonline.com', 'graph.microsoft.com'} or u.username:
        raise MailError('Invalid mail provider URL.')
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers or {}, method=method), timeout=15) as response:
            raw = response.read(4000001)
            if len(raw) > 4000000:
                raise MailError('Mail provider response exceeded the size limit.')
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        # Never expose token responses, message bodies or provider URLs in errors.
        if error.code in (401, 403):
            raise MailError('Mail access was denied. Check permissions or reconnect your account.') from None
        if error.code == 429:
            raise MailError('Mail provider is busy. Try again later.') from None
        raise MailError('Mail provider rejected the request. Check setup or reconnect.') from None
    except (URLError, TimeoutError, OSError):
        raise MailError('Mail provider could not be reached. For a send, check Sent mail before retrying.') from None


def addresses(value):
    return [a.lower() for _, a in getaddresses([value]) if a]


def safe_email_html(value):
    """Retain passive email formatting; the browser adds a separate sandbox/CSP."""
    from html import escape
    from html.parser import HTMLParser
    class EmailHTML(HTMLParser):
        allowed = set('div span p br hr h1 h2 h3 h4 h5 h6 b strong i em u s small blockquote pre code ul ol li table tbody thead tfoot tr td th colgroup col a img style center font'.split())
        void = {'br','hr','img','col'}
        def __init__(self):
            super().__init__(convert_charrefs=True); self.output=[]; self.blocked=None; self.instyle=False
        def handle_starttag(self, tag, attrs):
            if self.blocked: return
            if tag in {'script','iframe','object','svg','math','template'}:
                self.blocked=tag; return
            if tag not in self.allowed: return
            if tag=='style':self.instyle=True
            clean=[]
            for key,val in attrs:
                val=val or ''
                if key in {'style','class','width','height','align','valign','bgcolor','color','size','face','colspan','rowspan','cellpadding','cellspacing','border','alt','title'}:
                    clean.append((key,val))
                elif tag=='img' and key=='src' and re.match(r'^data:image/(png|jpeg|gif|webp);base64,',val,re.I):clean.append((key,val))
                elif tag=='a' and key=='href' and urlparse(val).scheme in {'https','http','mailto'}:clean.append((key,val))
            self.output.append('<'+tag+''.join(' '+k+'="'+escape(v,quote=True)+'"' for k,v in clean)+'>')
        def handle_endtag(self, tag):
            if self.blocked:
                if tag==self.blocked:self.blocked=None
                return
            if tag=='style':self.instyle=False
            if tag in self.allowed and tag not in self.void:self.output.append('</'+tag+'>')
        def handle_data(self, data):
            if not self.blocked:self.output.append(data if self.instyle else escape(data))
    parser=EmailHTML();parser.feed(value[:200000]);parser.close();return ''.join(parser.output)


def gmail_message(m):
    headers = {h['name'].lower(): h['value'] for h in m.get('payload', {}).get('headers', [])}
    def plain(part):
        if part.get('filename'):
            return ''
        if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
            raw = part['body']['data']
            return base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)).decode('utf-8', errors='replace')
        return '\n'.join(filter(None, (plain(p) for p in part.get('parts', []))))
    def rich(part):
        if part.get('filename'): return ''
        if part.get('mimeType') == 'text/html' and part.get('body', {}).get('data'):
            raw = part['body']['data']
            return base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)).decode('utf-8', errors='replace')
        return ''.join(rich(p) for p in part.get('parts', []))
    return dict(html=safe_email_html(rich(m.get('payload', {}))),provider_id=m['id'], thread_id=m.get('threadId', ''), subject=headers.get('subject', '(No subject)'), sender=headers.get('from', ''), to=headers.get('to', ''), cc=headers.get('cc', ''), text=(plain(m.get('payload', {})) or m.get('snippet', ''))[:50000], date=datetime.fromtimestamp(int(m.get('internalDate', '0')) / 1000, timezone.utc).isoformat(), message_id=headers.get('message-id', ''), direction='sent' if 'SENT' in m.get('labelIds', []) else 'received')


def microsoft_message(m):
    def fmt(entries):
        return ', '.join(e.get('emailAddress', {}).get('address', '') for e in entries)
    return dict(provider_id=m['id'], thread_id=m.get('conversationId', ''), subject=m.get('subject') or '(No subject)', sender=m.get('from', {}).get('emailAddress', {}).get('address', ''), to=fmt(m.get('toRecipients', [])), cc=fmt(m.get('ccRecipients', [])), text=m.get('body', {}).get('content', m.get('bodyPreview', ''))[:50000], date=m.get('receivedDateTime') or m.get('sentDateTime') or datetime.now(timezone.utc).isoformat(), message_id=m.get('internetMessageId', ''), direction='received')


class MailService:
    def __init__(self, connect):
        self.connect = connect
        self.pending = {}
        self.imports = {}
        self.lock = threading.RLock()

    def initialize(self, db):
        db.executescript('''
        CREATE TABLE IF NOT EXISTS mail_accounts (id TEXT PRIMARY KEY, owner TEXT NOT NULL, provider TEXT NOT NULL, email TEXT NOT NULL, tokens TEXT NOT NULL, signature TEXT NOT NULL DEFAULT '', days INTEGER NOT NULL DEFAULT 30, last_sync TEXT NOT NULL DEFAULT '', UNIQUE(owner,provider,email));
        CREATE TABLE IF NOT EXISTS mail_messages (id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES mail_accounts(id) ON DELETE CASCADE, provider_id TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(account_id,provider_id));
        CREATE TABLE IF NOT EXISTS mail_logs (message_id TEXT NOT NULL REFERENCES mail_messages(id) ON DELETE CASCADE, record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE, PRIMARY KEY(message_id,record_id));
        CREATE TABLE IF NOT EXISTS mail_sends (owner TEXT NOT NULL, send_id TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(owner,send_id));
        CREATE TABLE IF NOT EXISTS mail_ranges (account_id TEXT PRIMARY KEY REFERENCES mail_accounts(id) ON DELETE CASCADE, selection TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mail_tasks (message_id TEXT PRIMARY KEY REFERENCES mail_messages(id) ON DELETE CASCADE, task_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE);
        ''')

    def cipher(self):
        try:
            from cryptography.fernet import Fernet
            return Fernet(os.environ['MAIL_TOKEN_KEY'].encode())
        except (ImportError, KeyError, ValueError):
            raise MailError('Configure MAIL_TOKEN_KEY and install email dependencies before connecting mail.') from None

    def config(self, provider):
        if provider not in PROVIDERS:
            raise MailError('Choose Google or Microsoft.')
        prefix = 'GOOGLE_MAIL_' if provider == 'google' else 'MICROSOFT_MAIL_'
        client, secret = os.getenv(prefix+'CLIENT_ID', ''), os.getenv(prefix+'CLIENT_SECRET', '')
        origin = os.getenv('SPROCKET_ORIGIN', 'http://127.0.0.1:8765').rstrip('/')
        u = urlparse(origin)
        if (u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost'))) or u.path or u.query or u.fragment or u.username:
            raise MailError('SPROCKET_ORIGIN must be HTTPS, or a loopback HTTP origin.')
        if not client or not secret:
            raise MailError('This email provider needs server-side app credentials. See Email setup.')
        self.cipher()
        return dict(PROVIDERS[provider], client=client, secret=secret, origin=origin, redirect=origin+'/mail/callback/'+provider)

    def status(self, owner):
        providers = []
        for provider, meta in PROVIDERS.items():
            try:
                self.config(provider)
                ready, reason = True, ''
            except MailError as error:
                ready, reason = False, str(error)
            providers.append(dict(id=provider, label=meta['label'], ready=ready, reason=reason))
        with self.connect() as db:
            accounts = [dict(r) for r in db.execute('SELECT id,provider,email,signature,days,last_sync FROM mail_accounts WHERE owner=?', (owner,))]
        with self.connect() as db:
            for account in accounts:
                row = db.execute('SELECT selection FROM mail_ranges WHERE account_id=?',(account['id'],)).fetchone()
                account['import_range'] = json.loads(row[0]) if row else {'preset': str(account['days'])}
        return dict(providers=providers, accounts=accounts)

    def begin(self, provider, owner):
        cfg = self.config(provider)
        state, verifier, browser = [secrets.token_urlsafe(32) for _ in range(3)]
        with self.lock:
            self.pending = {k: v for k,v in self.pending.items() if v['expires'] > time.time()}
            if len(self.pending) >= 1000:
                raise MailError('Too many pending connections. Try later.')
            self.pending[state] = dict(provider=provider, owner=owner, verifier=verifier, browser=browser, expires=time.time()+600)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params = dict(client_id=cfg['client'], redirect_uri=cfg['redirect'], response_type='code', scope=cfg['scopes'], state=state, code_challenge=challenge, code_challenge_method='S256')
        params.update(dict(access_type='offline', prompt='consent') if provider == 'google' else dict(response_mode='query', prompt='select_account'))
        cookie = 'sprocket_mail='+browser+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=600'+('; Secure' if cfg['origin'].startswith('https:') else '')
        return cfg['auth']+'?'+urlencode(params), cookie

    def token_request(self, provider, params):
        cfg = self.config(provider)
        return remote(cfg['token'], urlencode(dict(params, client_id=cfg['client'], client_secret=cfg['secret'])).encode(), {'Content-Type':'application/x-www-form-urlencoded'})

    def pack(self, tokens):
        return self.cipher().encrypt(json.dumps(tokens).encode()).decode()

    def unpack(self, value):
        try:
            return json.loads(self.cipher().decrypt(value.encode()))
        except MailError:
            raise
        except Exception:
            raise MailError('Stored mail credentials cannot be opened. Restore the encryption key or disconnect and reconnect.') from None

    def finish(self, provider, owner, query, headers):
        with self.lock:
            attempt = self.pending.pop(query.get('state', [''])[0], None)
        if not attempt or attempt['expires'] <= time.time() or attempt['provider'] != provider or attempt['owner'] != owner or not hmac.compare_digest(attempt['browser'], OIDC.cookie_value(headers, 'sprocket_mail')):
            raise MailError('Connection expired or browser identity changed. Start a new connection.')
        if 'error' in query or not query.get('code'):
            raise MailError('Email permission was declined. Start a new connection when ready.')
        cfg = self.config(provider)
        tokens = self.token_request(provider, dict(grant_type='authorization_code', code=query['code'][0], redirect_uri=cfg['redirect'], code_verifier=attempt['verifier']))
        granted = set(tokens.get('scope', '').split())
        required = set(cfg['scopes'].split())-{'offline_access'}
        if provider == 'microsoft':
            required = {s.rsplit('/',1)[-1].lower() for s in required}
            granted = {s.rsplit('/',1)[-1].lower() for s in granted}
        if not required.issubset(granted) or not tokens.get('access_token') or not tokens.get('refresh_token'):
            raise MailError('Read, send and offline permissions are required. Reconnect and grant all requested permissions.')
        tokens['expires_at'] = time.time()+int(tokens.get('expires_in', 3600))
        profile = self.call(provider, tokens['access_token'], '/profile' if provider == 'google' else '/me?$select=mail,userPrincipalName')
        address = profile.get('emailAddress') if provider == 'google' else (profile.get('mail') or profile.get('userPrincipalName'))
        if not address or len(address) > 320:
            raise MailError('Provider did not return an email address.')
        with self.connect() as db:
            db.execute('INSERT INTO mail_accounts(id,owner,provider,email,tokens) VALUES(?,?,?,?,?) ON CONFLICT(owner,provider,email) DO UPDATE SET tokens=excluded.tokens', (str(uuid.uuid4()),owner,provider,address.lower(),self.pack(tokens)))

    def account(self, db, owner, ident):
        row = db.execute('SELECT * FROM mail_accounts WHERE id=? AND owner=?', (ident,owner)).fetchone()
        if not row:
            raise MailError('Email account not found.')
        return dict(row)

    def access(self, account):
        tokens = self.unpack(account['tokens'])
        if tokens.get('expires_at', 0) <= time.time()+60:
            fresh = self.token_request(account['provider'], dict(grant_type='refresh_token', refresh_token=tokens['refresh_token']))
            if not fresh.get('access_token'):
                raise MailError('Reconnect your email account.')
            tokens.update(fresh)
            tokens['expires_at'] = time.time()+int(fresh.get('expires_in', 3600))
            # Persist refresh rotation before later API calls can fail.
            with self.connect() as db:
                db.execute('UPDATE mail_accounts SET tokens=? WHERE id=?', (self.pack(tokens),account['id']))
        return tokens['access_token']

    def call(self, provider, token, path, body=None, method=None):
        base = 'https://gmail.googleapis.com/gmail/v1/users/me' if provider == 'google' else 'https://graph.microsoft.com/v1.0'
        headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json'}
        if provider == 'microsoft':
            headers['Prefer'] = 'outlook.body-content-type="text", IdType="ImmutableId"'
        return remote(base+path, json.dumps(body).encode() if body is not None else None, headers, method)

    def ensure_correspondents(self, db, message, account):
        """Create missing CRM correspondents/domain companies; never invent firm details."""
        settings = json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
        kinds = {t['id'] for t in settings['types']}
        if not {'contacts','companies'}.issubset(kinds):
            raise MailError('Contacts and Companies record types are required for automatic email sync.')
        own = {r[0].lower() for r in db.execute('SELECT email FROM mail_accounts WHERE owner=?',(account['owner'],))}
        now = datetime.now(timezone.utc).isoformat()
        # Received mail creates the sender; sent mail creates its recipients, including Cc.
        counterpart = message['sender'] if message['direction'] == 'received' else ', '.join(filter(None, [message['to'],message.get('cc','')]))
        created_contacts = created_companies = 0
        seen = set()
        for display, address in getaddresses([counterpart]):
            address = address.strip().lower()
            if address in own or address in seen or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+', address):
                continue
            seen.add(address)
            domain = address.rsplit('@',1)[1]
            contacts = [(r['id'],json.loads(r['body'])) for r in db.execute("SELECT * FROM records WHERE kind='contacts'")]
            matches = [(ident,body) for ident,body in contacts if str(body.get('email','')).strip().lower() == address]
            company = None
            for r in db.execute("SELECT * FROM records WHERE kind='companies'"):
                body = json.loads(r['body'])
                raw = str(body.get('domain','')).strip().lower()
                host = urlparse(raw if '://' in raw else '//'+raw).hostname or ''
                if host.removeprefix('www.') == domain.removeprefix('www.'):
                    company = r['id']; break
            if not company:
                company = str(uuid.uuid4())
                body = dict(name=domain,domain=domain,links=[],notes='Automatically created from an email domain. Company identity has not been verified.',record_source='Email sync')
                db.execute('INSERT INTO records VALUES(?,?,?,?)',(company,'companies',json.dumps(body),now))
                created_companies += 1
            if not matches:
                ident = str(uuid.uuid4())
                body = dict(lifecycle_stage='Lead',owner=account.get('crm_owner') or account['email'],name=display.strip()[:300] or address,email=address,links=[company],notes='Automatically created from a synced email correspondent.',record_source='Email sync')
                db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,'contacts',json.dumps(body),now))
                created_contacts += 1
            else:
                for ident,body in matches:
                    if company not in body.get('links',[]):
                        body['links'] = body.get('links',[])+[company]
                        db.execute('UPDATE records SET body=?,updated=? WHERE id=?',(json.dumps(body),now,ident))
        return created_contacts,created_companies

    def log_message(self, db, m):
        count = 0
        for r in self.matched(db,m):
            if db.execute('SELECT 1 FROM mail_logs WHERE message_id=? AND record_id=?',(m['id'],r['id'])).fetchone():
                for activity in db.execute('SELECT id,body FROM activities WHERE record_id=?',(r['id'],)).fetchall():
                    body = json.loads(activity['body'])
                    if body.get('mail_message_id') == m['id']:
                        body['email'] = {k:m.get(k,'') for k in ('subject','sender','to','cc','date','direction','text','html')}
                        db.execute('UPDATE activities SET body=? WHERE id=?',(json.dumps(body),activity['id']))
                continue
            body = dict(type='Email',email={k:m.get(k,'') for k in ('subject','sender','to','cc','date','direction','text','html')},text=m['subject']+'\nFrom: '+m['sender']+'\nTo: '+m['to']+'\n\n'+m['text'],mail_message_id=m['id'])
            db.execute('INSERT INTO activities VALUES(?,?,?,?)',(str(uuid.uuid4()),r['id'],json.dumps(body),m['date']))
            db.execute('INSERT INTO mail_logs VALUES(?,?)',(m['id'],r['id']))
            count += 1
        return count

    def matched(self, db, message):
        participants = set(a for key in ('sender','to','cc') for a in addresses(message.get(key,'')))
        contacts = [dict(json.loads(r['body']), id=r['id'], kind=r['kind']) for r in db.execute("SELECT * FROM records WHERE kind='contacts'") if str(json.loads(r['body']).get('email','')).lower() in participants]
        ids = {r['id'] for r in contacts}
        deals = [dict(json.loads(r['body']), id=r['id'], kind=r['kind']) for r in db.execute("SELECT * FROM records WHERE kind='deals'")]
        linked = [r for r in deals if ids.intersection(r.get('links', [])) or any(r['id'] in c.get('links', []) for c in contacts)]
        return [dict(id=r['id'],name=r['name'],kind=r['kind']) for r in contacts+linked]

    def messages(self, owner, account_id):
        with self.connect() as db:
            self.account(db, owner, account_id)
            messages = [dict(json.loads(r['body']), id=r['id']) for r in db.execute('SELECT * FROM mail_messages WHERE account_id=?', (account_id,))]
            for m in messages:
                m['matches'] = self.matched(db,m)
                m['logged_records'] = [r[0] for r in db.execute('SELECT record_id FROM mail_logs WHERE message_id=?',(m['id'],))]
            return sorted(messages, key=lambda m:m['date'], reverse=True)[:200]

    def import_range(self, data):
        preset = str(data.get('preset', ''))
        today = datetime.now(timezone.utc).date()
        if preset in ('7', '30', '90'):
            start, end = today-timedelta(days=int(preset)-1), today
        elif preset == 'custom':
            try:
                start = datetime.strptime(data.get('start', ''), '%Y-%m-%d').date()
                end = datetime.strptime(data.get('end', ''), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                raise MailError('Choose valid start and end dates.') from None
        else:
            raise MailError('Choose 7, 30, 90 days or a custom date range.')
        if start > end or end > today:
            raise MailError('Start must be before end, and dates cannot be in the future.')
        lower = datetime.combine(start, datetime.min.time(), timezone.utc)
        upper = datetime.combine(end+timedelta(days=1), datetime.min.time(), timezone.utc)
        return dict(preset=preset, start=start.isoformat(), end=end.isoformat()), lower, upper

    def import_job(self, owner, data):
        job = self.imports.get(data.get('import_id'))
        if not job or job['owner'] != owner or job['account_id'] != data.get('account_id') or job['expires'] < time.time():
            raise MailError('Import preview expired. Preview the date range again.')
        return job

    def preview(self, owner, data):
        with self.lock:
            with self.connect() as db:
                account = self.account(db, owner, data['account_id'])
            token, provider = self.access(account), account['provider']
            if data.get('import_id'):
                job = self.import_job(owner, data)
            else:
                selection, lower, upper = self.import_range(data)
                if provider == 'google':
                    params = dict(maxResults=500, q=f'after:{int(lower.timestamp())-1} before:{int(upper.timestamp())} -in:trash -in:spam')
                    path = '/messages?'+urlencode(params)
                else:
                    stamp = lambda dt: dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    path = '/me/messages?'+urlencode({'$top':100,'$select':'id','$filter':f'receivedDateTime ge {stamp(lower)} and receivedDateTime lt {stamp(upper)}'})
                self.imports = {k:v for k,v in self.imports.items() if v['expires'] > time.time()}
                if len(self.imports) >= 100: raise MailError('Too many previews. Try again later.')
                ident = secrets.token_urlsafe(32)
                job = dict(id=ident, owner=owner, account_id=account['id'], selection=selection, path=path, ids=[], seen=set(), pages=set(), index=0, expires=time.time()+3600, contacts_created=0, companies_created=0, logged=0)
                self.imports[ident] = job
            if job['path']:
                path = job['path']
                if path in job['pages']: raise MailError('Provider repeated a page. Preview again.')
                listing = self.call(provider, token, path)
                rows = listing.get('messages' if provider == 'google' else 'value', [])
                for row in rows:
                    if row['id'] not in job['seen']:
                        job['ids'].append(row['id']); job['seen'].add(row['id'])
                job['pages'].add(path)
                if provider == 'google':
                    next_token = listing.get('nextPageToken')
                    job['path'] = ''
                    if next_token:
                        from urllib.parse import parse_qs
                        params = {k:v[0] for k,v in parse_qs(urlparse(path).query).items()}
                        params['pageToken'] = next_token
                        job['path'] = '/messages?'+urlencode(params)
                else:
                    link = listing.get('@odata.nextLink', '')
                    if link:
                        u = urlparse(link)
                        if u.scheme != 'https' or u.netloc != 'graph.microsoft.com' or u.path != '/v1.0/me/messages' or u.fragment:
                            raise MailError('Invalid provider pagination link.')
                        job['path'] = u.path[len('/v1.0'):]+('?' + u.query if u.query else '')
                    else: job['path'] = ''
            return dict(import_id=job['id'], count=len(job['ids']), ready=not job['path'], selection=job['selection'])

    def sync(self, owner, ident, data=None):
        with self.lock:
            job = self.import_job(owner, dict(data or {}, account_id=ident))
            if job['path']: raise MailError('Finish previewing the range before importing.')
            with self.connect() as db:
                account = self.account(db,owner,ident)
            account['crm_owner'] = (data or {}).get('_crm_owner') or account['email']
            token, provider = self.access(account), account['provider']
            ids = job['ids'][job['index']:job['index']+10]
            messages = []
            for remote_id in ids:
                path = ('/messages/' if provider == 'google' else '/me/messages/')+quote(remote_id,safe='')
                if provider == 'google': path += '?format=full'
                message = self.call(provider, token, path)
                m = gmail_message(message) if provider == 'google' else microsoft_message(message)
                if provider == 'microsoft' and account['email'] in addresses(m['sender']): m['direction']='sent'
                messages.append(m)
            now = datetime.now(timezone.utc).isoformat()
            contacts_created = companies_created = logged = 0
            with self.connect() as db:
                for m in messages:
                    db.execute('INSERT INTO mail_messages VALUES(?,?,?,?) ON CONFLICT(account_id,provider_id) DO UPDATE SET body=excluded.body', (str(uuid.uuid4()),ident,m['provider_id'],json.dumps(m)))
                    ident_row = db.execute('SELECT id FROM mail_messages WHERE account_id=? AND provider_id=?',(ident,m['provider_id'])).fetchone()
                    m['id'] = ident_row[0]
                    c,co = self.ensure_correspondents(db,m,account)
                    contacts_created += c; companies_created += co
                    logged += self.log_message(db,m)
                db.execute('UPDATE mail_accounts SET last_sync=? WHERE id=?',(now,ident))
                db.execute('INSERT INTO mail_ranges VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET selection=excluded.selection',(ident,json.dumps(job['selection'])))
            job['index'] += len(ids)
            for key, value in [('contacts_created',contacts_created),('companies_created',companies_created),('logged',logged)]: job[key] += value
            job['expires'] = time.time()+3600
            return dict(ok=True,count=job['index'],total=len(job['ids']),done=job['index']==len(job['ids']),contacts_created=job['contacts_created'],companies_created=job['companies_created'],logged=job['logged'])

    def message(self, db, owner, ident):
        row = db.execute('SELECT m.* FROM mail_messages m JOIN mail_accounts a ON a.id=m.account_id WHERE m.id=? AND a.owner=?',(ident,owner)).fetchone()
        if not row: raise MailError('Email message not found.')
        return dict(json.loads(row['body']),id=row['id'],account_id=row['account_id'])

    def log(self, owner, ident):
        with self.connect() as db:
            m = self.message(db,owner,ident)
            return dict(ok=True,count=self.log_message(db,m))

    def task(self, owner, data):
        with self.connect() as db:
            m = self.message(db,owner,data['message_id'])
            previous = db.execute('SELECT task_id FROM mail_tasks WHERE message_id=?',(m['id'],)).fetchone()
            if previous: return dict(ok=True,id=previous[0],existing=True)
            name = str(data.get('name','')).strip()
            due = str(data.get('due_date',''))
            if not name or len(name)>300: raise MailError('Enter a task name up to 300 characters.')
            datetime.strptime(due,'%Y-%m-%d')
            settings = json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
            if not any(t['id']=='tasks' for t in settings['types']): raise MailError('Create a Tasks record type first.')
            ident = str(uuid.uuid4())
            body = dict(name=name,due_date=due,notes='Follow up on email: '+m['subject'],links=[r['id'] for r in self.matched(db,m)],mail_message_id=m['id'])
            db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,'tasks',json.dumps(body),datetime.now(timezone.utc).isoformat()))
            db.execute('INSERT INTO mail_tasks VALUES(?,?)',(m['id'],ident))
            return dict(ok=True,id=ident)

    def send(self, owner, data):
        with self.lock:
            with self.connect() as db:
                account = self.account(db,owner,data['account_id'])
                reply = self.message(db,owner,data['reply_id']) if data.get('reply_id') else None
            if reply and reply['account_id'] != account['id']: raise MailError('Reply must use the original email account.')
            recipient = str(data.get('to','')).strip()
            if len(recipient)>320 or '\r' in recipient or '\n' in recipient or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',recipient): raise MailError('Enter one valid recipient email address.')
            subject, text = str(data.get('subject','')).strip(), str(data.get('text','')).strip()
            if not subject or len(subject)>500 or '\r' in subject or '\n' in subject or not text or len(text)>50000: raise MailError('Subject and message are required (maximum 500 / 50,000 characters).')
            if account['signature']: text += '\n\n'+account['signature']
            token, provider = self.access(account), account['provider']
            send_id = data.get('send_id', '')
            if not isinstance(send_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}', send_id):
                raise MailError('A unique send request ID is required.')
            with self.connect() as db:
                if db.execute('SELECT 1 FROM mail_sends WHERE owner=? AND send_id=?', (owner,send_id)).fetchone():
                    raise MailError('This send was already attempted. Check Sent mail before composing again.')
                db.execute('INSERT INTO mail_sends VALUES(?,?,?)', (owner,send_id,'attempted'))
            # Never automatically retry a send: delivery may have succeeded before a timeout.
            if provider == 'google':
                message = EmailMessage()
                message['From'],message['To'],message['Subject'] = account['email'],recipient,subject
                if reply and reply.get('message_id'):
                    if '\r' in reply['message_id'] or '\n' in reply['message_id']: raise MailError('Invalid reply header.')
                    message['In-Reply-To']=reply['message_id']; message['References']=reply['message_id']
                message.set_content(text)
                payload = {'raw':base64.urlsafe_b64encode(message.as_bytes()).decode()}
                if reply: payload['threadId']=reply['thread_id']
                result = self.call(provider,token,'/messages/send',payload)
                provider_id = result['id']
            else:
                if reply:
                    # Graph's reply API preserves the recipient and subject of the original thread.
                    if recipient.lower() not in addresses(reply['sender']) or subject != ('Re: '+reply['subject'] if not reply['subject'].lower().startswith('re:') else reply['subject']):
                        raise MailError('For a Microsoft reply, keep the original recipient and reply subject.')
                    self.call(provider,token,'/me/messages/'+quote(reply['provider_id'],safe='')+'/reply',{'comment':text})
                else:
                    self.call(provider,token,'/me/sendMail',dict(message=dict(subject=subject,body=dict(contentType='Text',content=text),toRecipients=[dict(emailAddress=dict(address=recipient))]),saveToSentItems=True))
                provider_id = 'local-sent-'+str(uuid.uuid4())
            m = dict(provider_id=provider_id,thread_id=reply['thread_id'] if reply else '',subject=subject,sender=account['email'],to=recipient,cc='',text=text,date=datetime.now(timezone.utc).isoformat(),message_id='',direction='sent')
            with self.connect() as db:
                ident=str(uuid.uuid4())
                db.execute('INSERT INTO mail_messages VALUES(?,?,?,?)',(ident,account['id'],provider_id,json.dumps(m)))
                self.ensure_correspondents(db,m,account)
                m['id']=ident
                self.log_message(db,m)
                db.execute('UPDATE mail_sends SET status=? WHERE owner=? AND send_id=?', ('accepted',owner,send_id))
            return dict(ok=True,message_id=ident,message='Provider accepted the message. Delivery is not guaranteed; see Sent mail.')

    def post(self, action, owner, data):
        if action == 'preview': return self.preview(owner,data)
        if action == 'sync': return self.sync(owner,data['account_id'],data)
        if action == 'send': return self.send(owner,data)
        if action == 'log': return self.log(owner,data['message_id'])
        if action == 'task': return self.task(owner,data)
        with self.lock, self.connect() as db:
            self.account(db,owner,data['account_id'])
            if action == 'disconnect':
                db.execute('DELETE FROM mail_accounts WHERE id=?',(data['account_id'],))
                return dict(ok=True)
            if action == 'preferences':
                days, signature = data.get('days'), data.get('signature','')
                if days not in (7,30,90) or not isinstance(signature,str) or len(signature)>2000: raise MailError('Choose 7, 30 or 90 days and a signature up to 2,000 characters.')
                db.execute('UPDATE mail_accounts SET days=?,signature=? WHERE id=?',(days,signature,data['account_id']))
                return dict(ok=True)
        raise MailError('Unknown email action.')
