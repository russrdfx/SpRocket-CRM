const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({Date,Number,JSON,Boolean,Map,Set,shell:()=>{},state:null,esc:String});
vm.runInContext(fs.readFileSync(__dirname+'/web/dashboard.js','utf8'),ctx);
const prefs=JSON.parse(vm.runInContext('JSON.stringify(dashDefaults)',ctx));
const data={auth:{profile:{name:'Sample User'}},mail:{accounts:[{email:'sample@example.test'}]},settings:{pipelines:[{id:'p',stages:[{id:'zero',name:'Lead',probability:0},{id:'one',name:'Negotiation',probability:1},{id:'won',name:'Closed Won',probability:1},{id:'lost',name:'Closed Lost',probability:0}]}]},records:[
 {id:'t1',kind:'tasks',owner:'Sample User',due_date:'2026-10-12'},
 {id:'t2',kind:'tasks',owner:'someone else',due_date:'2026-10-13'},
 {id:'t3',kind:'tasks',owner:'',due_date:'2026-10-13'},
 {id:'t4',kind:'tasks',owner:'Sample User',completed:true},
 {id:'c1',kind:'contacts',updated:'2026-10-13'}, {id:'c2',kind:'contacts'},
 ...['zero','one','won','lost'].map((stage,i)=>({id:'d'+i,kind:'deals',pipeline:'p',stage,amount:100,updated:'2026-09-01',close_date:'2026-10-20'}))
],activities:[
 {id:'a1',record_id:'d0',type:'Email',mail_message_id:'m',created:'2026-10-13'},
 {id:'a2',record_id:'c1',type:'Email',mail_message_id:'m',created:'2026-10-13'},
 {id:'a3',record_id:'c1',type:'Email',mail_message_id:'m',created:'2026-10-13'}
]};
const calendar={events:[{title:'Today',start:'2026-10-13',end:'2026-10-14'}, {title:'Tomorrow',start:'2026-10-14',end:'2026-10-15'},{title:'Cancelled',start:'2026-10-13',end:'2026-10-14',status:'cancelled'},{title:'Old',start:'2026-10-12',end:'2026-10-13'}]};
const now=new Date('2026-10-13T12:00:00');
const model=ctx.dashModel(data,prefs,calendar,now);
assert.equal(model.tasks.length,2);assert.equal(model.overdue.length,1);assert.equal(model.todayTasks.length,1);
assert.equal(model.open.length,2,'0% and 100% open stages must remain open');assert.equal(model.won.length,1);assert.equal(model.weighted,100);assert.equal(model.value,200);assert.equal(model.closing.length,2);
assert.equal(model.followups.length,1);assert.equal(model.followups[0].id,'c2');assert.equal(model.conversations.length,1);assert.equal(model.conversations[0].record_id,'c1');
assert.equal(model.events.length,2);assert.equal(ctx.dashModel(data,{...prefs,meeting_days:1,task_scope:'all'},calendar,now).events.length,1);
assert.equal(ctx.dashModel(data,{...prefs,task_scope:'all'},calendar,now).tasks.length,3);
const link=ctx.feedbackEmail('Bug report','Subject & test','Details\nwith lines',{version:'0.2.0',edition:'web',build:'abc'});
assert.ok(link.startsWith('mailto:russ@rdfx.ca?'));assert.ok(link.includes('Subject%20%26%20test'));assert.ok(decodeURIComponent(link).includes('SpRocket CRM 0.2.0 (web)'));assert.ok(!link.includes('sample@example.test'));
console.log('Dashboard task ownership, dates, terminal stages, activity deduplication and feedback encoding passed');
