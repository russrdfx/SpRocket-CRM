import base64,json,time,unittest
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
import test_mail
from test_server import app
import crm_tools
from mail_service import MailError

class ProductivityTest(unittest.TestCase):
    setUp=test_mail.MailTest.setUp
    tearDown=test_mail.MailTest.tearDown
    account=test_mail.MailTest.account
    def put(self,db,id,kind,body):db.execute('INSERT INTO records VALUES(?,?,?,?)',(id,kind,json.dumps(body),'original'))
    def test_merge_preserves_primary_links_and_activity(self):
        self.account()
        with app.connect() as db:
            self.put(db,'secondary','contacts',dict(name='Other',email='PERSON@example.test',phone='555',links=['deal']))
            self.put(db,'linked','companies',dict(name='Linked',links=['secondary','contact']))
            db.execute('INSERT INTO activities VALUES(?,?,?,?)',('note','secondary',json.dumps(dict(type='Note',text='Keep this')),'now'))
            crm_tools.merge(db,dict(source_id='secondary',target_id='contact'))
            primary=json.loads(db.execute("SELECT body FROM records WHERE id='contact'").fetchone()[0])
            self.assertEqual('SAMPLE — Contact',primary['name']);self.assertEqual('555',primary['phone']);self.assertEqual(['deal'],primary['links'])
            self.assertEqual(['contact'],json.loads(db.execute("SELECT body FROM records WHERE id='linked'").fetchone()[0])['links'])
            self.assertEqual('contact',db.execute("SELECT record_id FROM activities WHERE id='note'").fetchone()[0])
            self.assertIsNone(db.execute("SELECT id FROM records WHERE id='secondary'").fetchone())
            with self.assertRaises(ValueError):crm_tools.merge(db,dict(source_id='deal',target_id='contact'))
    def test_merge_email_dedup_keeps_log(self):
        self.account();test_mail.MailTest.message(self)
        with app.connect() as db:
            self.put(db,'secondary','contacts',dict(name='Secondary',email='person@example.test'))
            for ident in ('contact','secondary'):
                db.execute('INSERT INTO activities VALUES(?,?,?,?)',(ident,ident,json.dumps(dict(type='Email',mail_message_id='message')),'now'))
                db.execute('INSERT INTO mail_logs VALUES(?,?)',('message',ident))
            crm_tools.merge(db,dict(source_id='secondary',target_id='contact'))
            self.assertEqual(1,db.execute("SELECT count(*) FROM activities WHERE json_extract(body,'$.mail_message_id')='message'").fetchone()[0])
            self.assertEqual([('message','contact')],[tuple(r) for r in db.execute('SELECT * FROM mail_logs')])
    def test_reminders_and_recurring_completion(self):
        with app.connect() as db:
            self.put(db,'task','tasks',dict(name='SAMPLE task',due_date='2099-01-31',repeat_preference='Monthly'))
            crm_tools.reminder(db,'a',dict(id='task',fingerprint='one',action='snooze'))
            self.assertEqual([],crm_tools.reminders(db,'b')['states'])
            self.assertTrue(crm_tools.reminders(db,'a')['states'][0]['snooze_until'])
            result=crm_tools.complete_task(db,dict(id='task',expected_updated='original'));self.assertEqual('2099-02-28',result['next_date'])
            self.assertEqual([],crm_tools.reminders(db,'a')['states'])
            with self.assertRaises(ValueError):crm_tools.complete_task(db,dict(id='task',expected_updated='original'))
            self.put(db,'once','tasks',dict(name='One'))
            crm_tools.complete_task(db,dict(id='once'));crm_tools.complete_task(db,dict(id='once'))
            self.assertEqual(1,db.execute("SELECT count(*) FROM activities WHERE record_id='once'").fetchone()[0])
    def test_personal_email_does_not_create_company(self):
        with app.connect() as db:
            c,co=self.mail.ensure_correspondents(db,dict(sender='Person <sample@gmail.com>',to='me@example.test',cc='',direction='received'),dict(email='me@example.test',crm_owner='User',owner=self.owner))
            self.assertEqual((1,0),(c,co))
            body=json.loads(db.execute("SELECT body FROM records WHERE json_extract(body,'$.email')='sample@gmail.com'").fetchone()[0]);self.assertEqual('User',body['owner']);self.assertEqual([],body['links'])
    def test_auto_requires_history_and_is_owner_scoped(self):
        self.account(expires=time.time()+600)
        with self.assertRaises(MailError):self.mail.auto_setting(self.owner,dict(account_id='account',enabled=True))
        with app.connect() as db:db.execute("UPDATE mail_accounts SET last_sync='now'")
        self.mail.auto_setting(self.owner,dict(account_id='account',enabled=True))
        with patch.object(self.mail,'call',return_value={'messages':[]}) as request:
            self.mail.auto_tick('other',{});request.assert_not_called()
            self.mail.auto_tick(self.owner,{});self.assertEqual(1,request.call_count)
            self.mail.auto_tick(self.owner,{});self.assertEqual(1,request.call_count)
        self.mail.auto_setting(self.owner,dict(account_id='account',enabled=False))
        with patch.object(self.mail,'call') as request:self.mail.auto_tick(self.owner,{});request.assert_not_called()
    def test_auto_retry_retains_watermark_and_history_selection(self):
        self.account(expires=time.time()+600)
        with app.connect() as db:
            db.execute("UPDATE mail_accounts SET last_sync='now'")
            db.execute('INSERT INTO mail_ranges VALUES(?,?)',('account',json.dumps(dict(preset='7'))))
        self.mail.auto_setting(self.owner,dict(account_id='account',enabled=True))
        with app.connect() as db:before=db.execute('SELECT watermark FROM mail_auto').fetchone()[0]
        with patch.object(self.mail,'call',side_effect=MailError('Unavailable')):self.mail.auto_tick(self.owner,{})
        with app.connect() as db:
            self.assertEqual(before,db.execute('SELECT watermark FROM mail_auto').fetchone()[0]);db.execute('UPDATE mail_auto SET checked=0')
        with patch.object(self.mail,'call',return_value={'messages':[]}):self.mail.auto_tick(self.owner,{})
        with app.connect() as db:self.assertEqual('7',json.loads(db.execute('SELECT selection FROM mail_ranges').fetchone()[0])['preset'])
    def test_google_html_signature_multipart_and_inline_image(self):
        self.account(expires=time.time()+600)
        logo=base64.b64encode(b'sample image').decode()
        self.mail.post('preferences',self.owner,dict(account_id='account',days=30,signature='Signed',signature_html='<b>Signed</b><img src="data:image/png;base64,'+logo+'"><script>bad()</script>'))
        sent=[]
        def call(provider,token,path,data=None):
            if path.startswith('/settings/'):return {'displayName':'User'}
            sent.append(data);return {'id':'sent'}
        with patch.object(self.mail,'call',side_effect=call):self.mail.send(self.owner,dict(account_id='account',to='person@example.test',subject='Test',text='Hello',html='<p><b>Hello</b></p>',send_id='sample-send-id-12345'))
        mime=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(sent[-1]['raw']))
        self.assertIn('Signed',mime.get_body(preferencelist=('plain',)).get_content());html=mime.get_body(preferencelist=('html',)).get_content();self.assertIn('cid:sprocket-',html);self.assertNotIn('bad()',html)
        images=[p for p in mime.walk() if p.get_content_maintype()=='image'];self.assertEqual(1,len(images));self.assertEqual(b'sample image',images[0].get_payload(decode=True))
    def test_microsoft_html_send(self):
        self.account(provider='microsoft',expires=time.time()+600)
        with patch.object(self.mail,'call',return_value={}) as call:
            self.mail.send(self.owner,dict(account_id='account',to='person@example.test',subject='Test',text='Hello',html='<b>Hello</b>',send_id='sample-send-id-12345'))
            body=call.call_args.args[3]['message']['body'];self.assertEqual('HTML',body['contentType']);self.assertIn('<b>Hello</b>',body['content'])

    def test_auto_pagination_batches_and_repeat_deduplication(self):
        self.account(expires=time.time()+600)
        with app.connect() as db:db.execute("UPDATE mail_accounts SET last_sync='now'")
        self.mail.auto_setting(self.owner,dict(account_id='account',enabled=True))
        def provider(provider,token,path,*args):
            if path.startswith('/messages?'):
                if 'pageToken=next' in path:return {'messages':[{'id':str(n)} for n in range(10,25)]}
                return {'messages':[{'id':str(n)} for n in range(10)],'nextPageToken':'next'}
            return {'id':path.split('/')[2].split('?')[0],'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':'person@example.test'},{'name':'To','value':'me@example.test'}],'body':{'data':base64.urlsafe_b64encode(b'SAMPLE message').decode()}},'internalDate':'1000'}
        with patch.object(self.mail,'call',side_effect=provider):
            first=self.mail.auto_tick(self.owner,{});self.assertTrue(first['busy'])
            with app.connect() as db:self.assertEqual(0,db.execute('SELECT count(*) FROM mail_messages').fetchone()[0])
            self.assertTrue(self.mail.auto_tick(self.owner,{})['busy'])
            with app.connect() as db:self.assertEqual(10,db.execute('SELECT count(*) FROM mail_messages').fetchone()[0])
            self.mail.auto_tick(self.owner,{})
            self.assertFalse(self.mail.auto_tick(self.owner,{})['busy'])
            with app.connect() as db:
                self.assertEqual(25,db.execute('SELECT count(*) FROM mail_messages').fetchone()[0]);self.assertEqual(50,db.execute('SELECT count(*) FROM activities').fetchone()[0]);db.execute('UPDATE mail_auto SET checked=0')
            for _ in range(4):self.mail.auto_tick(self.owner,{})
            with app.connect() as db:self.assertEqual(50,db.execute('SELECT count(*) FROM activities').fetchone()[0])
