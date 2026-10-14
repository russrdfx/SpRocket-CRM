import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
import server as app
import followups as f
from mail_service import safe_email_html
class FollowupTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.temp.name)/'sample.db';app.initialize();self.mail=Mock()
  with app.connect() as db:
   for ident,kind,body in [('c','contacts',dict(name='SAMPLE Person',email='sample@example.test',first_name='Morgan',links=['co'])),('co','companies',dict(name='SAMPLE & Company',domain='example.test'))]:db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,kind,json.dumps(body),'before'))
 def tearDown(self):app.DB=self.old;self.temp.cleanup()
 def create(self,**kw):
  data=dict(request_id='sample_request_12345',record_id='c',name='SAMPLE call',due_date='2026-10-20',due_time='10:30',owner='Actor');data.update(kw)
  with app.connect() as db:return f.schedule(db,'user','Actor',data,app.validate_record,self.mail)
 def save(self,owner='user',admin=False,**kw):
  data=dict(name='SAMPLE greeting',subject='Hello {{contact.first_name}}',body='{{company.name}} — {{user.name}}',html='<p>{{company.name}}</p>',scope='personal');data.update(kw)
  with app.connect() as db:return f.save_template(db,owner,data,admin,safe_email_html)
 def test_schedule_context_owner_reminder_and_idempotency(self):
  result=self.create();self.assertEqual(result['id'],self.create()['id'])
  with app.connect() as db:
   row=db.execute("SELECT * FROM records WHERE kind='tasks'").fetchone();body=json.loads(row['body']);self.assertEqual('Actor',body['owner']);self.assertEqual(['c','co'],body['links']);self.assertEqual('At due time',body['reminder_preference']);self.assertEqual(2,db.execute('SELECT COUNT(*) FROM activities').fetchone()[0])
 def test_invalid_data_rolls_back_reservation(self):
  for props in ({'due_time':'25:00'},{'due_date':'2026-02-30'},{'owner':'Unknown'},{'record_id':'missing'}):
   with self.assertRaises(ValueError):self.create(**props)
  with app.connect() as db:self.assertEqual(0,db.execute('SELECT COUNT(*) FROM followup_requests').fetchone()[0])
  self.create()
 def test_email_owner_access_is_checked(self):
  self.mail.message.side_effect=ValueError('Not your mailbox')
  with self.assertRaises(ValueError):self.create(record_id=None,message_id='private')
  self.mail.message.assert_called_once()
 def test_reschedule_stale_guard_and_reminders_reset(self):
  ident=self.create()['id']
  with app.connect() as db:
   row=db.execute('SELECT * FROM records WHERE id=?',(ident,)).fetchone();db.execute('INSERT INTO reminder_state VALUES(?,?,?,?,?)',('user',ident,'old','',1))
  with app.connect() as db:f.reschedule(db,dict(id=ident,expected_updated=row['updated'],due_date='2026-10-21',due_time='11:00'),app.validate_record)
  with app.connect() as db:
   self.assertFalse(db.execute('SELECT * FROM reminder_state').fetchone())
   with self.assertRaises(ValueError):f.reschedule(db,dict(id=ident,expected_updated=row['updated'],due_date='2026-10-22',due_time='11:00'),app.validate_record)
 def test_template_visibility_and_placeholders(self):
  ident=self.save()['id']
  with app.connect() as db:
   self.assertEqual([],f.templates(db,'other')['templates'])
   rendered=f.render_template(db,'user','Actor',dict(id=ident,email='sample@example.test'),safe_email_html);self.assertEqual('Hello Morgan',rendered['subject']);self.assertIn('SAMPLE &amp; Company',rendered['html']);self.assertEqual([],rendered['missing'])
   absent=f.render_template(db,'user','Actor',dict(id=ident,email='absent@example.test'),safe_email_html);self.assertIn('contact.first_name',absent['missing'])
   with self.assertRaises(ValueError):f.render_template(db,'other','Other',dict(id=ident,email='sample@example.test'),safe_email_html)
 def test_shared_permissions_stale_edits_and_sanitization(self):
  with self.assertRaises(ValueError):self.save(scope='workspace')
  result=self.save(admin=True,scope='workspace',html='<script>bad()</script><p>Hello</p><img src="https://bad.test/pixel">')
  with app.connect() as db:
   t=f.templates(db,'other')['templates'][0];self.assertFalse(t['can_edit']);self.assertNotIn('bad()',t['html']);self.assertNotIn('https://bad',t['html'])
  with self.assertRaises(ValueError):self.save(owner='other',id=result['id'],expected_updated=t['updated'],delete=True)
  with self.assertRaises(ValueError):self.save(admin=True,id=result['id'],expected_updated='stale')
  for value in ('{{unknown}}','{{contact.bad}}','{{unfinished'):
   with self.assertRaises(ValueError):self.save(body=value)
 def test_duplicate_contact_match_is_not_guessed(self):
  ident=self.save()['id']
  with app.connect() as db:
   db.execute('INSERT INTO records VALUES(?,?,?,?)',('c2','contacts',json.dumps(dict(name='Second',email='sample@example.test',first_name='Jamie')),'before'))
   rendered=f.render_template(db,'user','Actor',dict(id=ident,email='sample@example.test'),safe_email_html);self.assertFalse(rendered['contact_matched']);self.assertIn('contact.first_name',rendered['missing'])
 def test_unresolved_placeholders_never_reach_provider(self):
  import test_mail as fixtures
  from unittest.mock import patch
  fixture=fixtures.MailTest('test_state_pkce_and_wrong_browser_no_token_exchange');fixture.setUp()
  try:
   fixture.account(expires=9999999999)
   with patch.object(fixture.mail,'call') as provider:
    for body in ({'text':'Hello {{contact.first_name}}'},{'html':'<a href="https://{{company.domain}}">Site</a>'}):
     data=dict(account_id='account',send_id='sample_unresolved_12345',to='person@example.test',subject='Hello',text='Hello');data.update(body)
     with self.assertRaises(ValueError):fixture.mail.send(fixture.owner,data)
    provider.assert_not_called()
  finally:fixture.tearDown()
