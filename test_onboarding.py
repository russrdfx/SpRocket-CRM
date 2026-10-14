import json,unittest
import onboarding
import test_mail as fixtures
class OnboardingTest(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.MailTest('test_state_pkce_and_wrong_browser_no_token_exchange');self.fixture.setUp();self.connect=fixtures.app.connect
 def tearDown(self):self.fixture.tearDown()
 def status(self,owner='user-a'):
  with self.connect() as db:return onboarding.status(db,owner,json.loads(db.execute('SELECT body FROM settings').fetchone()[0]))
 def save(self,data,owner='user-a'):
  with self.connect() as db:return onboarding.save(db,owner,data)
 def test_progress_requires_review_and_records_derived(self):
  first=self.status();self.assertEqual(first['required_done'],1)
  for step in onboarding.REVIEWED:self.save(dict(action='reviewed',step=step,enabled=True))
  self.assertEqual(self.status()['required_done'],5);self.assertEqual(self.status('user-b')['required_done'],1)
  with self.connect() as db:
   settings=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);settings['pipelines']=[];db.execute('UPDATE settings SET body=?',(json.dumps(settings),))
  self.assertEqual(self.status()['required_done'],4,'Deleting reviewed configuration must reopen the step')
 def test_optional_connections_private_and_skip_reversible(self):
  self.fixture.account();self.assertTrue(next(s for s in self.status()['steps'] if s['id']=='email')['done'])
  self.assertFalse(next(s for s in self.status('user-b')['steps'] if s['id']=='email')['done'])
  self.save(dict(action='skipped',step='calendar',enabled=True));self.assertTrue(next(s for s in self.status()['steps'] if s['id']=='calendar')['skipped'])
  self.save(dict(action='skipped',step='calendar',enabled=False));self.assertFalse(next(s for s in self.status()['steps'] if s['id']=='calendar')['skipped'])
 def test_hidden_personal_and_validation(self):
  self.save(dict(action='hidden',enabled=True));self.assertTrue(self.status()['progress']['hidden']);self.assertFalse(self.status('user-b')['progress']['hidden'])
  for data in ([],{},dict(action='reviewed',step='records',enabled=True),dict(action='skipped',step='backup',enabled=True),dict(action='hidden',enabled='yes')):
   with self.assertRaises(ValueError):self.save(data)
 def test_progress_does_not_mutate_workspace(self):
  with self.connect() as db:before=db.execute('SELECT body FROM settings').fetchone()[0];records=db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
  self.save(dict(action='reviewed',step='pipeline',enabled=True))
  with self.connect() as db:self.assertEqual(before,db.execute('SELECT body FROM settings').fetchone()[0]);self.assertEqual(records,db.execute('SELECT COUNT(*) FROM records').fetchone()[0])
class StageOutcomeTest(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.MailTest('test_state_pkce_and_wrong_browser_no_token_exchange');self.fixture.setUp()
 def tearDown(self):self.fixture.tearDown()
 def test_explicit_outcomes_validate_and_preserve_other_configuration(self):
  with fixtures.app.connect() as db:
   original=json.loads(db.execute('SELECT body FROM settings').fetchone()[0]);settings=json.loads(json.dumps(original))
   for outcome in ('open','won','lost'):
    settings['pipelines'][0]['stages'][0]['outcome']=outcome
    fixtures.app.validate_settings(settings,original,db.execute('SELECT * FROM records').fetchall())
   settings['pipelines'][0]['stages'][0]['outcome']='maybe'
   with self.assertRaises(ValueError):fixtures.app.validate_settings(settings,original,db.execute('SELECT * FROM records').fetchall())
if __name__=='__main__':unittest.main()
