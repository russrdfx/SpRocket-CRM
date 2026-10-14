/* Shared personal inbox for Google and Microsoft. HTML email is isolated in a sandbox with remote content blocked. */
let mailAccount='', mailMessages=[], mailSearch='', mailSelected='', mailGeneration=0;
async function mailView(target=$('#content')){
 const generation=++mailGeneration;
 target.innerHTML='<h1>Personal inbox</h1><p>Loading connections…</p>';
 try{
  const config=await api('/api/mail');
  if(generation!==mailGeneration||!target.isConnected)return;
  if(!config.accounts.some(a=>a.id===mailAccount))mailAccount=config.accounts[0]?.id||'';
  const account=config.accounts.find(a=>a.id===mailAccount);
  target.innerHTML=`<div class="heading"><div><h1>Personal inbox</h1><p>Google and Microsoft mail, connected to your CRM.</p></div><button id="mail-compose" ${account?'':'disabled'}>Compose email</button></div>${!state.auth?.enabled?'<p class="mail-notice">Local demo: connected mail is available to anyone using this local workspace. Enable SSO for separate personal inboxes.</p>':'<p class="muted">Your cached inbox is private to your sign-in identity. Synced messages are automatically logged on matching contacts and linked deals, and are visible to the workspace.</p>'}<section class="panel"><h2>Email connections</h2><div class="grid">${config.providers.map(p=>`<div><h3>${esc(p.label)}</h3><p>${p.ready?'Ready to connect':esc(p.reason)}</p><button data-mail-connect="${p.id}" ${p.ready?'':'disabled'}>Connect ${p.id==='google'?'Google':'Microsoft'}</button></div>`).join('')}</div><details><summary>What access does this need?</summary><p>Read email and send messages when you press Send. No delete or mailbox editing permission is requested. Connecting does not import messages until you choose a date range and press Import. Sync creates missing contacts and companies from correspondent email domains and logs messages on their CRM records. You can disconnect here and revoke permission at your provider.</p><p>Setup instructions: EMAIL.md in the project documentation. Provider credentials and the encryption key are configured on the server.</p></details></section>${account?`<section class="panel"><div class="toolbar"><label for="mail-account">Account</label><select id="mail-account">${config.accounts.map(a=>`<option value="${esc(a.id)}" ${a.id===mailAccount?'selected':''}>${esc(a.email)} · ${esc(a.provider)}</option>`).join('')}</select><button id="mail-sync">Import email…</button><button id="mail-auto" ${account.last_sync?'':'disabled title="Import your chosen history first"'}>${account.auto?.enabled?'Pause automatic sync':'Enable automatic sync'}</button><button id="mail-preferences">Sender & signature</button><button id="mail-disconnect">Disconnect</button></div><p id="mail-sync-status" role="status">${account.last_sync?'Last synced '+esc(new Date(account.last_sync).toLocaleString()):'Not synced yet.'}${account.auto?.enabled?' · Automatic sync: '+esc(account.auto.status)+(account.auto.error?' · '+esc(account.auto.error):''):' · Automatic sync paused'}</p><input id="mail-search" aria-label="Search cached emails" placeholder="Search cached emails" value="${esc(mailSearch)}"><div class="mail-layout"><div id="mail-list"></div><div id="mail-detail"></div></div></section>`:'<section class="panel"><h2>Connect your first inbox</h2><p>Configure a Google or Microsoft app on the server, then connect your account above. Sync logs email on matching contacts and linked deals. Missing contacts are created automatically. Business email domains create companies; personal email domains remain individual contacts.</p></section>'}<p class="error" id="mail-error" role="alert"></p>`;
  target.querySelectorAll('[data-mail-connect]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const next=await api('/api/mail/connect',{provider:b.dataset.mailConnect});location.href=next.url}catch(e){$('#mail-error').textContent=e.message;b.disabled=false}});
  if(!account)return;
  $('#mail-compose').onclick=()=>mailCompose(account);
  $('#mail-account').onchange=e=>{mailAccount=e.target.value;mailSelected='';mailView(target)};
  $('#mail-sync').onclick=()=>mailImport(account,target);
  $('#mail-auto').onclick=async e=>{e.target.disabled=true;try{await api('/api/mail/auto',{account_id:account.id,enabled:!account.auto?.enabled});await mailView(target);scheduleProductivity(100)}catch(err){$('#mail-error').textContent=err.message;e.target.disabled=false}};
  $('#mail-preferences').onclick=()=>{
   const modal=$('#modal');modal.innerHTML=`<form id="mail-prefs"><h2>Sender & signature</h2><p>Use the sender name from your connected account, or enter an override for CRM messages. This does not change your provider settings. Microsoft sender names are managed by Microsoft.</p><label for="mail-sender-name">Sender name override (optional)</label><input name="sender_name" id="mail-sender-name" ${account.provider==='microsoft'?'disabled':''} maxlength="200" value="${esc(account.sender_name)}"><p id="mail-sender-status" role="status">${esc(account.provider_name?'Provider name: '+account.provider_name:'Provider name is checked when sending. Your CRM profile name is the fallback.')}</p><button type="button" id="mail-refresh-identity">Check sender name</button><label for="signature-format">Signature format</label><select id="signature-format"><option value="rich">Rich text / HTML</option><option value="plain">Plain text</option></select><div id="signature-editor"></div><label for="mail-signature" id="signature-plain-label">Plain-text signature</label><textarea name="signature" id="mail-signature" maxlength="2000">${esc(account.signature)}</textarea><p>Added to outgoing messages. Format text, add links, or upload a small logo. Remote images are excluded.</p><p class="error" id="mail-prefs-error"></p><div class="actions"><button type="button" id="mail-prefs-cancel">Cancel</button><button>Save</button></div></form>`;
   const editor=richEditor($('#signature-editor'),account.signature_html||plainHTML(account.signature),'Signature');const format=$('#signature-format');format.value=account.signature_html?'rich':'plain';const toggle=()=>{const rich=format.value==='rich';$('#signature-editor').hidden=!rich;$('#mail-signature').hidden=rich;$('#signature-plain-label').hidden=rich};format.onchange=()=>{if(format.value==='rich')editor.set(plainHTML($('#mail-signature').value));else $('#mail-signature').value=editor.text();toggle()};toggle();
   $('#mail-prefs-cancel').onclick=()=>modal.close();$('#mail-prefs').onsubmit=async e=>{e.preventDefault();try{await api('/api/mail/preferences',{account_id:mailAccount,days:account.days,sender_name:e.target.sender_name.value,signature:format.value==='rich'?editor.text():e.target.signature.value,signature_html:format.value==='rich'?editor.html():''});modal.close();mailView(target)}catch(err){$('#mail-prefs-error').textContent=err.message}};$('#mail-refresh-identity').onclick=async e=>{e.target.disabled=true;try{const identity=await api('/api/mail/identity',{account_id:account.id});$('#mail-sender-status').textContent='Effective sender: '+(identity.name?identity.name+' <'+identity.email+'>':identity.email)}catch(err){$('#mail-prefs-error').textContent=err.message}finally{e.target.disabled=false}};modal.showModal();
  };
  $('#mail-disconnect').onclick=async()=>{if(!confirm('Disconnect this inbox and remove its cached messages and stored credentials? CRM activity logs and follow-up tasks will remain. Also revoke app access at Google or Microsoft if desired.'))return;try{await api('/api/mail/disconnect',{account_id:mailAccount});mailSelected='';mailView(target)}catch(err){$('#mail-error').textContent=err.message}};
  mailMessages=(await api('/api/mail/messages?account_id='+encodeURIComponent(mailAccount))).messages;
  if(generation!==mailGeneration||!target.isConnected)return;
  $('#mail-search').oninput=e=>{mailSearch=e.target.value;mailList(account)};mailList(account);
 }catch(e){if(generation===mailGeneration&&target.isConnected)target.innerHTML=`<h1>Personal inbox</h1><p class="error">${esc(e.message)}</p>`}
}
function mailImport(account,target){
 const modal=$('#modal'),saved=account.import_range||{preset:String(account.days)},today=new Date().toISOString().slice(0,10);
 let preview=null,busy=false,cancelled=false;
 modal.innerHTML=`<form id="mail-import-form"><h2>Import email</h2><p>Choose a date range before importing. Dates include the entire day in UTC. Existing messages and activity logs will not be duplicated.</p><label for="mail-range">Time frame</label><select id="mail-range">${[['7','Last 7 days'],['30','Last 30 days'],['90','Last 90 days'],['custom','Custom date range']].map(([v,label])=>`<option value="${v}" ${saved.preset===v?'selected':''}>${label}</option>`).join('')}</select><div id="mail-custom-range"><label for="mail-range-start">Start date</label><input id="mail-range-start" type="date" max="${today}" value="${esc(saved.start||today)}"><label for="mail-range-end">End date</label><input id="mail-range-end" type="date" max="${today}" value="${esc(saved.end||today)}"></div><p>Importing creates missing contacts and companies and logs messages on CRM records visible to the workspace. Previously imported records are kept when you change the range.</p><label class="auto-choice"><input type="checkbox" id="import-auto" checked> Automatically sync new mail while the app is open after this import</label><p id="mail-import-progress" role="status">Preview the range to count matching messages.</p><progress id="mail-import-meter" hidden></progress><p id="mail-import-error" class="error" role="alert"></p><div class="actions"><button type="button" id="mail-import-cancel">Cancel</button><button type="button" id="mail-import-preview">Preview messages</button><button id="mail-import-submit" disabled>Import</button></div></form>`;
 const range=$('#mail-range'),start=$('#mail-range-start'),end=$('#mail-range-end'),previewButton=$('#mail-import-preview'),submit=$('#mail-import-submit'),cancel=$('#mail-import-cancel'),status=$('#mail-import-progress'),meter=$('#mail-import-meter'),error=$('#mail-import-error');
 const selection=()=>({preset:range.value,start:start.value,end:end.value});
 const changed=()=>{preview=null;submit.disabled=true;status.textContent='Preview the range to count matching messages.';$('#mail-custom-range').hidden=range.value!=='custom'};
 [range,start,end].forEach(el=>el.onchange=changed);changed();
 const controls=disabled=>{busy=disabled;[range,start,end,previewButton].forEach(el=>el.disabled=disabled);submit.disabled=disabled||!preview?.ready||!preview.count};
 cancel.onclick=()=>{if(busy){cancelled=true;cancel.disabled=true;status.textContent='Stopping after the current batch…'}else modal.close()};
 modal.oncancel=e=>{if(busy){e.preventDefault();cancel.click()}};
 previewButton.onclick=async()=>{
  controls(true);error.textContent='';cancelled=false;meter.hidden=true;
  try{
   let result=null;
   do{result=await api('/api/mail/preview',{account_id:account.id,...selection(),...(result?{import_id:result.import_id}:{})});status.textContent=`Counting matching messages… ${result.count} found.`}while(!result.ready&&!cancelled);
   if(cancelled){modal.close();return}
   preview=result;status.textContent=`${result.count} matching messages from ${result.selection.start} through ${result.selection.end} (UTC).`;
  }catch(e){error.textContent=e.message;preview=null}finally{controls(false);cancel.disabled=false}
 };
 $('#mail-import-form').onsubmit=async e=>{
  e.preventDefault();if(!preview?.ready||busy)return;
  controls(true);error.textContent='';cancelled=false;meter.hidden=false;meter.max=preview.count;
  let result;
  try{
   do{result=await api('/api/mail/sync',{account_id:account.id,import_id:preview.import_id});meter.value=result.count;status.textContent=`Imported ${result.count} of ${result.total} messages. Created ${result.contacts_created} contacts and ${result.companies_created} companies.`}while(!result.done&&!cancelled);
   if(result.done&&$('#import-auto').checked)await api('/api/mail/auto',{account_id:account.id,enabled:true});
   if(result.done||cancelled){modal.close();state=await api('/api/state');state.auth=await api('/api/auth');state.mail=await api('/api/mail');if(page==='inbox'){await mailView(target);const summary=target.querySelector('#mail-sync-status');if(summary)summary.textContent=`${result.done?'Import complete':'Import stopped'}: ${result.count} of ${result.total} messages. Created ${result.contacts_created} contacts and ${result.companies_created} companies.`}}
  }catch(e){error.textContent=e.message+' You can retry Import to continue; completed batches are kept.'}finally{controls(false);cancel.disabled=false}
 };
 modal.showModal();
}
function mailList(account){
 const rows=mailMessages.filter(m=>[m.subject,m.sender,m.to,m.text].join(' ').toLowerCase().includes(mailSearch.toLowerCase()));
 $('#mail-list').innerHTML=rows.map(m=>`<button class="mail-row ${m.id===mailSelected?'selected':''}" data-mail-message="${esc(m.id)}"><b>${esc(m.subject)}</b><span>${esc(m.direction==='sent'?'To: '+m.to:m.sender)}</span><small>${esc(new Date(m.date).toLocaleString())} · ${m.matches.length} matched records</small></button>`).join('')||'<p>No cached messages match. Choose Import email to select a date range.</p>';
 document.querySelectorAll('[data-mail-message]').forEach(b=>b.onclick=()=>{mailSelected=b.dataset.mailMessage;mailList(account)});
 const m=mailMessages.find(m=>m.id===mailSelected);
 if(!m){$('#mail-detail').innerHTML='<p>Select a message to view its details.</p>';return}
 $('#mail-detail').innerHTML=`<h2>${esc(m.subject)}</h2><p><b>From:</b> ${esc(m.sender)}<br><b>To:</b> ${esc(m.to)}${m.cc?'<br><b>Cc:</b> '+esc(m.cc):''}</p><small>${esc(new Date(m.date).toLocaleString())}</small>${emailOpenStatus(m)}${emailBody(m)}<div class="actions"><button id="mail-reply" ${m.direction==='sent'?'disabled title="Compose a new message to follow up on sent mail"':''}>Reply</button><button id="mail-task">Create follow-up task</button><button id="mail-log" ${m.matches.length?'':'disabled'}>Log on newly matched records</button></div><p class="muted">Synced messages are logged automatically and shared with the workspace. Matched contacts and linked deals:</p>${m.matches.map(r=>`<button data-mail-record="${esc(r.id)}">${esc(r.name)}${m.logged_records.includes(r.id)?' · logged':''}</button>`).join(' ')||'<p>No contacts have a matching email address.</p>'}<p class="error" id="mail-message-error"></p>`;
 document.querySelectorAll('[data-mail-record]').forEach(b=>b.onclick=()=>{const r=state.records.find(r=>r.id===b.dataset.mailRecord);if(r)openRecord(r)});
 $('#mail-reply').onclick=()=>mailCompose(account,m);
 $('#mail-log').onclick=async e=>{e.target.disabled=true;try{const result=await api('/api/mail/log',{message_id:m.id});state=(await api('/api/state'));state.auth=await api('/api/auth');await mailView();toast(`Logged on ${result.count} records`)}catch(err){$('#mail-message-error').textContent=err.message;e.target.disabled=false}};
 $('#mail-task').onclick=()=>{
  const modal=$('#modal');modal.innerHTML=`<form id="mail-task-form"><h2>Follow-up task</h2><label for="mail-task-name">Task name</label><input name="name" id="mail-task-name" required maxlength="300" value="${esc('Follow up: '+m.subject)}"><label for="mail-task-due">Due date</label><input name="due_date" id="mail-task-due" type="date" required><p>Linked to matched contacts and deals. Tasks are visible to the workspace.</p><p class="error" id="mail-task-error"></p><div class="actions"><button type="button" id="mail-task-cancel">Cancel</button><button>Create task</button></div></form>`;
  $('#mail-task-cancel').onclick=()=>modal.close();$('#mail-task-form').onsubmit=async e=>{e.preventDefault();try{const result=await api('/api/mail/task',{message_id:m.id,name:e.target.elements.name.value,due_date:e.target.elements.due_date.value});modal.close();await refresh();toast(result.existing?'This message already has a follow-up task':'Follow-up task created')}catch(err){$('#mail-task-error').textContent=err.message}};modal.showModal();
 };
}
async function mailCompose(account,reply=null,recipient=''){
 if(!account){try{const config=await api('/api/mail');account=config.accounts.find(a=>a.id===mailAccount)||config.accounts[0];if(!account){toast('Connect an email account in Inbox first');go('inbox');return}}catch(e){toast(e.message);return}}
 const modal=$('#modal'),subject=reply?(reply.subject.toLowerCase().startsWith('re:')?reply.subject:'Re: '+reply.subject):'';
 const from=reply?.sender||recipient;
 const parsed=from.match(/<([^>]+)>/),to=parsed?parsed[1]:from;
 const fixed=reply&&account.provider==='microsoft';
 modal.innerHTML=`<form id="mail-send-form"><h2>${reply?'Reply':'Compose email'}</h2><p><b>From:</b> ${esc(account.email)}</p><label for="mail-send-to">To (one recipient)</label><input name="to" id="mail-send-to" type="email" required value="${esc(to)}" ${fixed?'readonly':''}><label for="mail-send-subject">Subject</label><input name="subject" id="mail-send-subject" required maxlength="500" value="${esc(subject)}" ${fixed?'readonly':''}><label for="mail-send-text">Message</label><div id="compose-editor"></div>${account.signature_html||account.signature?'<label>Signature (added automatically)</label>'+emailBody({html:account.signature_html,text:account.signature}):''}<p>Send uses your connected provider. The message is automatically logged on matched CRM contacts and linked deals; missing contacts and domain companies are created.</p>${emailTrackingChoice(account)}<p class="error" id="mail-send-error" role="alert"></p><div class="actions"><button type="button" id="mail-send-cancel">Cancel</button><button class="primary" id="mail-send-button">Send email</button></div></form>`;
 $('#mail-send-cancel').onclick=()=>modal.close();
 const editor=richEditor($('#compose-editor'),'','Message');
 composerTemplates($('#mail-send-form'),editor,fixed).catch(e=>toast(e.message));
 const sendId=uid();
 $('#mail-send-form').onsubmit=async e=>{e.preventDefault();const form=e.target,button=$('#mail-send-button');if(!editor.text().trim()){toast('Enter a message before sending');return}button.disabled=true;button.textContent='Sending…';try{const result=await api('/api/mail/send',{send_id:sendId,account_id:account.id,reply_id:reply?.id||'',to:form.elements.to.value,subject:form.elements.subject.value,text:editor.text(),html:editor.html(),track_opens:!!form.elements.track_opens?.checked});modal.close();mailAccount=account.id;go('inbox');toast(result.message)}catch(err){$('#mail-send-error').textContent=err.message+' If delivery is uncertain, check your provider’s Sent mail before composing again.';button.textContent='Send attempted — check Sent mail';/* Keep disabled: retries can duplicate a successfully delivered message. */}};
 modal.showModal();
}
const mailContactDetails=contactDetails;contactDetails=function(id){mailContactDetails(id);const r=state.records.find(r=>r.id===id);if(!r)return;const parent=$('#contact-edit')?.parentElement;if(parent){const b=document.createElement('button');b.textContent='Send email';b.onclick=()=>mailCompose(null,null,r.email||'');parent.append(b)}};
const mailDealDetails=dealDetails;dealDetails=function(id){mailDealDetails(id);const r=state.records.find(r=>r.id===id);if(!r)return;const related=state.records.filter(c=>c.kind==='contacts'&&((r.links||[]).includes(c.id)||(c.links||[]).includes(r.id)));const parent=$('#deal-edit')?.parentElement;if(parent){const b=document.createElement('button');b.textContent='Send email';b.onclick=()=>mailCompose(null,null,related[0]?.email||'');parent.append(b)}};
const callbackResult=new URLSearchParams(location.search).get('mail');if(callbackResult){page='inbox';history.replaceState(null,'',location.pathname);if(callbackResult==='failed')setTimeout(()=>toast('Email connection failed or permission was declined. Check setup and reconnect.'),500)}

function activityEmail(a){
 if(a.email)return a.email;
 if(a.type!=='Email'||!a.mail_message_id)return null;
 // Older imports retain the original structured header text.
 const match=(a.text||'').match(/^([^\n]*)\nFrom: ([^\n]*)\nTo: ([^\n]*)\n\n([\s\S]*)$/);
 return match?{subject:match[1],sender:match[2],to:match[3],text:match[4],date:a.created}:null;
}
function activityPreview(a){const m=activityEmail(a);return m?`${m.subject} · ${m.sender} — ${(m.text||'').replace(/\s+/g,' ').slice(0,160)}`:(a.text||'').slice(0,240)}
function emailBody(m){
 if(m.html){
  const document=`<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; form-action 'none'; base-uri 'none'"><style>body{margin:20px;font:14px/1.6 Arial,sans-serif;color:#263442;overflow-wrap:anywhere}img{max-width:100%;height:auto}table{max-width:100%}a{color:#075d69}</style></head><body>${m.html}</body></html>`;
  return `<p class="email-privacy">Remote images and active content are blocked.</p><iframe class="email-html" title="Email message body" sandbox="" referrerpolicy="no-referrer" srcdoc="${esc(document)}"></iframe><details class="email-text-alternative"><summary>View plain text</summary><pre class="email-plain">${esc(m.text||'No plain-text version available.')}</pre></details>`;
 }
 return `<div class="email-body"><pre class="email-plain">${esc(m.text||'No message body.')}</pre></div>`;
}
function activityContent(a){
 const m=activityEmail(a);if(!m)return `<p class="activity-text">${esc(a.text)}</p>`;
 return `<article class="email-card"><div class="email-message-header"><h3>${esc(m.subject||'(No subject)')}</h3><time>${esc(new Date(m.date||a.created).toLocaleString())}</time><dl><dt>From</dt><dd>${esc(m.sender)}</dd><dt>To</dt><dd>${esc(m.to)}</dd>${m.cc?`<dt>Cc</dt><dd>${esc(m.cc)}</dd>`:''}</dl>${emailOpenStatus({...m,id:a.mail_message_id})}</div>${emailBody(m)}</article>`;
}
