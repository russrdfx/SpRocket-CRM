"""Separate, read-only Google Calendar connection and reviewed CRM meeting logging."""
import hmac,json,os,time,uuid
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
from auth import OIDC
from mail_service import MailService,MailError,remote

SCOPE='https://www.googleapis.com/auth/calendar.events.readonly'
class CalendarService(MailService):
    def initialize(self,db):
        db.executescript('''CREATE TABLE IF NOT EXISTS calendar_accounts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,email TEXT NOT NULL,tokens TEXT NOT NULL,UNIQUE(owner,email));
        CREATE TABLE IF NOT EXISTS calendar_events(account_id TEXT NOT NULL REFERENCES calendar_accounts(id) ON DELETE CASCADE,event_id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(account_id,event_id));
        CREATE TABLE IF NOT EXISTS calendar_logs(account_id TEXT NOT NULL,event_id TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,activity_id TEXT NOT NULL,PRIMARY KEY(account_id,event_id,record_id));''')
    def config(self,provider='google'):
        if provider!='google':raise MailError('Choose Google Calendar.')
        # Reuse the registered app, never the mailbox access token or consent.
        cfg=super().config('google');cfg.update(scopes=SCOPE+' openid email',redirect=cfg['origin']+'/calendar/callback/google')
        return cfg
    def begin(self,provider,owner):
        url,cookie=super().begin(provider,owner);return url,cookie.replace('sprocket_mail=','sprocket_calendar=',1)
    def finish(self,provider,owner,query,headers):
        with self.lock:attempt=self.pending.pop(query.get('state',[''])[0],None)
        if not attempt or attempt['expires']<=time.time() or attempt['owner']!=owner or attempt['provider']!=provider or not hmac.compare_digest(attempt['browser'],OIDC.cookie_value(headers,'sprocket_calendar')):raise MailError('Calendar connection expired. Start again.')
        if 'error' in query or not query.get('code'):raise MailError('Calendar permission was declined.')
        cfg=self.config(provider);tokens=self.token_request(provider,dict(grant_type='authorization_code',code=query['code'][0],redirect_uri=cfg['redirect'],code_verifier=attempt['verifier']))
        if SCOPE not in tokens.get('scope','').split() or not tokens.get('refresh_token') or not tokens.get('access_token'):raise MailError('Calendar read and offline permissions are required.')
        user=remote('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':'Bearer '+tokens['access_token']},service='Calendar')
        email=user.get('email','')
        if user.get('email_verified') is not True or '@' not in email or len(email)>320:raise MailError('Google did not return a verified account email.')
        tokens['expires_at']=time.time()+int(tokens.get('expires_in',3600))
        with self.connect() as db:db.execute('INSERT INTO calendar_accounts VALUES(?,?,?,?) ON CONFLICT(owner,email) DO UPDATE SET tokens=excluded.tokens',(str(uuid.uuid4()),owner,email.lower(),self.pack(tokens)))
    def account(self,db,owner,ident):
        row=db.execute('SELECT * FROM calendar_accounts WHERE id=? AND owner=?',(ident,owner)).fetchone()
        if not row or not row['tokens']:raise MailError('Calendar account not found.')
        return dict(row)
    def access(self,account):
        tokens=self.unpack(account['tokens'])
        if tokens.get('expires_at',0)<=time.time()+60:
            fresh=self.token_request('google',dict(grant_type='refresh_token',refresh_token=tokens['refresh_token']))
            if not fresh.get('access_token'):raise MailError('Reconnect Google Calendar.')
            tokens.update(fresh);tokens['expires_at']=time.time()+int(fresh.get('expires_in',3600))
            with self.connect() as db:db.execute('UPDATE calendar_accounts SET tokens=? WHERE id=?',(self.pack(tokens),account['id']))
        return tokens['access_token']
    def status(self,owner):
        try:config=self.config();configured=True
        except MailError:configured=False
        with self.connect() as db:
            accounts=[dict(id=r['id'],email=r['email']) for r in db.execute('SELECT * FROM calendar_accounts WHERE owner=? AND tokens<>\'\'',(owner,))]
            events=[dict(json.loads(r['body']),event_id=r['event_id'],account_id=r['account_id']) for r in db.execute('SELECT e.* FROM calendar_events e JOIN calendar_accounts a ON a.id=e.account_id WHERE a.owner=?',(owner,))]
        return dict(configured=configured,accounts=accounts,events=sorted(events,key=lambda e:e.get('start','')),redirect_uri=config['redirect'] if configured else '')
    def sync(self,owner,data):
        start=datetime.fromisoformat(data.get('start',''));end=datetime.fromisoformat(data.get('end',''))+timedelta(days=1)
        if not 0<(end-start).days<=366:raise MailError('Choose a calendar window up to one year.')
        with self.lock:
            with self.connect() as db:account=self.account(db,owner,data.get('account_id'))
            token=self.access(account);params=dict(timeMin=start.replace(tzinfo=timezone.utc).isoformat(),timeMax=end.replace(tzinfo=timezone.utc).isoformat(),singleEvents='true',showDeleted='true',maxResults=100)
            continuation=data.get('page_token','')
            if continuation:
                job=self.imports.get(continuation)
                if not job or job['owner']!=owner or job['account']!=account['id'] or job['params']!=params or job['expires']<time.time():raise MailError('Calendar continuation expired. Start again.')
                params['pageToken']=job['token']
            result=remote('https://www.googleapis.com/calendar/v3/calendars/primary/events?'+urlencode(params),headers={'Authorization':'Bearer '+token},service='Calendar')
            with self.connect() as db:
                for event in result.get('items',[]):
                    ident=event.get('id')
                    if not ident:continue
                    body=dict(title=event.get('summary','Untitled event')[:1000],start=event.get('start',{}).get('dateTime',event.get('start',{}).get('date','')),end=event.get('end',{}).get('dateTime',event.get('end',{}).get('date','')),location=event.get('location','')[:1000],status=event.get('status','confirmed'),visibility=event.get('visibility','default'),attendees=[a['email'].lower() for a in event.get('attendees',[]) if a.get('email') and a.get('responseStatus')!='declined' and not a.get('self')])
                    previous=db.execute('SELECT body FROM calendar_events WHERE account_id=? AND event_id=?',(account['id'],ident)).fetchone()
                    if body['status']=='cancelled' and previous:
                        retained=json.loads(previous[0]);retained['status']='cancelled';body=retained
                    db.execute('INSERT INTO calendar_events VALUES(?,?,?) ON CONFLICT(account_id,event_id) DO UPDATE SET body=excluded.body',(account['id'],ident,json.dumps(body)))
                    # Correct already-reviewed timeline entries; cancelled events retain history.
                    for log in db.execute('SELECT * FROM calendar_logs WHERE account_id=? AND event_id=?',(account['id'],ident)).fetchall():
                        db.execute('UPDATE activities SET body=? WHERE id=?',(json.dumps(self.activity(body)),log['activity_id']))
            self.imports={k:v for k,v in self.imports.items() if v['expires']>time.time()}
            next_id=''
            if result.get('nextPageToken'):
                next_id=str(uuid.uuid4());params.pop('pageToken',None);self.imports[next_id]=dict(owner=owner,account=account['id'],params=params,token=result['nextPageToken'],expires=time.time()+600)
            return dict(ok=True,count=len(result.get('items',[])),next_page=next_id)
    @staticmethod
    def activity(event):
        return dict(type='Meeting',text=event.get('title','Meeting')+'\n'+event.get('start','')+' – '+event.get('end','')+'\n'+event.get('location','')+'\nStatus: '+event.get('status','confirmed'),calendar_event=True)
    def log(self,owner,data):
        with self.connect() as db:
            account=self.account(db,owner,data.get('account_id'));row=db.execute('SELECT body FROM calendar_events WHERE account_id=? AND event_id=?',(account['id'],data.get('event_id'))).fetchone()
            if not row:raise MailError('Sync this event first.')
            event=json.loads(row[0]);contacts=[r['id'] for r in db.execute("SELECT * FROM records WHERE kind='contacts'") if json.loads(r['body']).get('email','').lower() in event['attendees']]
            if not contacts:raise MailError('No attendee matches an existing contact email.')
            targets=set(contacts)
            for r in db.execute("SELECT * FROM records WHERE kind='deals'"):
                if set(contacts).intersection(json.loads(r['body']).get('links',[])):targets.add(r['id'])
            count=0
            for ident in targets:
                if db.execute('SELECT 1 FROM calendar_logs WHERE account_id=? AND event_id=? AND record_id=?',(account['id'],data['event_id'],ident)).fetchone():continue
                activity_id=str(uuid.uuid4());db.execute('INSERT INTO activities VALUES(?,?,?,?)',(activity_id,ident,json.dumps(self.activity(event)),datetime.now(timezone.utc).isoformat()));db.execute('INSERT INTO calendar_logs VALUES(?,?,?,?)',(account['id'],data['event_id'],ident,activity_id));count+=1
        return dict(ok=True,logged=count)
    def disconnect(self,owner,data):
        with self.lock,self.connect() as db:
            self.account(db,owner,data.get('account_id'));db.execute('DELETE FROM calendar_events WHERE account_id=?',(data['account_id'],));db.execute("UPDATE calendar_accounts SET tokens='' WHERE id=?",(data['account_id'],))
        return {'ok':True}
