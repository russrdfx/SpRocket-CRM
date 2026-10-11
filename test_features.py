import base64,json,os,socket,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
import server as app
import workspace_tools,enrichment,automation
from calendar_service import SCOPE

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=app.DB;app.DB=Path(self.temp.name)/'fixture.db';app.initialize();self.owner='fixture-owner'
    def tearDown(self):app.DB=self.previous;self.temp.cleanup()
    def record(self,kind,body,ident=None,days=0):
        ident=ident or str(uuid.uuid4());now=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        with app.connect() as db:
            app.validate_record(db,kind,body);db.execute('INSERT INTO records VALUES(?,?,?,?)',(ident,kind,json.dumps(body),now))
        return ident
    def preview(self,csv,mode='fill',kind='contacts',mapping=None):
        with app.connect() as db:return workspace_tools.preview_import(db,self.owner,dict(kind=kind,csv=csv,mode=mode,mapping=mapping or {'Email':'email','Name':'name','Phone':'phone'}),app.validate_record)
    def apply(self,ident,owner=None):
        with app.connect() as db:return workspace_tools.apply_import(db,owner or self.owner,{'id':ident},app.validate_record)
    def body(self,ident):
        with app.connect() as db:return json.loads(db.execute('SELECT body FROM records WHERE id=?',(ident,)).fetchone()[0])
    def test_saved_views_are_private(self):
        with app.connect() as db:
            view=workspace_tools.save_view(db,self.owner,dict(kind='deals',name='My stale deals',filters={'inactive_days':30}))
            self.assertEqual(len(workspace_tools.views(db,self.owner)['views']),1);self.assertEqual(workspace_tools.views(db,'other')['views'],[])
            with self.assertRaises(ValueError):workspace_tools.save_view(db,'other',dict(id=view['id'],kind='deals',name='Hijack',filters={}))
    def test_csv_preview_no_mutation_and_dedup(self):
        preview=self.preview('Email,Name,Phone\na@example.test,A,123\n');self.assertTrue(preview['ready'])
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
        self.assertEqual(self.apply(preview['id'])['counts']['create'],1);self.assertTrue(self.apply(preview['id'])['existing'])
    def test_csv_fill_and_explicit_update(self):
        ident=self.record('contacts',dict(name='Original',email='a@example.test',phone=''))
        self.apply(self.preview('Email,Name,Phone\na@example.test,Replacement,123')['id']);self.assertEqual(self.body(ident)['name'],'Original');self.assertEqual(self.body(ident)['phone'],'123')
        self.apply(self.preview('Email,Name,Phone\na@example.test,Replacement,999','update')['id']);self.assertEqual(self.body(ident)['name'],'Replacement')
    def test_csv_invalid_row_blocks_all(self):
        preview=self.preview('Email,Name,Phone\na@example.test,A,123\nnot-an-email,B,456');self.assertFalse(preview['ready'])
        with self.assertRaises(ValueError):self.apply(preview['id'])
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
    def test_csv_owner_and_stale_protection(self):
        ident=self.record('contacts',dict(name='A',email='a@example.test'));preview=self.preview('Email,Name,Phone\na@example.test,A,123')
        with self.assertRaises(ValueError):self.apply(preview['id'],'other')
        with app.connect() as db:db.execute('UPDATE records SET updated=? WHERE id=?',('future',ident))
        with self.assertRaises(ValueError):self.apply(preview['id'])
    def test_csv_ambiguous_duplicate_and_same_file(self):
        self.record('contacts',dict(name='A',email='a@example.test'));self.record('contacts',dict(name='B',email='a@example.test'));self.assertFalse(self.preview('Email,Name,Phone\na@example.test,C,123')['ready'])
        self.assertFalse(self.preview('Email,Name,Phone\nb@example.test,B,123\nb@example.test,C,456')['ready'])
    def test_csv_relationship_and_formula_escape(self):
        company=self.record('companies',dict(name='=SUM(1)',domain='example.test'));preview=self.preview('Email,Company\na@example.test,example.test',mapping={'Email':'email','Company':'company_domain'});self.apply(preview['id']);self.assertIn(company,self.body(preview['rows'][0]['id'])['links'])
        with app.connect() as db:export=workspace_tools.export_csv(db,{'kind':'companies'});self.assertIn("'=SUM(1)",export['csv'])
    def test_csv_number_and_checkbox(self):
        preview=self.preview('Name,Completed\nTask,false',kind='tasks',mapping={'Name':'name','Completed':'completed'});self.apply(preview['id']);self.assertIs(self.body(preview['rows'][0]['id'])['completed'],False)
        bad=self.preview('Name,Amount\nDeal,NaN',kind='deals',mapping={'Name':'name','Amount':'amount'});self.assertFalse(bad['ready'])
    def enrichment_job(self,ident,html):
        with patch('enrichment.website',return_value=('https://example.test/',html)),app.connect() as db:return enrichment.preview(db,self.owner,{'id':ident})
    def test_enrichment_review_fill_provenance(self):
        ident=self.record('companies',dict(name='Existing',domain='example.test'))
        preview=self.enrichment_job(ident,'<script type="application/ld+json">{"@type":"Organization","name":"Published","address":{"addressLocality":"Town"}}</script>');self.assertEqual(self.body(ident)['name'],'Existing')
        with app.connect() as db:
            with self.assertRaises(ValueError):enrichment.apply(db,self.owner,dict(preview_id=preview['preview_id'],fields=['name']),app.validate_record)
        with app.connect() as db:enrichment.apply(db,self.owner,dict(preview_id=preview['preview_id'],fields=['city']),app.validate_record)
        self.assertEqual(self.body(ident)['city'],'Town');self.assertEqual(self.body(ident)['enrichment_source'],'https://example.test/')
    def test_enrichment_personal_domain_and_private_network(self):
        ident=self.record('contacts',dict(name='Private',email='a@gmail.com'))
        with app.connect() as db,self.assertRaises(ValueError):enrichment.preview(db,self.owner,{'id':ident})
        for ip in ['127.0.0.1','10.1.2.3','169.254.169.254','::1']:
            with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]),self.assertRaises(ValueError):enrichment.PublicHTTPS('example.test').connect()
    def test_enrichment_contact_creates_company_only_after_review(self):
        ident=self.record('contacts',dict(name='Person',email='person@example.test',links=[]));preview=self.enrichment_job(ident,'<script type="application/ld+json">{"@type":"Organization","name":"Published"}</script>')
        with app.connect() as db,self.assertRaises(ValueError):enrichment.apply(db,self.owner,dict(preview_id=preview['preview_id'],fields=['name']),app.validate_record)
        with app.connect() as db:result=enrichment.apply(db,self.owner,dict(preview_id=preview['preview_id'],fields=['name'],create_company=True),app.validate_record)
        self.assertIn(result['id'],self.body(ident)['links']);self.assertEqual(self.body(result['id'])['name'],'Published')
    def setup_rule(self,trigger='stage',enabled=True):
        pipeline=dict(id='p',name='Fixture pipeline',kind='deals',stages=[dict(id='a',name='Qualified',probability=.5),dict(id='b',name='Proposal',probability=.7),dict(id='c',name='Closed won',probability=1)])
        with app.connect() as db:
            settings=app.load_settings(db);settings['pipelines']=[pipeline];db.execute('UPDATE settings SET body=?',(json.dumps(settings),));return automation.save(db,dict(name='Follow up',title='Call {deal}',pipeline='p',trigger=trigger,stage='b',days=7,due=3,enabled=enabled))
    def test_stage_rule_only_transition_once(self):
        self.setup_rule();ident=self.record('deals',dict(name='Sample',pipeline='p',stage='a',owner='Owner'));old=self.body(ident);new=dict(old,stage='b')
        with app.connect() as db:
            automation.stage_changed(db,ident,None,new,'created',app.validate_record);automation.stage_changed(db,ident,old,old,'same',app.validate_record);self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE kind='tasks'").fetchone()[0],0)
            automation.stage_changed(db,ident,old,new,'changed',app.validate_record);automation.stage_changed(db,ident,old,new,'changed',app.validate_record)
            task=json.loads(db.execute("SELECT body FROM records WHERE kind='tasks'").fetchone()[0]);self.assertEqual(task['owner'],'Owner');self.assertEqual(task['links'],[ident]);self.assertEqual(db.execute('SELECT COUNT(*) FROM automation_runs').fetchone()[0],1)
    def test_inactivity_preview_closed_exclusion_and_dedup(self):
        self.setup_rule('inactive');ident=self.record('deals',dict(name='Stale',pipeline='p',stage='a'),days=10);self.record('deals',dict(name='Won',pipeline='p',stage='c'),days=10)
        with app.connect() as db:
            self.assertEqual(automation.inactive(db,app.validate_record,True)['count'],1);self.assertEqual(db.execute('SELECT COUNT(*) FROM automation_runs').fetchone()[0],0)
            self.assertEqual(automation.inactive(db,app.validate_record)['count'],1);self.assertEqual(automation.inactive(db,app.validate_record)['count'],0)
    def test_disabled_rule_creates_nothing(self):
        self.setup_rule('inactive',False);self.record('deals',dict(name='Stale',pipeline='p',stage='a'),days=10)
        with app.connect() as db:self.assertEqual(automation.inactive(db,app.validate_record)['count'],0)
    def calendar_account(self):
        with app.connect() as db:db.execute('INSERT INTO calendar_accounts VALUES(?,?,?,?)',('calendar',self.owner,'me@example.test','fixture-token'))
    def test_calendar_owner_scope_and_reviewed_logging(self):
        self.calendar_account();contact=self.record('contacts',dict(name='Person',email='person@example.test'));deal=self.record('deals',dict(name='Deal',links=[contact]));event=dict(title='Meeting',start='2026-10-11',end='2026-10-12',attendees=['person@example.test'],status='confirmed',visibility='private')
        with app.connect() as db:db.execute('INSERT INTO calendar_events VALUES(?,?,?)',('calendar','event',json.dumps(event)))
        self.assertEqual(app.CALENDAR.status('other')['events'],[])
        with self.assertRaises(ValueError):app.CALENDAR.log('other',dict(account_id='calendar',event_id='event'))
        result=app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'));self.assertEqual(result['logged'],2);self.assertEqual(app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'))['logged'],0)
    def test_calendar_pagination_and_cancel_updates_logged_entry(self):
        self.calendar_account();contact=self.record('contacts',dict(name='Person',email='person@example.test'));items=dict(items=[dict(id='event',summary='Meeting',start={'date':'2026-10-11'},end={'date':'2026-10-12'},attendees=[{'email':'person@example.test'}])],nextPageToken='provider-page')
        request=dict(account_id='calendar',start='2026-10-01',end='2026-10-31')
        with patch.object(app.CALENDAR,'access',return_value='token'),patch('calendar_service.remote',return_value=items):result=app.CALENDAR.sync(self.owner,request)
        self.assertTrue(result['next_page']);app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'))
        with patch.object(app.CALENDAR,'access',return_value='token'),patch('calendar_service.remote',return_value={'items':[dict(id='event',status='cancelled')]}):app.CALENDAR.sync(self.owner,dict(request,page_token=result['next_page']))
        with app.connect() as db:self.assertIn('cancelled',json.loads(db.execute('SELECT body FROM activities WHERE record_id=?',(contact,)).fetchone()[0])['text'])
    def test_calendar_scopes_are_separate(self):
        with patch.dict(os.environ,dict(GOOGLE_MAIL_CLIENT_ID='fixture',GOOGLE_MAIL_CLIENT_SECRET='fixture')) ,patch.object(app.CALENDAR,'cipher'):
            config=app.CALENDAR.config();self.assertIn(SCOPE,config['scopes']);self.assertNotIn('gmail.',config['scopes']);self.assertTrue(config['redirect'].endswith('/calendar/callback/google'))
    def test_backup_restore_and_safety_copy(self):
        original=self.record('contacts',dict(name='Original',email='a@example.test'));download=app.RECOVERY.download();extra=self.record('contacts',dict(name='Later',email='b@example.test'));preview=app.RECOVERY.preview(self.owner,download,app.validate_settings,app.validate_record)
        with self.assertRaises(ValueError):app.RECOVERY.apply('other',dict(id=preview['id'],confirm='RESTORE'))
        result=app.RECOVERY.apply(self.owner,dict(id=preview['id'],confirm='RESTORE'));self.assertTrue((app.DB.parent/'backups'/result['safety_backup']).is_file());self.assertEqual(self.body(original)['name'],'Original')
        with app.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM records WHERE id=?',(extra,)).fetchone())
    def test_restore_stale_and_invalid_file(self):
        backup=app.RECOVERY.download();preview=app.RECOVERY.preview(self.owner,backup,app.validate_settings,app.validate_record);self.record('contacts',dict(name='New'))
        with self.assertRaises(ValueError):app.RECOVERY.apply(self.owner,dict(id=preview['id'],confirm='RESTORE'))
        with self.assertRaises(ValueError):app.RECOVERY.preview(self.owner,dict(data=base64.b64encode(b'bad').decode()),app.validate_settings,app.validate_record)
    def test_csv_import_rolls_back_on_late_stale_row(self):
        first=self.record('contacts',dict(name='First',email='first@example.test'));second=self.record('contacts',dict(name='Second',email='second@example.test'));preview=self.preview('Email,Name,Phone\nfirst@example.test,First,123\nsecond@example.test,Second,456')
        with app.connect() as db:db.execute('UPDATE records SET updated=? WHERE id=?',('future',second))
        with self.assertRaises(ValueError):self.apply(preview['id'])
        self.assertNotIn('phone',self.body(first))
    def test_restore_rejects_unsafe_schema(self):
        import sqlite3
        backup=app.RECOVERY.snapshot();path=Path(self.temp.name)/'altered.db';path.write_bytes(backup)
        with sqlite3.connect(path) as db:db.execute('CREATE TRIGGER bad AFTER INSERT ON records BEGIN DELETE FROM records; END;')
        with self.assertRaises(ValueError):app.RECOVERY.preview(self.owner,{'data':base64.b64encode(path.read_bytes()).decode()},app.validate_settings,app.validate_record)
    def test_enrichment_ambiguous_organizations(self):
        with self.assertRaises(ValueError):enrichment.facts('<script type="application/ld+json">[{"@type":"Organization","name":"One"},{"@type":"Organization","name":"Two"}]</script>')
    def test_calendar_bad_continuation_rejected(self):
        self.calendar_account()
        with patch.object(app.CALENDAR,'access',return_value='token'),self.assertRaises(ValueError):app.CALENDAR.sync(self.owner,dict(account_id='calendar',start='2026-10-01',end='2026-10-31',page_token='arbitrary-provider-token'))
    def test_calendar_logs_survive_contact_merge(self):
        import crm_tools
        self.calendar_account();one=self.record('contacts',dict(name='One',email='same@example.test'));two=self.record('contacts',dict(name='Two',email='same@example.test'));event=dict(title='Meeting',start='2026-10-11',end='2026-10-12',attendees=['same@example.test'],status='confirmed',visibility='default')
        with app.connect() as db:db.execute('INSERT INTO calendar_events VALUES(?,?,?)',('calendar','event',json.dumps(event)))
        self.assertEqual(app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'))['logged'],2)
        with app.connect() as db:crm_tools.merge(db,dict(source_id=one,target_id=two))
        self.assertEqual(app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'))['logged'],0)
        with app.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM activities WHERE record_id=? AND body LIKE '%calendar_event%'",(two,)).fetchone()[0],1)
    def test_calendar_disconnect_erases_token_and_cache_retains_log_identity(self):
        self.calendar_account();contact=self.record('contacts',dict(name='Person',email='person@example.test'));event=dict(title='Meeting',start='2026-10-11',end='2026-10-12',attendees=['person@example.test'])
        with app.connect() as db:db.execute('INSERT INTO calendar_events VALUES(?,?,?)',('calendar','event',json.dumps(event)))
        app.CALENDAR.log(self.owner,dict(account_id='calendar',event_id='event'));app.CALENDAR.disconnect(self.owner,dict(account_id='calendar'))
        self.assertEqual(app.CALENDAR.status(self.owner)['accounts'],[]);self.assertEqual(app.CALENDAR.status(self.owner)['events'],[])
        with app.connect() as db:self.assertEqual(db.execute('SELECT tokens FROM calendar_accounts').fetchone()[0],'');self.assertEqual(db.execute('SELECT COUNT(*) FROM calendar_logs').fetchone()[0],1)
