const fs=require('fs'),vm=require('vm'),assert=require('assert'),source=fs.readFileSync('web/app.js','utf8');
let route='',edited=null;const state={activities:[{id:'copy-company',record_id:'co',mail_message_id:'same-mail',created:'2026-10-14T12:00:00Z'},{id:'copy-contact',record_id:'c',mail_message_id:'same-mail',created:'2026-10-14T12:00:00Z'},{id:'note',record_id:'co',created:'2026-10-14T13:00:00Z'},{id:'unrelated',record_id:'other',created:'2026-10-14T14:00:00Z'}]};
const c=vm.createContext({state,go:value=>route=value,recordModal:r=>edited=r});
vm.runInContext(source.slice(source.indexOf('function openRecord('),source.indexOf('function dealDetails(')),c);
c.openRecord({id:'co',kind:'companies'});assert.equal(route,'company:co');assert.equal(edited,null,'Viewing company must not open editor');
c.openRecord({id:'c',kind:'contacts'});assert.equal(route,'contact:c');c.openRecord({id:'d',kind:'deals'});assert.equal(route,'deal:d');
vm.runInContext(source.slice(source.indexOf('function companyActivityRows('),source.indexOf('function companyDetails(')),c);
assert.deepEqual(Array.from(c.companyActivityRows({id:'co'},[{id:'c'}]),a=>a.id),['note','copy-company'],'Related mail is deduplicated and unrelated activities excluded');
console.log('Company view routing, related activity scope and email deduplication passed');
