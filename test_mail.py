import base64
import json
import os
import tempfile
import time
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from mail_service import MailService, MailError, gmail_message, microsoft_message, NoRedirect
from test_server import app, CRMTest

class MailTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old_db=app.DB
        app.DB=Path(self.temp.name)/'mail.db';app.initialize();self.mail=MailService(app.connect)
        self.env=patch.dict(os.environ, {'MAIL_TOKEN_KEY':Fernet.generate_key().decode(), 'GOOGLE_MAIL_CLIENT_ID':'test-client', 'GOOGLE_MAIL_CLIENT_SECRET':'test-secret', 'MICROSOFT_MAIL_CLIENT_ID':'test-client','MICROSOFT_MAIL_CLIENT_SECRET':'test-secret','SPROCKET_ORIGIN':'http://127.0.0.1:8765'})
        self.env.start();self.owner='user-a'
        with app.connect() as db:
            db.execute('INSERT INTO records VALUES(?,?,?,?)',('contact','contacts',json.dumps({'name':'SAMPLE — Contact','email':'person@example.test','links':['deal']}),'2026-01-01'))
            db.execute('INSERT INTO records VALUES(?,?,?,?)',('deal','deals',json.dumps({'name':'SAMPLE — Deal','links':[]}),'2026-01-01'))
    def tearDown(self):
        self.env.stop();app.DB=self.old_db;self.temp.cleanup()
    def account(self, provider='google', expires=0):
        tokens={'access_token':'private-access','refresh_token':'private-refresh','expires_at':expires}
        with app.connect() as db:
            db.execute('INSERT INTO mail_accounts(id,owner,provider,email,tokens) VALUES(?,?,?,?,?)',('account',self.owner,provider,'me@example.test',self.mail.pack(tokens)))
    def message(self):
        m=dict(provider_id='remote-id',thread_id='thread',subject='Test',sender='Person <person@example.test>',to='me@example.test',cc='',text='<script>not HTML</script>\nSample email',date='2026-01-01T00:00:00+00:00',message_id='<original@example.test>',direction='received')
        with app.connect() as db:db.execute('INSERT INTO mail_messages VALUES(?,?,?,?)',('message','account','remote-id',json.dumps(m)))
        return m
    def test_state_pkce_and_wrong_browser_no_token_exchange(self):
        url,cookie=self.mail.begin('google',self.owner)
        self.assertIn('code_challenge_method=S256',url);self.assertIn('access_type=offline',url)
        state=next(iter(self.mail.pending))
        with patch.object(self.mail,'token_request') as request:
            with self.assertRaises(MailError): self.mail.finish('google',self.owner,{'state':[state],'code':['code']},{'Cookie':'sprocket_mail=wrong'})
            request.assert_not_called()
    def test_callback_wrong_owner_expiration_provider_and_replay(self):
        for mismatch in ('owner','expired','provider'):
            _,cookie=self.mail.begin('google',self.owner);state=next(iter(self.mail.pending));attempt=self.mail.pending[state]
            if mismatch=='expired':attempt['expires']=0
            with self.assertRaises(MailError):self.mail.finish('microsoft' if mismatch=='provider' else 'google','other' if mismatch=='owner' else self.owner,{'state':[state],'code':['code']},{'Cookie':cookie.split(';')[0]})
            self.assertNotIn(state,self.mail.pending)
    def test_callback_encrypts_credentials_checks_scopes_and_reconnects(self):
        tokens=dict(access_token='secret-access',refresh_token='secret-refresh',scope='Mail.Read Mail.Send User.Read',expires_in=3600)
        for _ in range(2):
            _,cookie=self.mail.begin('microsoft',self.owner);state=next(iter(self.mail.pending))
            with patch.object(self.mail,'token_request',return_value=tokens.copy()), patch.object(self.mail,'call',return_value={'mail':'me@example.test'}):
                self.mail.finish('microsoft',self.owner,{'state':[state],'code':['code']},{'Cookie':cookie.split(';')[0]})
        with app.connect() as db:
            rows=db.execute('SELECT * FROM mail_accounts').fetchall();self.assertEqual(1,len(rows));self.assertNotIn('secret-access',rows[0]['tokens']);self.assertEqual('secret-access',self.mail.unpack(rows[0]['tokens'])['access_token'])
        status=json.dumps(self.mail.status(self.owner));self.assertNotIn('secret-access',status);self.assertNotIn('secret-refresh',status)
        _,cookie=self.mail.begin('google',self.owner);state=next(iter(self.mail.pending))
        with patch.object(self.mail,'token_request',return_value={'access_token':'x','refresh_token':'y','scope':'gmail.send'}):
            with self.assertRaises(MailError):self.mail.finish('google',self.owner,{'state':[state],'code':['code']},{'Cookie':cookie.split(';')[0]})
    def test_refresh_rotation_persists(self):
        self.account()
        with app.connect() as db:account=self.mail.account(db,self.owner,'account')
        with patch.object(self.mail,'token_request',return_value={'access_token':'new','refresh_token':'rotated','expires_in':600}):self.assertEqual('new',self.mail.access(account))
        with app.connect() as db:self.assertEqual('rotated',self.mail.unpack(self.mail.account(db,self.owner,'account')['tokens'])['refresh_token'])
    def test_messages_accounts_and_mutations_are_owner_scoped(self):
        self.account();self.message();self.assertEqual([],self.mail.status('other')['accounts'])
        for action,data in [('disconnect',{'account_id':'account'}),('preferences',{'account_id':'account','days':7,'signature':''}),('log',{'message_id':'message'}),('task',{'message_id':'message','name':'test','due_date':'2026-01-02'})]:
            with self.assertRaises(MailError):self.mail.post(action,'other',data)
        with self.assertRaises(MailError):self.mail.messages('other','account')
    def test_matching_logging_tasks_deduplicate_and_disconnect_retains_crm(self):
        self.account();self.message()
        self.assertEqual({'contact','deal'},{m['id'] for m in self.mail.messages(self.owner,'account')[0]['matches']})
        self.assertEqual(2,self.mail.log(self.owner,'message')['count']);self.assertEqual(0,self.mail.log(self.owner,'message')['count'])
        task=self.mail.task(self.owner,dict(message_id='message',name='Follow up',due_date='2026-01-02'))
        self.assertEqual(task['id'],self.mail.task(self.owner,dict(message_id='message',name='again',due_date='2026-01-02'))['id'])
        self.mail.post('disconnect',self.owner,{'account_id':'account'})
        with app.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM mail_messages').fetchone()[0]);self.assertEqual(2,db.execute('SELECT count(*) FROM activities').fetchone()[0]);self.assertIsNotNone(db.execute('SELECT id FROM records WHERE id=?',(task['id'],)).fetchone())
    def test_google_sync_upserts_and_automatically_logs(self):
        self.account(expires=time.time()+600)
        message={'id':'remote','payload':{'mimeType':'text/plain','headers':[{'name':'From','value':'person@example.test'}],'body':{'data':base64.urlsafe_b64encode(b'Sample mail').decode()}},'internalDate':'1000'}
        def call(provider,token,path,*args):return {'messages':[{'id':'remote'}],'nextPageToken':'more'} if path.startswith('/messages?') else message
        with patch.object(self.mail,'call',side_effect=call):
            self.assertTrue(self.mail.sync(self.owner,'account')['limited']);self.mail.sync(self.owner,'account')
        with app.connect() as db:self.assertEqual(1,db.execute('SELECT count(*) FROM mail_messages').fetchone()[0]);self.assertEqual(2,db.execute('SELECT count(*) FROM activities').fetchone()[0])
    def test_sync_creates_contact_company_reuses_domain_and_excludes_own_address(self):
        self.account(expires=time.time()+600)
        messages = [{'id':'one','payload':{'headers':[{'name':'From','value':'New Person <new@newco.example>'},{'name':'To','value':'me@example.test'}]},'internalDate':'1000'}, {'id':'two','payload':{'headers':[{'name':'From','value':'Other <other@newco.example>'}]},'internalDate':'2000'}]
        def call(provider,token,path,*args):
            if path.startswith('/messages?'):return {'messages':[{'id':m['id']} for m in messages]}
            return next(m for m in messages if '/messages/'+m['id']+'?' in path)
        with patch.object(self.mail,'call',side_effect=call):
            result=self.mail.sync(self.owner,'account')
            self.assertEqual(2,result['contacts_created']);self.assertEqual(1,result['companies_created']);self.assertEqual(2,result['logged'])
            result=self.mail.sync(self.owner,'account')
            self.assertEqual(0,result['contacts_created']);self.assertEqual(0,result['companies_created']);self.assertEqual(0,result['logged'])
        with app.connect() as db:
            contacts=[json.loads(r[0]) for r in db.execute("SELECT body FROM records WHERE kind='contacts'")]
            self.assertFalse(any(c.get('email')=='me@example.test' for c in contacts))
            created=[c for c in contacts if c.get('record_source')=='Email sync']
            self.assertEqual(created[0]['links'],created[1]['links'])
            company=json.loads(db.execute("SELECT body FROM records WHERE kind='companies'").fetchone()[0]);self.assertEqual('newco.example',company['domain'])

    def test_gmail_mime_reply_signature_and_no_duplicate_send(self):
        self.account(expires=time.time()+600);self.message();self.mail.post('preferences',self.owner,{'account_id':'account','days':7,'signature':'Sample signature'})
        data=dict(send_id='unique-send-id-12345',account_id='account',reply_id='message',to='person@example.test',subject='Re: Test',text='Sample reply')
        with patch.object(self.mail,'call',return_value={'id':'sent'}) as call:
            self.mail.send(self.owner,data);payload=call.call_args[0][3]
            message=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(payload['raw']))
            self.assertEqual('<original@example.test>',message['In-Reply-To']);self.assertIn('Sample signature',message.get_content());self.assertEqual('thread',payload['threadId'])
            with self.assertRaises(MailError):self.mail.send(self.owner,data)
            self.assertEqual(1,call.call_count)
    def test_unknown_delivery_does_not_retry(self):
        self.account(expires=time.time()+600)
        data=dict(send_id='uncertain-send-12345',account_id='account',to='person@example.test',subject='Sample',text='Test')
        with patch.object(self.mail,'call',side_effect=MailError('Timed out')) as call:
            with self.assertRaises(MailError):self.mail.send(self.owner,data)
            with self.assertRaises(MailError):self.mail.send(self.owner,data)
            self.assertEqual(1,call.call_count)
    def test_microsoft_send_and_reply_adapter(self):
        self.account('microsoft',expires=time.time()+600);self.message()
        with patch.object(self.mail,'call',return_value={}) as call:
            self.mail.send(self.owner,dict(send_id='microsoft-send-12345',account_id='account',to='person@example.test',subject='Test',text='Body'))
            self.assertEqual('/me/sendMail',call.call_args[0][2]);self.assertEqual('Text',call.call_args[0][3]['message']['body']['contentType'])
            self.mail.send(self.owner,dict(send_id='microsoft-reply-12345',account_id='account',reply_id='message',to='person@example.test',subject='Re: Test',text='Reply'))
            self.assertEqual('/me/messages/remote-id/reply',call.call_args[0][2])
    def test_header_injection_and_untrusted_redirect_rejected(self):
        self.account(expires=time.time()+600)
        with patch.object(self.mail,'call') as call:
            with self.assertRaises(MailError):self.mail.send(self.owner,dict(account_id='account',to='person@example.test\r\nBcc: other@example.test',subject='test',text='test'))
            call.assert_not_called()
        with self.assertRaises(MailError):NoRedirect().redirect_request(None,None,302,'',{},'https://attacker.example')
    def test_message_normalization_no_attachment_decode(self):
        raw=base64.urlsafe_b64encode(b'Sample body').decode()
        m=gmail_message({'id':'test','payload':{'parts':[{'mimeType':'text/plain','body':{'data':raw}},{'filename':'private.txt','mimeType':'text/plain','body':{'data':raw}}]},'internalDate':'1000'})
        self.assertEqual('Sample body',m['text'])
        self.assertEqual('Sample',microsoft_message({'id':'test','body':{'content':'Sample'}})['text'])

class MailHTTPTest(CRMTest):
    def test_mail_requires_origin_and_does_not_leak_missing_credentials(self):
        self.assertEqual(403,self.request('/api/mail/connect',{'provider':'google'})[0])
        status=self.request('/api/mail')[1];self.assertEqual(2,len(status['providers']));self.assertNotIn('secret',json.dumps(status['accounts']))
        self.assertEqual(400,self.request('/api/mail/connect',{'provider':'unknown'},self.url)[0])
