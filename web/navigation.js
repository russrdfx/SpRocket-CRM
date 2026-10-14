/* Sidebar preferences belong to the signed-in user, not the whole workspace. */
const navIconPaths={
 home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
 contacts:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 5"/>',
 company:'<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M10 21v-6h4v6"/>',
 deals:'<path d="M3 7h18v14H3zM8 7V3h8v4M3 12h18M10 12v3h4v-3"/>',
 tasks:'<rect x="4" y="4" width="16" height="17" rx="2"/><path d="M9 4V2h6v2M8 12l3 3 5-6"/>',
 mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18M7 14h2m4 0h2m-8 3h2"/>',
 ticket:'<path d="M3 7h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4zM15 7v2m0 3v2m0 3v2"/>',
 chart:'<path d="M4 3v17h17M8 16v-4m5 4V8m5 8V5"/>',
 megaphone:'<path d="m3 10 16-6v16L3 14zM6 15l2 6h4l-2-5M21 8v8"/>',
 file:'<path d="M5 3h10l4 4v14H5zM15 3v5h4M8 12h8m-8 4h8"/>',
 wallet:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 8h18M16 12h5v5h-5zM6 5V3h12"/>',
 support:'<path d="M3 14v-2a9 9 0 0 1 18 0v2M3 12h4v7H3zM17 12h4v7h-4zM21 19v2h-6"/>',
 data:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
 bot:'<rect x="4" y="7" width="16" height="14" rx="3"/><path d="M12 3v4M2 12h2m16 0h2M8 12h1m6 0h1M8 17h8"/>',
 bolt:'<path d="m14 2-9 12h7l-2 8 9-12h-7z"/>',
 code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-16-2 20"/>',
 settings:'<path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',
 clean:'<path d="m15 3 4 4-9 9-4-4zM6 12l-3 8 8 1 3-8M6 17l-1 4m4-3v3"/>',
 search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
 more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
 pin:'<path d="M9 3h6l-1 6 4 4v2H6v-2l4-4zM12 15v7"/>',
 unpin:'<path d="M9 3h6l-1 6 4 4v2H8M12 15v7M3 3l18 18"/>',
 chevron:'<path d="m8 5 7 7-7 7"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',
 layers:'<path d="m12 3 10 6-10 6L2 9zM2 13l10 6 10-6M2 17l10 6 10-6"/>',
 sparkle:'<path d="m12 3 2 7 7 2-7 2-2 7-2-7-7-2 7-2z"/>',phone:'<path d="m5 3 4 5-2 3a13 13 0 0 0 6 6l3-2 5 4-2 3C9 23 1 15 2 5z"/>'
};
const navGroupIcons={CRM:'contacts',Work:'tasks',Marketing:'megaphone',Content:'file',Sales:'chart',Revenue:'wallet',Service:'support','Data Management':'data',Agents:'bot',Automation:'bolt',Reporting:'chart',Development:'code','Custom records':'layers'};
const navItemIcons={Contacts:'contacts',Companies:'company',Deals:'deals',Tickets:'ticket',Tasks:'tasks',Inbox:'mail',Calendar:'calendar',Dashboards:'home',Reports:'chart',Configuration:'settings','Data Quality':'clean','Data Model':'layers','Data Enrichment':'sparkle',Calls:'phone',Meetings:'calendar','Marketing Emails':'mail',Invoices:'wallet',Workflows:'bolt','Prospecting Agent':'bot'};
const navBuiltPages={'Message Templates':'templates',Contacts:'contacts',Companies:'companies',Deals:'deals',Tickets:'tickets',Tasks:'tasks',Inbox:'inbox',Calendar:'calendar',Dashboards:'dashboard',Reports:'reports',Configuration:'settings','Data Quality':'cleanup','Activity Feed':'dashboard'};
const navSettings={'Data Model':'Properties','Data Enrichment':'Data Enrichment'};
let navMoreOpen=false,navMoreGroup='CRM',navMoreQuery='',navSaving=false,navLastPage='',navLastOwner='';
function navIcon(key){return `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${navIconPaths[key]||navIconPaths.file}</svg>`}
function navLabel(item){return item.startsWith('record:')?type(item.slice(7))?.name||'Custom records':item==='Data Quality'?'Data cleanup':item}
function navPlanned(item){return !item.startsWith('record:')&&!(item in navBuiltPages)&&!(item in navSettings)}
function navOwner(){return JSON.stringify(state.auth?.user||'local')}
function navGroup(item){return Object.keys(state.navigation.catalog).find(group=>state.navigation.catalog[group].includes(item))||'Custom records'}
function navRoute(item){return item.startsWith('record:')?item.slice(7):navBuiltPages[item]||'module:'+item}
function navCurrent(item){
 if(item==='Configuration')return page==='settings'&&!state.navigation.preferences.pins.some(p=>navSettings[p]===settingsSection);
 if(item in navSettings)return page==='settings'&&settingsSection===navSettings[item];
 const route=navRoute(item);return page===route||(item==='Contacts'&&page.startsWith('contact:'))||(item==='Deals'&&page.startsWith('deal:'));
}
function navNavigate(item){navCloseMore();if(item in navSettings){settingsSection=navSettings[item];go('settings')}else if(item.startsWith('record:'))go(item.slice(7));else destination(item)}
function navButton(item,label=navLabel(item)){const icon=navItemIcons[item]||navGroupIcons[navGroup(item)]||'file';return `<button type="button" class="nav-link ${navCurrent(item)?'active':''}" data-nav-item="${esc(item)}" ${navCurrent(item)?'aria-current="page"':''} title="${esc(label)}">${navIcon(icon)}<span>${esc(label)}</span>${navPlanned(item)?'<small class="nav-planned">Planned</small>':''}</button>`}
function navPaint(){
 if(!state.navigation)return;const prefs=state.navigation.preferences;
 $('#nav').classList.add('organized-nav');
 $('#nav').innerHTML=`<div class="nav-home">${navButton('Dashboards','Home')}</div>${Object.keys(state.navigation.catalog).map((group,index)=>{const pins=prefs.pins.filter(p=>navGroup(p)===group);if(!pins.length)return '';const collapsed=prefs.collapsed.includes(group);return `<div class="nav-section"><button type="button" class="nav-section-toggle" data-nav-section="${esc(group)}" aria-expanded="${!collapsed}" aria-controls="nav-section-${index}" ${navSaving?'disabled':''}>${navIcon(navGroupIcons[group])}<span>${esc(group)}</span>${navIcon('chevron')}</button><div class="nav-section-items" id="nav-section-${index}" ${collapsed?'hidden':''}>${pins.map(item=>`<div class="nav-shortcut">${navButton(item)}<button type="button" class="nav-remove" data-nav-remove="${esc(item)}" aria-label="Remove ${esc(navLabel(item))} from sidebar" title="Remove from sidebar" ${navSaving?'disabled':''}>${navIcon('unpin')}</button></div>`).join('')}</div></div>`}).join('')}<div class="nav-utilities"><button type="button" id="more" aria-expanded="${navMoreOpen}" aria-controls="more-menu" aria-haspopup="dialog">${navIcon('more')}<span>More tools</span>${navIcon('chevron')}</button>${navButton('Configuration')}</div>`;
 $('#nav').querySelectorAll('[data-nav-item]').forEach(b=>b.onclick=()=>navNavigate(b.dataset.navItem));
 $('#nav').querySelectorAll('[data-nav-remove]').forEach(b=>b.onclick=()=>navSave({...prefs,pins:prefs.pins.filter(p=>p!==b.dataset.navRemove)},'#more'));
 $('#nav').querySelectorAll('[data-nav-section]').forEach(b=>b.onclick=()=>{const key=b.dataset.navSection;navSave({...prefs,collapsed:prefs.collapsed.includes(key)?prefs.collapsed.filter(g=>g!==key):[...prefs.collapsed,key]},`[data-nav-section="${key}"]`)});
 $('#more').onclick=()=>{navMoreOpen=!navMoreOpen;navMoreQuery='';navPaintMore();$('#more').setAttribute('aria-expanded',String(navMoreOpen));if(navMoreOpen)$('#nav-tool-search').focus()};
}
async function navSave(prefs,focus){
 if(navSaving)return;const owner=navOwner();navSaving=true;navPaint();navPaintMore();
 try{const saved=await api('/api/navigation/preferences',prefs);if(navOwner()===owner)state.navigation.preferences=saved}
 catch(error){toast('Sidebar changes could not be saved: '+error.message)}
 finally{navSaving=false;navPaint();navPaintMore();const target=focus&&document.querySelector(focus);if(target&&!target.disabled)target.focus()}
}
function navCloseMore(returnFocus=false){navMoreOpen=false;const menu=$('#more-menu');if(menu)menu.hidden=true;$('#more')?.setAttribute('aria-expanded','false');if(returnFocus)$('#more')?.focus()}
function navPositionMore(){const menu=$('#more-menu');if(!menu||menu.hidden)return;const rect=$('#more').getBoundingClientRect(),width=Math.min(630,window.innerWidth-24);menu.style.width=width+'px';menu.style.left=Math.min(rect.right+12,Math.max(12,window.innerWidth-width-12))+'px';menu.style.top=Math.max(12,Math.min(rect.top,window.innerHeight-Math.min(580,window.innerHeight-24)-12))+'px';menu.style.bottom='auto'}
function navPaintMore(){
 let menu=$('#more-menu');if(!menu){menu=document.createElement('div');menu.id='more-menu';document.body.append(menu)}
 menu.className='more-menu nav-tool-menu';menu.setAttribute('role','dialog');menu.setAttribute('aria-label','Browse and pin navigation tools');menu.hidden=!navMoreOpen;
 if(!state.navigation)return;
 const prefs=state.navigation.preferences,catalog=state.navigation.catalog,groups=Object.keys(catalog),matches=navMoreQuery.trim().toLowerCase();
 const items=matches?groups.flatMap(group=>catalog[group]).filter(item=>navLabel(item).toLowerCase().includes(matches)):catalog[navMoreGroup]||catalog[groups[0]];
 menu.innerHTML=`<div class="nav-tool-header"><label class="nav-search-label">${navIcon('search')}<input id="nav-tool-search" aria-label="Find a tool" placeholder="Find a tool" value="${esc(navMoreQuery)}"></label><button type="button" id="nav-tool-close" aria-label="Close tools">${navIcon('close')}</button></div><div class="nav-tool-body"><div class="more-groups" role="tablist" aria-label="Tool categories" aria-orientation="vertical">${groups.map(group=>`<button type="button" role="tab" data-tool-group="${esc(group)}" aria-selected="${!matches&&navMoreGroup===group}" aria-controls="nav-tool-items" class="${!matches&&navMoreGroup===group?'selected':''}">${navIcon(navGroupIcons[group])}<span>${esc(group)}</span>${navIcon('chevron')}</button>`).join('')}</div><div class="more-items" id="nav-tool-items">${items.map(item=>{const fixed=['Dashboards','Activity Feed','Configuration'].includes(item),pinned=fixed||prefs.pins.includes(item);return `<div class="nav-tool-row"><button type="button" class="nav-tool-open" data-tool-item="${esc(item)}">${navIcon(navItemIcons[item]||navGroupIcons[navGroup(item)])}<span>${esc(navLabel(item))}${navPlanned(item)?'<small>Planned feature</small>':''}${fixed?'<small>Always available '+(item==='Configuration'?'in Configuration':'on Home')+'</small>':''}</span></button><button type="button" class="nav-tool-pin ${pinned?'pinned':''}" data-tool-pin="${esc(item)}" aria-label="${pinned?'Unpin':'Pin'} ${esc(navLabel(item))}${pinned?'':' to sidebar'}" aria-pressed="${pinned}" title="${fixed?'Always available in the sidebar':pinned?'Remove from sidebar':'Pin to sidebar'}" ${fixed||navSaving?'disabled':''}>${navIcon('pin')}</button></div>`}).join('')||'<p class="nav-no-results">No matching tools.</p>'}</div></div><div class="nav-tool-footer"><span id="nav-save-status" role="status">${navSaving?'Saving sidebar…':'Pin tools to add them to your sidebar.'}</span><button type="button" id="nav-reset" ${navSaving?'disabled':''}>Reset shortcuts</button></div>`;
 $('#nav-tool-close').onclick=()=>navCloseMore(true);$('#nav-tool-search').oninput=e=>{const start=e.target.selectionStart;navMoreQuery=e.target.value;navPaintMore();$('#nav-tool-search').focus();$('#nav-tool-search').setSelectionRange(start,start)};
 menu.querySelectorAll('[data-tool-group]').forEach(b=>{b.onclick=()=>{navMoreGroup=b.dataset.toolGroup;navMoreQuery='';navPaintMore();menu.querySelector(`[data-tool-group="${navMoreGroup}"]`).focus()};b.onkeydown=e=>{if(['ArrowUp','ArrowDown','Home','End'].includes(e.key)){e.preventDefault();const i=groups.indexOf(b.dataset.toolGroup),next=groups[e.key==='Home'?0:e.key==='End'?groups.length-1:(i+(e.key==='ArrowDown'?1:groups.length-1))%groups.length];navMoreGroup=next;navMoreQuery='';navPaintMore();menu.querySelector(`[data-tool-group="${next}"]`).focus()}}});
 menu.querySelectorAll('[data-tool-item]').forEach(b=>b.onclick=()=>navNavigate(b.dataset.toolItem));menu.querySelectorAll('[data-tool-pin]').forEach(b=>b.onclick=()=>{const item=b.dataset.toolPin,pinned=prefs.pins.includes(item);navSave({...prefs,pins:pinned?prefs.pins.filter(p=>p!==item):[...prefs.pins,item]},`[data-tool-pin="${item}"]`)});
 $('#nav-reset').onclick=()=>navSave({pins:['Contacts','Companies','Deals','Tickets','Tasks','Inbox','Calendar','Data Quality',...(catalog['Custom records']||[])],collapsed:[]},'#nav-reset');navPositionMore();
}
const organizedShell=shell;shell=function(){organizedShell();if(!state.navigation)return;const owner=navOwner();if(navLastOwner!==owner||navLastPage!==page)navCloseMore();navLastOwner=owner;navLastPage=page;navPaint();navPaintMore()};
function navInsideTools(event){return event.composedPath().some(node=>node?.id==='more-menu'||node?.id==='more')}
document.addEventListener('click',e=>{if(navMoreOpen&&!navInsideTools(e))navCloseMore()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&navMoreOpen){e.preventDefault();navCloseMore(true)}});
window.addEventListener('resize',navPositionMore);
if(state)shell();
