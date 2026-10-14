import base64,json,os,re,time,unittest
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
import test_mail as fixtures
import mail_tracking

class TrackingTest(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.MailTest('test_state_pkce_and_wrong_browser_no_token_exchange');self.fixture.setUp();self.mail=self.fixture.mail;self.owner=self.fixture.owner
  self.env=patch.dict(os.environ,{'SPROCKET_WEB':'1','SPROCKET_ORIGIN':'https://crm.example.com'});self.env.start();self.fixture.account(expires=time.time()+600)
 def tearDown(self):self.env.stop();self.fixture.tearDown()
 def send(self,**kw):
  data=dict(account_id='account',send_id='sample_request_123456',to='person@example.test',subject='SAMPLE tracking',text='Sample email',track_opens=True);data.update(kw)
  with patch.object(self.mail,'call',return_value={'id':'remote-sent'}) as call:
   result=self.mail.send(self.owner,data)
  payload=next(c.args[3] for c in call.call_args_list if c.args[2]=='/messages/send')
  parsed=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(payload['raw']))
  return result,parsed
 def enable(self):self.mail.tracking.configure({'enabled':True})
 def token(self,message):return re.search(r'/email-open/([\w-]+)\.gif',message.get_body(preferencelist=('html',)).get_content()).group(1)
 def test_default_off_and_plain_send_unchanged(self):
  self.assertFalse(self.mail.tracking.status(self.owner)['enabled'])
  with self.assertRaises(ValueError):self.send()
  result,m=self.send(track_opens=False);self.assertIsNone(m.get_body(preferencelist=('html',)))
 def test_payload_counts_timestamps_and_private_previews(self):
  self.enable();result,m=self.send();token=self.token(m);self.assertEqual('Sample email\n',m.get_body(preferencelist=('plain',)).get_content())
  with fixtures.app.connect() as db:
   bodies=' '.join(r[0] for r in db.execute('SELECT body FROM mail_messages'));self.assertNotIn(token,bodies)
   self.assertNotIn(token,' '.join(r[0] for r in db.execute('SELECT body FROM activities')))
  self.mail.tracking.hit(token);self.mail.tracking.hit(token)
  item=self.mail.messages(self.owner,'account')[0];self.assertEqual(1,item['tracking']['count']);self.assertEqual(1,len(item['tracking']['opens']))
  with fixtures.app.connect() as db:db.execute('UPDATE mail_tracking SET last_hit=0')
  self.mail.tracking.hit(token);self.assertEqual(2,self.mail.messages(self.owner,'account')[0]['tracking']['count'])
  with fixtures.app.connect() as db:
   activities=[dict(json.loads(r['body'])) for r in db.execute('SELECT body FROM activities')];self.mail.tracking.decorate(db,activities);self.assertEqual(2,activities[0]['email']['tracking']['count'])
  with self.assertRaises(ValueError):self.send()
 def test_paused_expired_unknown_and_owner_boundaries(self):
  self.enable();_,m=self.send();token=self.token(m);self.mail.tracking.configure({'enabled':False});self.mail.tracking.hit(token)
  self.assertEqual(0,self.mail.messages(self.owner,'account')[0]['tracking']['count']);self.enable()
  with fixtures.app.connect() as db:db.execute('UPDATE mail_tracking SET expires=0')
  self.mail.tracking.hit(token);self.mail.tracking.hit('unknown');self.assertEqual(0,self.mail.messages(self.owner,'account')[0]['tracking']['count'])
  self.assertEqual([],self.mail.tracking.status('other')['accounts'])
  with self.assertRaises(ValueError):self.mail.tracking.preference('other',dict(account_id='account',enabled=True))
 def test_contact_exclusion_blocks_send_without_reserving_attempt(self):
  self.enable()
  with fixtures.app.connect() as db:
   record=json.loads(db.execute("SELECT body FROM records WHERE id='contact'").fetchone()[0]);record['email_tracking_disabled']=True;db.execute("UPDATE records SET body=? WHERE id='contact'",(json.dumps(record),))
  with self.assertRaisesRegex(ValueError,'excluded'):self.send()
  self.send(track_opens=False)
 def test_early_request_before_provider_accept_and_uncertain_delivery(self):
  self.enable()
  def call(provider,token,path,*args):
   if path=='/messages/send':
    m=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(args[0]['raw']));self.mail.tracking.hit(self.token(m));return {'id':'sent'}
   return {}
  with patch.object(self.mail,'call',side_effect=call):self.mail.send(self.owner,dict(account_id='account',send_id='sample_early_123456',to='person@example.test',subject='Sample',text='Hello',track_opens=True))
  self.assertEqual(1,self.mail.messages(self.owner,'account')[0]['tracking']['count'])
 def test_sync_sanitization_and_public_origin(self):
  self.assertNotIn('https://crm.example.com',fixtures.safe_email_html('<p>Hello</p><img src="https://crm.example.com/email-open/secret.gif">'))
  for url in ('http://crm.example.com','https://127.0.0.1','https://localhost','https://user:pass@crm.example.com','https://crm.example.com/path'):
   with patch.dict(os.environ,{'SPROCKET_ORIGIN':url}):
    self.assertFalse(mail_tracking.origin())
    with self.assertRaises(ValueError):self.enable()
 def test_preferences_and_microsoft_html(self):
  self.enable();self.mail.tracking.preference(self.owner,dict(account_id='account',enabled=True));self.assertTrue(self.mail.status(self.owner)['tracking']['accounts'][0]['default_enabled'])
  with fixtures.app.connect() as db:db.execute("UPDATE mail_accounts SET provider='microsoft'")
  with patch.object(self.mail,'call',return_value={}) as call:self.mail.send(self.owner,dict(account_id='account',send_id='microsoft_request_123',to='person@example.test',subject='Sample',text='Hi',track_opens=True))
  payload=call.call_args.args[3];self.assertIn('/email-open/',payload['message']['body']['content']);self.assertEqual('HTML',payload['message']['body']['contentType'])
 def test_visible_opens_and_disconnect_preserve_shared_history(self):
  self.enable();_,m=self.send();self.mail.tracking.hit(self.token(m));message=self.mail.messages(self.owner,'account')[0]
  self.assertIn(message['id'],self.mail.tracking.visible_opens('other')['messages']) # Logged activity is shared.
  with fixtures.app.connect() as db:
   db.execute('INSERT INTO mail_messages VALUES(?,?,?,?)',('private','account','private-provider',json.dumps(dict(subject='Private',direction='sent',date='2026-01-01'))))
   private=self.mail.tracking.prepare(db,self.owner,'account','private-request-1234','unknown@example.test',True);self.mail.tracking.accept(db,private,'private')
  self.assertNotIn('private',self.mail.tracking.visible_opens('other')['messages']);self.assertIn('private',self.mail.tracking.visible_opens(self.owner)['messages'])
  self.mail.post('disconnect',self.owner,dict(account_id='account'))
  with fixtures.app.connect() as db:
   bodies=[json.loads(r[0]) for r in db.execute('SELECT body FROM activities')];self.assertEqual(1,bodies[0]['email']['tracking']['count']);self.assertTrue(bodies[0]['email']['tracking']['disconnected']);self.assertFalse(bodies[0]['email']['tracking']['collecting'])
