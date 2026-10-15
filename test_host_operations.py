import importlib.util,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import web_operations
spec=importlib.util.spec_from_file_location('verified_backup',Path(__file__).parent/'deploy/verified_backup.py');backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
class HostOperationsTest(unittest.TestCase):
 def test_backup_restore_failure_and_cleanup(self):
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def run(cmd,**kwargs):
    calls.append(cmd);return SimpleNamespace(returncode=0,stdout=b'archive' if 'pg_dump' in cmd else b'1' if 'psql' in cmd else b'',stderr=b'')
   result=backup.backup(folder,Path(folder)/'backups',run);self.assertTrue(result['restore_verified']);self.assertTrue(any('dropdb' in c for c in calls));self.assertTrue((Path(folder)/'backups'/result['backup_file']).exists())
   receipt=Path(folder)/'backups/latest-verified-backup.json';original=receipt.read_bytes()
   def fail(cmd,**kwargs):
    if 'pg_restore' in cmd and '--dbname' in cmd:return SimpleNamespace(returncode=1,stdout=b'',stderr=b'PRIVATE ERROR')
    return run(cmd,**kwargs)
   with self.assertRaises(RuntimeError) as error:backup.backup(folder,Path(folder)/'backups',fail)
   self.assertNotIn('PRIVATE',str(error.exception));self.assertEqual(receipt.read_bytes(),original)
 def test_worker_health_and_receipt(self):
  with tempfile.TemporaryDirectory() as folder:
   def connect():
    db=sqlite3.connect(Path(folder)/'ops.db');db.row_factory=sqlite3.Row;return db
   with connect() as db:web_operations.initialize(db)
   self.assertEqual(web_operations.status(connect,False)['state'],'disabled');self.assertEqual(web_operations.status(connect,True)['state'],'not_started')
   web_operations.started(connect);web_operations.finished(connect,1);self.assertEqual(web_operations.status(connect,True)['state'],'attention')
   web_operations.finished(connect,0);self.assertEqual(web_operations.status(connect,True)['state'],'running')
   with patch('web_operations.time.time',return_value=9999999999):self.assertEqual(web_operations.status(connect,True)['state'],'stale')
   receipt=Path(folder)/'receipt.json';receipt.write_text('{"restore_verified":false}')
   with patch.dict('os.environ',{'SPROCKET_BACKUP_RECEIPT':str(receipt)}):self.assertEqual(web_operations.status(connect,False)['backup']['state'],'unavailable')
