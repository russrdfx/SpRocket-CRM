const fs=require('fs'),vm=require('vm'),assert=require('assert');
const banners=[],pending=[];const content={prepend(b){b.isConnected=true;banners.push(b)}};
const c=vm.createContext({state:null,page:'dashboard',settingsView(){},dashRender(){for(const b of banners)b.isConnected=false},dashboard(){},$:s=>content,document:{createElement(){return {hidden:false,isConnected:false,innerHTML:'',querySelector(){return {}},remove(){this.isConnected=false}}}},api:()=>new Promise(resolve=>pending.push(resolve))});
vm.runInContext(fs.readFileSync('web/onboarding.js','utf8'),c);c.state={auth:{is_admin:true}};
vm.runInContext('dashRender();dashRender()',c);
(async()=>{for(const resolve of pending)resolve({progress:{hidden:false},required_done:1,required_total:5});await Promise.resolve();assert.equal(banners.filter(b=>b.isConnected&&!b.hidden).length,1,'Calendar repaint must leave exactly one visible setup reminder');assert.ok(banners[1].innerHTML.includes('1 of 5 essentials'));
 const before=pending.length;c.state.auth.is_admin=false;vm.runInContext('dashRender()',c);assert.equal(pending.length,before,'Members must not request administrator setup status');console.log('Setup reminder survives async dashboard repaint and remains administrator-only');})().catch(e=>{console.error(e);process.exitCode=1});
