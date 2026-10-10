import unittest
import record_forms

class RecordFormTest(unittest.TestCase):
    def test_additive_upgrade_preserves_custom_definitions_and_is_idempotent(self):
        custom=dict(key='priority',label='Our priority',type='select',options=['One','Two'])
        settings={'types':[{'id':'deals','fields':[custom]},{'id':'custom','fields':[]}], 'pipelines':[]}
        self.assertTrue(record_forms.upgrade(settings))
        self.assertEqual(custom,settings['types'][0]['fields'][0])
        self.assertEqual([],settings['types'][1]['fields'])
        self.assertFalse(record_forms.upgrade(settings))
        self.assertEqual(1,sum(f['key']=='priority' for f in settings['types'][0]['fields']))
        settings['types'][0]['fields']=[custom]
        self.assertFalse(record_forms.upgrade(settings))
        self.assertEqual([custom],settings['types'][0]['fields'])
    def test_all_five_types_have_expected_properties(self):
        settings={'types':[{'id':kind,'fields':[]} for kind in record_forms.FIELDS]}
        record_forms.upgrade(settings)
        keys={t['id']:{f['key'] for f in t['fields']} for t in settings['types']}
        self.assertTrue({'first_name','last_name','job_title','lifecycle_stage','lead_status'} <= keys['contacts'])
        self.assertTrue({'domain','employees','annual_revenue','linkedin_url','time_zone'} <= keys['companies'])
        self.assertTrue({'deal_type','amount','close_date','priority'} <= keys['deals'])
        self.assertTrue({'source','priority','create_date'} <= keys['tickets'])
        self.assertTrue({'task_type','queue','due_date','due_time','priority'} <= keys['tasks'])

    def test_line_item_validation_and_creation_property_persistence(self):
        import json, tempfile
        from pathlib import Path
        from test_server import app
        old=app.DB
        with tempfile.TemporaryDirectory() as folder:
            try:
                app.DB=Path(folder)/'forms.db';app.initialize()
                samples={'contacts':{'first_name':'Sample','last_name':'Person','job_title':'Tester','lifecycle_stage':'Lead'},'companies':{'industry':'Technology','employees':5,'annual_revenue':1000,'time_zone':'America/Edmonton'},'deals':{'amount':100,'deal_type':'New business','line_items':[{'description':'Sample service','quantity':2,'unit_price':50}]},'tickets':{'source':'Email','create_date':'2026-10-10'},'tasks':{'task_type':'Call','due_date':'2026-10-11','due_time':'08:00','reminder_preference':'At due time','repeat_preference':'Weekly'}}
                with app.connect() as db:
                    for kind,props in samples.items():
                        body=dict(props,name='SAMPLE — '+kind,links=[])
                        app.validate_record(db,kind,body)
                        db.execute('INSERT INTO records VALUES(?,?,?,?)',(kind,kind,json.dumps(body),'2026-10-10'))
                    for kind,props in samples.items():
                        saved=json.loads(db.execute('SELECT body FROM records WHERE id=?',(kind,)).fetchone()[0])
                        for key,value in props.items():self.assertEqual(value,saved[key])
                    for value in (0,-1,float('inf')):
                        with self.assertRaises(ValueError):app.validate_record(db,'deals',dict(name='Invalid',line_items=[dict(description='Test',quantity=value,unit_price=1)]))
            finally:app.DB=old
