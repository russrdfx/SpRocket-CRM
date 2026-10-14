import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
import enrichment_service as es
import record_forms

class EnrichmentTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db';self.cipher=Fernet(Fernet.generate_key());self.service=es.EnrichmentService(self.connect,lambda:self.cipher)
  with self.connect() as db:
   db.executescript('CREATE TABLE settings(body TEXT);CREATE TABLE records(id TEXT PRIMARY KEY,kind TEXT,body TEXT,updated TEXT);CREATE TABLE activities(id TEXT,record_id TEXT,body TEXT,created TEXT);')
   settings={'types':[{'id':k,'fields':[]} for k in ('contacts','companies')]};record_forms.upgrade(settings);db.execute('INSERT INTO settings VALUES(?)',(json.dumps(settings),));self.service.initialize(db)
   for ident,kind,body in [('c','contacts',dict(name='SAMPLE Person',email='sample@example.com')),('co','companies',dict(name='SAMPLE Company',domain='example.com'))]:db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,kind,json.dumps(body),'before'))
 def tearDown(self):self.temp.cleanup()
 def connect(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row;return db
 def validate(self,db,kind,body):
  if not body.get('name'):raise ValueError('Name required')
 def config(self,**kw):
  value=es.defaults();value.update(api_key='sample-secret',enabled=True,**kw);return self.service.configure(value)
 def preview(self,csv='email,job_title\nsample@example.com,Designer',mapping=None):return self.service.csv_preview('owner',dict(kind='contacts',source='Apollo',csv=csv,mapping=mapping or {'email':'email','job_title':'job_title'}),self.validate)
 def apply(self,p,fields=['job_title'],**kw):return self.service.apply('owner','Sample',dict(selections=[dict(preview_id=p['preview_id'],record_id='c',fields=fields)],match_confirmed=True,**kw),self.validate)
 def body(self):
  with self.connect() as db:return json.loads(db.execute("SELECT body FROM records WHERE id='c'").fetchone()[0])
 def test_encrypted_config_and_verification(self):
  status=self.config();self.assertNotIn('sample-secret',json.dumps(status))
  with self.connect() as db:self.assertNotIn('sample-secret',str(dict(db.execute('SELECT * FROM enrichment_config').fetchone())))
  with patch.object(es,'apollo_request',return_value={'healthy':True,'is_logged_in':True}):self.assertTrue(self.service.verify()['config']['verified_at'])
  for mapping in ({'owner':'owner'}, {'job_title':False},{'name':'name','job_title':'name'}):
   d=es.defaults();d['mapping']['contacts']=mapping
   with self.assertRaises(ValueError):self.service.configure(d)
 def test_lookup_consent_quota_cache_and_phone_flags(self):
  self.config(daily_limit=1);response={'person':{'name':'Sample Person','title':'Designer'},'match_confidence':'high'}
  with self.assertRaises(ValueError):self.service.lookup('owner',{'id':'c'},self.validate)
  with patch.object(es,'apollo_request',return_value=response) as request:
   p=self.service.lookup('owner',{'id':'c','confirmed':True},self.validate)
   self.assertEqual('false',request.call_args.args[2]['reveal_phone_number']);self.assertEqual('false',request.call_args.args[2]['reveal_personal_emails'])
   self.assertEqual(p['preview_id'],self.service.lookup('owner',{'id':'c','confirmed':True},self.validate)['preview_id']);self.assertEqual(1,request.call_count)
   with self.assertRaises(ValueError):self.service.lookup('other',{'id':'co','confirmed':True},self.validate)
  self.assertEqual(1,self.service.status()['attempts_today'])
 def test_no_match_does_not_invent_fields(self):
  self.assertEqual(({},None),es.canonical('contacts',{'person':{},'match_confidence':'none'}))
  values,candidate=es.canonical('contacts',{'person':{'name':'Sample','phone':'123','email':None}});self.assertNotIn('phone',values);self.assertEqual('not provided',candidate['confidence'])
 def test_csv_unique_only_and_no_creation(self):
  p=self.preview('email,job_title\nsample@example.com,Designer\nmissing@example.com,CEO\nsample@example.com,CEO');self.assertEqual(1,len(p['items']));self.assertEqual(2,len(p['errors']))
  with self.connect() as db:db.execute('INSERT INTO records VALUES(?,?,?,?)',('duplicate','contacts',json.dumps(self.body()),'before'))
  self.assertFalse(self.preview()['preview_id'])
 def test_fill_review_history_and_guarded_undo(self):
  p=self.preview();receipt=self.apply(p)['receipts'][0];self.assertEqual('Designer',self.body()['job_title'])
  with self.connect() as db:
   body=self.body();body['notes']='Later unrelated note';db.execute("UPDATE records SET body=?,updated='new' WHERE id='c'",(json.dumps(body),))
  with self.assertRaises(ValueError):self.service.undo('other','Other',{'id':receipt,'confirmed':True},self.validate)
  self.service.undo('owner','Sample',{'id':receipt,'confirmed':True},self.validate);self.assertNotIn('job_title',self.body());self.assertEqual('Later unrelated note',self.body()['notes']);self.assertTrue(self.service.history('owner','c')['history'][0]['undone'])
 def test_undo_never_overwrites_newer_enriched_field(self):
  receipt=self.apply(self.preview())['receipts'][0]
  with self.connect() as db:
   body=self.body();body['job_title']='New edit';db.execute("UPDATE records SET body=?,updated='new' WHERE id='c'",(json.dumps(body),))
  with self.assertRaises(ValueError):self.service.undo('owner','Sample',{'id':receipt,'confirmed':True},self.validate)
  self.assertEqual('New edit',self.body()['job_title'])
 def test_stale_preview_and_owner(self):
  p=self.preview()
  with self.assertRaises(ValueError):self.service.apply('other','Other',dict(selections=[dict(preview_id=p['preview_id'],record_id='c',fields=['job_title'])],match_confirmed=True),self.validate)
  with self.connect() as db:db.execute("UPDATE records SET updated='new' WHERE id='c'")
  with self.assertRaises(ValueError):self.apply(p)
  self.assertNotIn('job_title',self.body())
 def test_overwrite_is_explicit_and_admin_policy(self):
  self.apply(self.preview());p=self.preview('email,job_title\nsample@example.com,CEO')
  with self.assertRaises(ValueError):self.apply(p)
  self.config(fill_only=True)
  with self.assertRaises(ValueError):self.apply(p,overwrite=True)
  self.config(fill_only=False);self.apply(p,overwrite=True);self.assertEqual('CEO',self.body()['job_title'])
 def test_linkedin_and_additive_migration(self):
  self.assertEqual('https://www.linkedin.com/in/sample',es.linkedin_url('linkedin.com/in/sample?utm=x','contacts'))
  for value in ('https://evil.com/in/person','javascript:alert(1)','https://linkedin.com/company/person'):
   with self.assertRaises(ValueError):es.linkedin_url(value,'contacts')
  s={'creation_schema_version':3,'types':[{'id':'contacts','fields':[]}]};record_forms.upgrade(s);keys={f['key'] for f in s['types'][0]['fields']};self.assertIn('linkedin_url',keys);self.assertNotIn('phone',keys);self.assertFalse(record_forms.upgrade(s))
 def test_batch_transaction_rolls_back(self):
  p=self.preview('email,job_title\nsample@example.com,Designer')
  with self.connect() as db:db.execute('INSERT INTO records VALUES(?,?,?,?)',('c2','contacts',json.dumps(dict(name='Second',email='second@example.com')),'before'))
  p2=self.service.csv_preview('owner',dict(kind='contacts',csv='email,job_title\nsecond@example.com,CEO',mapping={'email':'email','job_title':'job_title'}),self.validate)
  with self.connect() as db:db.execute("UPDATE records SET updated='changed' WHERE id='c2'")
  selections=[dict(preview_id=p['preview_id'],record_id='c',fields=['job_title']),dict(preview_id=p2['preview_id'],record_id='c2',fields=['job_title'])]
  with self.assertRaises(ValueError):self.service.apply('owner','Sample',dict(selections=selections,match_confirmed=True),self.validate)
  self.assertNotIn('job_title',self.body());self.assertEqual([],self.service.history('owner','c')['history'])
 def test_transport_uses_header_key_and_blocks_redirects(self):
  from urllib.error import HTTPError
  opener=unittest.mock.MagicMock();opener.open.side_effect=HTTPError('https://api.apollo.io',302,'Redirect',{},None)
  with patch.object(es,'build_opener',return_value=opener) as build:
   with self.assertRaisesRegex(ValueError,'could not complete'):es.apollo_request('sample-secret','people/match',{'email':'sample@example.com'})
   request=opener.open.call_args.args[0];self.assertNotIn('sample-secret',request.full_url);self.assertEqual('sample-secret',request.get_header('X-api-key'));self.assertIsInstance(build.call_args.args[0],es.NoRedirect)
 def test_numeric_estimates_and_invalid_csv_mapping(self):
  p=self.service.csv_preview('owner',dict(kind='companies',csv='domain,employees,estimated_annual_revenue\nexample.com,"1,200",50000',mapping={'domain':'domain','employees':'employees','estimated_annual_revenue':'estimated_annual_revenue'}),self.validate)
  item=p['items'][0];self.assertEqual(1200,item['suggestions']['employees']);self.assertTrue(item['details']['employees']['estimated'])
  with self.assertRaises(ValueError):self.service.csv_preview('owner',dict(kind='contacts',csv='email\nsample@example.com',mapping={'email':False}),self.validate)
