"""Sidebar edits are per-user, validated and compatible with changing record types."""
import copy
import unittest
from unittest.mock import patch
import navigation_preferences as nav
import test_feature_routes as routes

class NavigationRoutes(unittest.TestCase):
    setUp=routes.FeatureRoutes.setUp
    tearDown=routes.FeatureRoutes.tearDown
    request=routes.FeatureRoutes.request

    def test_member_preferences_are_private_and_persistent(self):
        with patch.object(self.server.RequestHandlerClass,'sso_admin',return_value=False):
            with patch.object(self.server.RequestHandlerClass,'mail_owner',return_value='a'):
                draft={'pins':['Contacts','Reports'],'collapsed':['CRM','Reporting']}
                self.assertEqual(self.request('/api/navigation/preferences',draft),(200,draft))
                routes.app.initialize()
                self.assertEqual(self.request('/api/state')[1]['navigation']['preferences'],draft)
            with patch.object(self.server.RequestHandlerClass,'mail_owner',return_value='b'):
                self.assertEqual(self.request('/api/state')[1]['navigation']['preferences']['pins'],nav.DEFAULT_PINS)

    def test_invalid_payload_and_cross_origin_do_not_write(self):
        self.assertEqual(self.request('/api/navigation/preferences',{'pins':[],'collapsed':[]},False)[0],403)
        for draft in [[],{}, {'pins':['Unknown'],'collapsed':[]},
                      {'pins':['Contacts','Contacts'],'collapsed':[]},
                      {'pins':['Dashboards'],'collapsed':[]},
                      {'pins':['Contacts'],'collapsed':['bad']},
                      {'pins':[{}],'collapsed':[]},
                      {'pins':[],'collapsed':['CRM','CRM']}]:
            self.assertEqual(self.request('/api/navigation/preferences',draft)[0],400)
        self.assertEqual(self.request('/api/state')[1]['navigation']['preferences']['pins'],nav.DEFAULT_PINS)
        self.assertEqual(self.request('/api/navigation/preferences',{'pins':[],'collapsed':[]})[0],200)
        self.assertEqual(self.request('/api/state')[1]['navigation']['preferences']['pins'],[])

    def test_custom_record_retirement_is_pruned(self):
        with routes.app.connect() as db:
            settings=routes.app.load_settings(db)
            settings['types'].append({'id':'projects','name':'Projects','fields':[]})
            saved=nav.save(db,'custom',settings,{'pins':['record:projects','Contacts'],'collapsed':['Custom records']})
            self.assertEqual(saved['pins'][0],'record:projects')
            settings['types']= [t for t in settings['types'] if t['id']!='projects']
            result=nav.load(db,'custom',settings)['preferences']
            self.assertEqual(result,{'pins':['Contacts'],'collapsed':[]})

    def test_catalog_and_static_script(self):
        import urllib.request
        catalog=self.request('/api/state')[1]['navigation']['catalog']
        self.assertIn('Calendar',catalog['Work'])
        self.assertNotIn('Calendar',catalog['Sales'])
        names=[n for items in catalog.values() for n in items]
        self.assertEqual(len(names),len(set(names)))
        with urllib.request.urlopen(self.url+'/navigation.js') as response:
            self.assertIn(b'navSave',response.read())
