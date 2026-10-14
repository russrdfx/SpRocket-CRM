import json,unittest
from datetime import datetime,timedelta,timezone
import notifications
import test_mail as fixtures

class NotificationTest(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.MailTest('test_state_pkce_and_wrong_browser_no_token_exchange');self.fixture.setUp();self.fixture.account();self.connect=fixtures.app.connect;self.now=datetime.now(timezone.utc)
 def tearDown(self):self.fixture.tearDown()
 def seed_open(self,owner='user-a',event='open1'):
  with self.connect() as db:
   m={'subject':'SAMPLE proposal','to':'Person <person@example.test>','direction':'sent'}
   db.execute('INSERT OR IGNORE INTO mail_messages VALUES(?,?,?,?)',('sent','account','remote',json.dumps(m)))
   db.execute('INSERT OR IGNORE INTO mail_tracking(id,token_hash,owner,account_id,send_id,state,expires,message_id) VALUES(?,?,?,?,?,?,?,?)',('track','hash',owner,'account','request','accepted',9999999999,'sent'))
   db.execute('INSERT INTO mail_tracking_events VALUES(?,?,?)',(event,'track',self.now.isoformat()))
 def task(self,**updates):
  body=dict(name='SAMPLE task',owner='Alice',due_date=self.now.date().isoformat(),due_time='09:00',reminder_preference='At due time');body.update(updates)
  with self.connect() as db:db.execute("INSERT INTO records VALUES('task','tasks',?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",(json.dumps(body),self.now.isoformat()))
  return body
 def feed(self,owner='user-a',aliases=('Alice',),offset=0,now=None):
  with self.connect() as db:return notifications.feed(db,owner,aliases,offset,now or self.now)
 def test_private_opens_dedup_and_read_persist(self):
  self.seed_open();a=self.feed();self.assertEqual(a['unread'],1);self.assertEqual(self.feed('user-b')['items'],[]);self.assertNotIn('hash',json.dumps(a));self.assertNotIn('body',a['items'][0])
  with self.connect() as db:notifications.save(db,'user-b',{'action':'read','ids':['open:open1']})
  self.assertEqual(self.feed()['unread'],1)
  with self.connect() as db:notifications.save(db,'user-a',{'action':'read','ids':['open:open1']})
  self.assertEqual(self.feed()['unread'],0);self.assertEqual(len(self.feed()['items']),1)
 def test_tracking_owner_and_account_owner_must_both_match(self):
  self.seed_open(owner='user-b');self.assertEqual(self.feed()['items'],[]);self.assertEqual(self.feed('user-b')['items'],[])
 def test_multiple_opens_have_distinct_alerts(self):
  self.seed_open();self.seed_open(event='open2');self.assertEqual(self.feed()['unread'],2)
 def test_preferences_filter_without_mutating_other_users(self):
  self.seed_open();self.feed()
  with self.connect() as db:notifications.save(db,'user-a',{'action':'preferences','preferences':dict(notifications.DEFAULTS,email_open=False)})
  self.assertEqual(self.feed()['items'],[])
  with self.connect() as db:notifications.save(db,'user-a',{'action':'preferences','preferences':notifications.DEFAULTS})
  self.assertEqual(self.feed()['unread'],1)
 def test_preferences_reject_partial_or_non_boolean(self):
  with self.connect() as db:
   for p in ({'desktop':True},dict(notifications.DEFAULTS,desktop='yes')):
    with self.assertRaises(ValueError):notifications.save(db,'user-a',{'action':'preferences','preferences':p})
 def test_due_timezone_owner_completion_and_reschedule(self):
  self.task();day=self.now.replace(hour=14,minute=59,second=0,microsecond=0)
  self.assertEqual(self.feed(offset=360,now=day)['items'],[])
  self.assertEqual(self.feed(offset=360,now=day+timedelta(minutes=1))['unread'],1)
  self.assertEqual(self.feed('user-b',('Bob',),360,day+timedelta(minutes=1))['items'],[])
  self.task(due_date=(day+timedelta(days=1)).date().isoformat());self.assertEqual(self.feed(offset=360,now=day+timedelta(minutes=1))['items'],[])
  self.task(completed=True);self.assertEqual(self.feed(now=day+timedelta(days=2))['items'],[])
 def test_reminder_dismiss_and_snooze_respected(self):
  task=self.task();legacy=json.dumps([task['due_date'],task['due_time'],task['reminder_preference']],separators=(',',':'));now=self.now.replace(hour=23)
  with self.connect() as db:db.execute('INSERT INTO reminder_state VALUES(?,?,?,?,?)',('user-a','task',legacy,(now+timedelta(minutes=15)).isoformat(),0))
  self.assertEqual(self.feed(now=now)['items'],[]);self.assertEqual(self.feed(now=now+timedelta(minutes=16))['unread'],1)
  with self.connect() as db:db.execute("UPDATE reminder_state SET dismissed=1 WHERE task_id='task'")
  self.assertEqual(self.feed(now=now+timedelta(minutes=16))['items'],[])
 def test_incoming_skips_history_sent_and_duplicates(self):
  with self.connect() as db:
   notifications.preferences(db,'user-a')
   for ident,direction,date in [('historical','received',self.now-timedelta(days=1)),('sent','sent',self.now+timedelta(minutes=1)),('new','received',self.now+timedelta(minutes=1))]:
    m=dict(id=ident,direction=direction,date=date.isoformat(),subject='SAMPLE inbox');notifications.incoming(db,'user-a',m);notifications.incoming(db,'user-a',m)
  self.assertEqual(self.feed()['unread'],1);self.assertEqual(self.feed()['items'][0]['message_id'],'new')
 def test_invalid_actions_offset_and_ids(self):
  with self.connect() as db:
   for d in ([],{'action':'remove'},{'action':'read','ids':['x']*1001}):
    with self.assertRaises(ValueError):notifications.save(db,'user-a',d)
   with self.assertRaises(ValueError):notifications.feed(db,'user-a',[],9999)

if __name__=='__main__':unittest.main()
