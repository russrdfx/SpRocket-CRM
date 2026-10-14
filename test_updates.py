import importlib.util,json,sqlite3,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import updates
class UpdateTests(unittest.TestCase):
    def test_channels_editions_and_semver(self):
        releases=[dict(tag_name='v0.1.8',prerelease=True),dict(tag_name='web-v0.2.0-beta.2',prerelease=True),dict(tag_name='web-v0.2.0-beta.10',prerelease=True),dict(tag_name='web-v0.1.9',prerelease=False),dict(tag_name='web-v9.0.0',draft=True),dict(tag_name='web-vBAD'),dict(tag_name='web-v0.2.0',prerelease=False)]
        self.assertEqual(updates.select_release(releases,'desktop','beta')['version'],'0.1.8')
        self.assertIsNone(updates.select_release(releases,'desktop','stable'))
        self.assertEqual(updates.select_release(releases,'web','stable')['version'],'0.2.0')
        self.assertEqual(updates.select_release(releases[:-1],'web','beta')['version'],'0.2.0-beta.10')
        self.assertGreater(updates.version_key('0.2.0'),updates.version_key('0.2.0-beta.99'))
    def test_release_urls_and_notes_are_not_provider_controlled(self):
        r=updates.select_release([dict(tag_name='web-v0.2.0-beta.2',html_url='https://evil.example',body='<script>evil</script>')],'web','beta')
        self.assertEqual(r['url'],'https://github.com/russrdfx/SpRocket-CRM/releases/tag/web-v0.2.0-beta.2')
        self.assertIn('<script>',r['notes']) # UI escapes notes as plain text.
    def test_cached_checks_failure_and_no_background_network(self):
        with tempfile.TemporaryDirectory() as folder:
            def connect():return sqlite3.connect(folder+'/test.db')
            checker=updates.Updates(connect);checker.initialize()
            with patch('updates.release_info',return_value=dict(version='0.2.0-beta.1',edition='web',build='')),patch('updates.fetch_releases',return_value=[dict(tag_name='web-v0.2.0-beta.2',prerelease=True)]) as fetch:
                self.assertIsNone(checker.status()['checked_at']);fetch.assert_not_called()
                result=checker.check('beta');self.assertTrue(result['update_available'])
                checker.check('beta');self.assertEqual(fetch.call_count,1)
                with self.assertRaises(ValueError):checker.check('evil')
            with patch('updates.release_info',return_value=dict(version='0.1.8',edition='desktop',build='')),patch('updates.fetch_releases',side_effect=OSError('private-secret')):
                result=checker.check('stable');self.assertFalse(result['update_available']);self.assertNotIn('private-secret',result['error'])
    def test_archive_safety_and_contract(self):
        spec=importlib.util.spec_from_file_location('upgrade',Path(__file__).parent/'deploy/upgrade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'test.zip';stage=root/'stage';stage.mkdir()
            with zipfile.ZipFile(archive,'w') as package:package.writestr('repo/../outside','bad')
            with self.assertRaises(ValueError):module.extract(archive,stage)
            with zipfile.ZipFile(archive,'w') as package:
                item=zipfile.ZipInfo('repo/link');item.external_attr=0o120777<<16;package.writestr(item,'target')
            with self.assertRaises(ValueError):module.extract(archive,stage)
            with zipfile.ZipFile(archive,'w') as package:package.writestr('repo/upgrade.json',json.dumps(dict(version='0.2.0-beta.2',database_schema=1,compatible_from=['0.2.0-beta.1'],app_only_rollback=True)))
            module.extract(archive,stage);module.contract(stage,'0.2.0-beta.1','web-v0.2.0-beta.2')
            with self.assertRaises(ValueError):module.contract(stage,'0.3.0','web-v0.2.0-beta.2')
            with self.assertRaises(ValueError):module.resolve('web-v0.2.0;evil')
    def test_upgrade_uses_existing_project_and_only_app(self):
        spec=importlib.util.spec_from_file_location('upgrade',Path(__file__).parent/'deploy/upgrade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cmd=module.compose(Path('/srv/crm'),'existing-project',Path('/srv/crm/.updates/target.json'))
        self.assertEqual(cmd[cmd.index('--project-name')+1],'existing-project')
        self.assertIn('/srv/crm/deploy/.env',cmd)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'override.json';module.override(path,'sha256:sample')
            self.assertEqual(json.loads(path.read_text()),{'services':{'app':{'image':'sha256:sample'}}})

    def test_backup_and_health_failure_restore_previous_app_without_touching_volumes(self):
        import sys,subprocess
        spec=importlib.util.spec_from_file_location('upgrade',Path(__file__).parent/'deploy/upgrade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for failure in ('none','backup','health'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);(root/'deploy').mkdir();(root/'deploy/.env').write_text('SAMPLE=example')
                stage=root/'.updates'/('a'*40);stage.mkdir(parents=True)
                (stage/'upgrade.json').write_text(json.dumps(dict(version='0.2.0-beta.2',database_schema=1,compatible_from=['0.2.0-beta.1'],app_only_rollback=True)))
                calls=[]
                def fake_output(cmd):
                    if 'config' in cmd:return '{"name":"existing"}'
                    if 'inspect' in cmd:return 'sha256:previous'
                    if 'ps' in cmd:return 'existing-container'
                    return '0.2.0-beta.1'
                def fake_run(cmd,**kwargs):
                    calls.append(cmd)
                    if 'pg_dump' in cmd:
                        if failure=='backup':raise subprocess.CalledProcessError(1,cmd)
                        kwargs['stdout'].write(b'PGDMPsample')
                def fake_verify(cmd,version=None):
                    if version and failure=='health':raise ValueError('Failed health')
                with patch.object(module,'resolve',return_value='a'*40),patch.object(module,'output',side_effect=fake_output),patch.object(module,'run',side_effect=fake_run),patch.object(module,'verify',side_effect=fake_verify),patch.object(sys,'argv',['upgrade','--root',folder,'--version','web-v0.2.0-beta.2','--approve']):
                    if failure=='none':module.main()
                    else:
                        with self.assertRaises((ValueError,subprocess.CalledProcessError)):module.main()
                record=json.loads((root/'.updates/last-upgrade.json').read_text())
                self.assertEqual(record['status'],'verified' if failure=='none' else 'app_rolled_back')
                self.assertEqual((root/'deploy/.env').read_text(),'SAMPLE=example')
                self.assertFalse(any('down' in cmd or '--volumes' in cmd for cmd in calls))
                self.assertLess(next(i for i,cmd in enumerate(calls) if 'build' in cmd),next(i for i,cmd in enumerate(calls) if 'stop' in cmd))
                if failure!='none':self.assertEqual(json.loads((root/'.updates/rollback.json').read_text())['services']['app']['image'],'sha256:previous')

    def test_failed_check_preserves_success_and_allows_immediate_retry(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as folder:
            checker=updates.Updates(lambda:sqlite3.connect(folder+'/status.db'));checker.initialize()
            release=dict(tag_name='web-v0.2.0-beta.5',prerelease=True)
            with patch('updates.release_info',return_value=dict(version='0.2.0-beta.4',edition='web',build='')),patch('updates.time.time',side_effect=[1000,1100,1101,1102]):
                with patch('updates.fetch_releases',return_value=[release]):first=checker.check('beta')
                with patch('updates.fetch_releases',side_effect=HTTPError('https://api.github.com',429,'PRIVATE',{},None)):failed=checker.check('beta')
                self.assertEqual(failed['latest'],first['latest']);self.assertEqual(failed['last_successful_at'],1000)
                self.assertIn('temporarily limited',failed['error']);self.assertNotIn('PRIVATE',failed['error'])
                with patch('updates.fetch_releases',return_value=[release]) as fetch:retried=checker.check('beta')
                self.assertFalse(retried['error']);self.assertEqual(fetch.call_count,1)
