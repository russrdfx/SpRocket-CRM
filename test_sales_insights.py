import json,sqlite3,unittest
from datetime import datetime,timezone,timedelta
import sales_insights as sales
class SalesInsightsTest(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.execute('CREATE TABLE records(id TEXT PRIMARY KEY,kind TEXT,body TEXT,updated TEXT)');sales.initialize(self.db)
  self.settings=dict(currency='CAD',pipelines=[dict(id='p',name='Sales',kind='deals',stages=[dict(id='open',name='Open',probability=.2),dict(id='won',name='Success',outcome='won',probability=1),dict(id='lost',name='Lost',probability=0)])])
 def tearDown(self):self.db.close()
 def put(self,ident,stage,**kwargs):self.db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?)',(ident,'deals',json.dumps(dict(name=ident,pipeline='p',stage=stage,**kwargs)),'2020-01-01'))
 def test_snapshot_baseline_and_outcomes(self):
  now=datetime.now(timezone.utc);self.put('a','open',amount=100);self.put('b','won',amount=500);self.put('c','lost',amount=50,loss_reason='Budget')
  data=sales.insights(self.db,self.settings,now);self.assertEqual(data['summary']['weighted_open'],20);self.assertEqual(data['summary']['win_rate'],50)
  row=self.db.execute("SELECT * FROM deal_observations WHERE deal_id='a'").fetchone();self.assertEqual(row['baseline'],1);self.assertEqual(row['entered'],now.isoformat())
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM deal_transitions').fetchone()[0],0)
  self.put('a','open',amount=200);data=sales.insights(self.db,self.settings,now+timedelta(hours=1));self.assertEqual(data['summary']['weighted_open'],40);self.assertEqual(data['snapshots'][0]['weighted_open'],20)
  data=sales.insights(self.db,self.settings,now+timedelta(days=1));self.assertEqual(len(data['snapshots']),2);self.assertEqual(data['loss_reasons'][0]['reason'],'Budget')
 def test_stage_observation_idempotence(self):
  now=datetime.now(timezone.utc).isoformat()
  for stage in ('open','open','won'):sales.observe(self.db,'new',dict(pipeline='p',stage=stage),now)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM deal_transitions').fetchone()[0],1);self.assertEqual(self.db.execute('SELECT baseline FROM deal_observations').fetchone()[0],0)
