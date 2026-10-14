"""Dashboard preferences must remain private and resist invalid layouts."""
import copy
import unittest
from unittest.mock import patch
import dashboard_preferences as prefs
import test_feature_routes as routes

class DashboardRoutes(unittest.TestCase):
    setUp = routes.FeatureRoutes.setUp
    tearDown = routes.FeatureRoutes.tearDown
    request = routes.FeatureRoutes.request
    def test_member_preferences_are_private_and_persist(self):
        with patch.object(self.server.RequestHandlerClass, 'sso_admin', return_value=False):
            with patch.object(self.server.RequestHandlerClass, 'mail_owner', return_value='member-a'):
                draft=copy.deepcopy(prefs.DEFAULTS)
                draft.update(default_tab='sales',density='compact',side_panel=False)
                draft['widgets']['sales']=['stalled','pipeline']
                self.assertEqual(self.request('/api/dashboard/preferences',draft),(200,draft))
                self.assertEqual(self.request('/api/state')[1]['dashboard'],draft)
            with patch.object(self.server.RequestHandlerClass, 'mail_owner', return_value='member-b'):
                self.assertEqual(self.request('/api/state')[1]['dashboard'],prefs.DEFAULTS)
            with patch.object(self.server.RequestHandlerClass, 'mail_owner', return_value='member-a'):
                self.assertEqual(self.request('/api/state')[1]['dashboard'],draft)
    def test_layout_validation_and_origin(self):
        self.assertEqual(self.request('/api/dashboard/preferences',prefs.DEFAULTS,False)[0],403)
        for replacement in ({'widgets':{'daily':['tasks','tasks'],'sales':[],'relationships':[]}},
                            {'widgets':{'daily':['conversations'],'sales':[],'relationships':[]}},
                            {'default_tab':[]},{'meeting_days':True},{'side_panel':'false'},
                            {'inactive_days':0}):
            draft=copy.deepcopy(prefs.DEFAULTS);draft.update(replacement)
            self.assertEqual(self.request('/api/dashboard/preferences',draft)[0],400)
        self.assertEqual(self.request('/api/state')[1]['dashboard'],prefs.DEFAULTS)
    def test_dashboard_script_is_served(self):
        import urllib.request
        with urllib.request.urlopen(self.url+'/dashboard.js') as response:
            self.assertIn(b'dashModel',response.read())

    def test_default_sales_pipeline_is_editable_and_not_reseeded(self):
        settings=self.request('/api/state')[1]['settings']
        pipeline=settings['pipelines'][0]
        self.assertEqual(pipeline['kind'],'deals')
        self.assertEqual([(s['name'],s['probability']) for s in pipeline['stages']],
                         [('Lead',.1),('Demo Booked',.2),('Demo Completed',.4),('Proposal Sent',.65),('Closed Won',1),('Closed Lost',0)])
        pipeline['name']='Our sales process';pipeline['stages'][0]['name']='Qualified'
        self.assertEqual(self.request('/api/settings',settings)[0],200)
        routes.app.initialize()
        self.assertEqual(self.request('/api/state')[1]['settings']['pipelines'][0]['name'],'Our sales process')
        settings['pipelines']=[]
        self.assertEqual(self.request('/api/settings',settings)[0],200)
        routes.app.initialize()
        self.assertEqual(self.request('/api/state')[1]['settings']['pipelines'],[])

