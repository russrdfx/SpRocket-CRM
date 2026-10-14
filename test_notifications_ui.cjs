const fs=require('fs'),vm=require('vm'),assert=require('assert');
const notices=[],storage=new Map();let response={items:[],unread:0,preferences:{desktop:true}};
class FakeNotification{constructor(title,options){notices.push({title,options})}}
FakeNotification.permission='granted';
const context=vm.createContext({console,Date,Set,Object,Number,String,JSON,encodeURIComponent,Notification:FakeNotification,state:{auth:{user:{subject:'sample-user'}}},$:()=>null,shell(){},settingsView(){},document:{addEventListener(){}},setTimeout(){return 1},clearTimeout(){},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},api:async()=>JSON.parse(JSON.stringify(response))});
vm.runInContext(fs.readFileSync('web/notifications.js','utf8'),context);
const check=()=>vm.runInContext('notificationCheck()',context);
(async()=>{
 response.items=[{id:'old-open',read:false,title:'Email opened',detail:'SAMPLE prior proposal'}];await check();assert.equal(notices.length,0,'Initial load must not flood the desktop');
 response.items.unshift({id:'new-open',read:false,title:'Email opened',detail:'SAMPLE current proposal'});await check();assert.equal(notices.length,1);assert.equal(notices[0].options.body,'SAMPLE current proposal');await check();assert.equal(notices.length,1,'Repeated polls must not repeat alerts');
 vm.runInContext('notificationSeen=new Set()',context);await check();assert.equal(notices.length,2,'Previously unseen old entry gets one alert');await check();assert.equal(notices.length,2,'Browser receipt suppresses duplicates');
 response.items.unshift({id:'already-read',read:true,title:'Email opened',detail:'SAMPLE read'});await check();assert.equal(notices.length,2);
 response.preferences.desktop=false;response.items.unshift({id:'muted',read:false,title:'Email opened',detail:'SAMPLE muted'});await check();assert.equal(notices.length,2);
 response.preferences.desktop=true;FakeNotification.permission='denied';response.items.unshift({id:'blocked',read:false,title:'Email opened',detail:'SAMPLE blocked'});await check();assert.equal(notices.length,2);
 console.log('Notification desktop baseline, read/mute/permission guards and duplicate suppression passed');
})().catch(e=>{console.error(e);process.exitCode=1});
