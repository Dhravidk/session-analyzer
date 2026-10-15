'use strict';
const $=id=>document.getElementById(id), base=location.pathname, token=base.split('/')[2];
const narrow=matchMedia('(max-width:900px)');
let catalog,selected=null,displayedSession=null,reportId=null,shown=100,pollTimer,watchedJob=null,selectTicket=0,storageKey='',restoring=false,localPreview=false;
let saved={query:'',folders:{},paths:{},listTop:0,selected:null,sidebar:true,positions:{}};
const statusNames={completed:'Analysis completed',partial:'Analysis incomplete',failed:'Analysis failed',running:'Analysis incomplete',created:'Not analyzed',not_run:'Not analyzed'};
const date=value=>{const d=new Date(value);return Number.isNaN(d.valueOf())?'Time unavailable':d.toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});};
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function icon(name){const el=node('span',undefined,'icon '+name);el.setAttribute('aria-hidden','true');return el;}
function message(text){$('status').textContent=text;$('status').hidden=!text;}
function persist(){if(!storageKey || restoring)return;try{sessionStorage.setItem(storageKey,JSON.stringify(saved));}catch{}}
function rememberPosition(){if(reportId&&displayedSession)try{saved.positions[displayedSession]={report:reportId,y:$('report').contentWindow.scrollY};}catch{}persist();}
async function api(route,payload){const response=await fetch(base+'api/'+route,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Ally-Library':token},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;}
function requestPreview(text){
  // Whole, well-formed native command envelope only. Ambiguous content stays literal.
  const match=(text||'').match(/^\s*<command-message>([^<>]*)<\/command-message>\s*<command-name>([^<>]*)<\/command-name>(?:\s*<command-args>([^<>]*)<\/command-args>)?\s*$/);
  return match?match[2]+(match[3]?' '+match[3]:''):text||'Request preview unavailable';
}
function hasAnalysis(report){return report&&report.kind!=='preview'&&!['created','not_run'].includes(report.status);}
function sessionTitle(item){const text=item.title||requestPreview(item.preview);return text.slice(0,150)+(text.length>150?'…':'');}
function setList(visible,focus=false){
  if(!restoring&&!visible&&$('list-scroll').getClientRects().length)saved.listTop=$('list-scroll').scrollTop;
  document.body.classList.toggle('list-hidden',!visible);$('toggle-list').setAttribute('aria-expanded',String(visible));
  if(visible)$('list-scroll').scrollTop=saved.listTop;
  $('drawer-backdrop').hidden=!(narrow.matches&&visible);$('viewer').inert=narrow.matches&&visible;
  $('session-list').setAttribute('role',narrow.matches?'dialog':'complementary');
  if(narrow.matches&&visible)$('session-list').setAttribute('aria-modal','true');else $('session-list').removeAttribute('aria-modal');
  if(!narrow.matches){saved.sidebar=visible;persist();}
  if(focus){if(visible)$('search').focus();else $('toggle-list').focus();}
}
function statusLine(item){
  const meta=node('span',undefined,'session-meta');
  const first=item.states[0]||{tone:'gray',label:'Unknown'};
  const dot=node('span',undefined,'status-dot '+first.tone);dot.setAttribute('aria-hidden','true');meta.append(dot);
  const when=item.activity_at?date(item.activity_at*1000):'File changed '+date(item.modified_at*1000);
  meta.append(node('span',when+' · '));
  item.states.forEach((state,index)=>{if(index)meta.append(' · ');meta.append(node('span',state.label,'status-label'));});
  meta.title=item.activity_basis+(first.key==='ready'?'. Ready means a completed analysis matches captured evidence; it does not indicate task success.':'');
  return meta;
}
function drawSessions(){
  const focus=document.activeElement,focusSession=focus?.dataset.session,focusFolder=focus?.dataset.folder;
  const top=!restoring&&$('list-scroll').getClientRects().length?$('list-scroll').scrollTop:saved.listTop,query=$('search').value.trim().toLocaleLowerCase();
  const all=catalog.sessions.filter(s=>!query||[s.title,s.preview,s.session_id,s.folder_path,s.relative_path].join(' ').toLocaleLowerCase().includes(query));
  const groups=new Map();
  for(const item of all.slice(0,shown)){if(!groups.has(item.folder_path))groups.set(item.folder_path,[]);groups.get(item.folder_path).push(item);}
  $('sessions').replaceChildren();
  for(const [path,items] of groups){
    const group=node('section',undefined,'folder-group'),head=node('div',undefined,'folder-head');
    const id='folder-'+items[0].id,open=query?saved.searchFolders?.[path]!==false:saved.folders[path]!==false;
    const toggle=node('button',undefined,'folder-toggle');toggle.dataset.folder=path;toggle.title=path;toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-controls',id);
    toggle.append(icon('chevron-right'),icon('folder'),node('span',items[0].folder_label,'folder-name'));
    if(!open)toggle.append(node('span',String(items.length),'folder-count'));
    toggle.onclick=()=>{if(query){saved.searchFolders=saved.searchFolders||{};saved.searchFolders[path]=!open;}else saved.folders[path]=!open;persist();drawSessions();};
    const full=node('button',undefined,'icon-button folder-path-button');full.append(icon('more-horizontal'));full.setAttribute('aria-label','Show full path for '+items[0].folder_label);full.setAttribute('aria-expanded',String(!!saved.paths[path]));
    const fullPath=node('code',path,'folder-full-path');fullPath.hidden=!saved.paths[path];
    full.onclick=()=>{saved.paths[path]=!saved.paths[path];fullPath.hidden=!saved.paths[path];full.setAttribute('aria-expanded',String(!!saved.paths[path]));persist();};
    head.append(toggle,full);group.append(head,fullPath);
    const rows=node('div');rows.id=id;rows.hidden=!open;
    for(const item of items){
      const row=node('button',undefined,'session');row.dataset.session=item.id;row.setAttribute('aria-current',String(selected?.id===item.id));
      row.append(node('span',sessionTitle(item),'session-title'),statusLine(item));row.title=item.title||requestPreview(item.preview);
      row.onclick=()=>select(item.id).catch(e=>message(e.message));rows.append(row);
    }
    group.append(rows);$('sessions').append(group);
  }
  $('more').hidden=all.length<=shown;$('no-results').hidden=!!all.length;
  $('session-count').textContent=all.length+' '+(all.length===1?'session':'sessions');
  $('list-scroll').scrollTop=top;
  if(focusSession)$('sessions').querySelector('[data-session="'+CSS.escape(focusSession)+'"]')?.focus({preventScroll:true});
  if(focusFolder)$('sessions').querySelector('[data-folder="'+CSS.escape(focusFolder)+'"]')?.focus({preventScroll:true});
}
function drawCatalog(next){
  catalog=next;$('root-label').textContent=next.folder_label;$('root-path').textContent=next.root;
  if(next.fixture_label)message(next.fixture_label);
  $('scan-limits').textContent=next.limits.join(' ');$('scan-limits').hidden=!next.limits.length;
  if(selected)selected=next.sessions.find(s=>s.id===selected.id)||null;
  drawSessions();if(selected)drawSelection();
}
function drawSelection(){
  const report=selected.latest_report,analyzed=hasAnalysis(report);
  $('selection').hidden=false;
  $('selected-title').textContent=report?.title||sessionTitle(selected);
  $('selected-folder').textContent=selected.folder_label;
  $('selected-time').textContent=selected.activity_at?date(selected.activity_at*1000):'Activity time unavailable';
  $('selected-id').textContent='Session '+selected.session_id;
  $('selected-path').textContent=selected.folder_path+'\nLog: '+selected.relative_path;
  $('selected-request').textContent=selected.preview+(selected.request_preview_truncated?'…':'');
  $('preview-limit').textContent=(selected.preview_partial?'Discovery inspected bounded excerpts. ':'')+(selected.request_preview_truncated?'This request preview is shortened; the complete retained request is in the turn/source view. ':'')+(selected.malformed_preview_lines?'Some preview lines could not be read. ':'');
  $('analysis-state').textContent=analyzed?(statusNames[report.status]||'Analysis state unknown'):'';
  const running=catalog.jobs.some(j=>['queued','running'].includes(j.status));
  $('analyze').disabled=!catalog.claude_available||running;
  $('analyze').title=!catalog.claude_available?'Relaunch with the approved Claude executable.':running?'An analysis is already running.':'';
  $('analyze-label').textContent=selected.job&&['queued','running'].includes(selected.job.status)?(analyzed?'Updating…':'Analyzing…'):analyzed?'Update analysis':'Analyze session';
  $('open-log').textContent=localPreview&&analyzed?'Return to saved analysis':'Inspect current log locally';
  const fresh=selected.freshness,notice=$('revision-note');notice.replaceChildren();notice.hidden=true;
  if(analyzed && fresh.state!=='current'){
    notice.hidden=false;notice.className='revision-note'+(fresh.state==='unknown'?' unknown':'');
    const dot=node('span',undefined,'status-dot '+(fresh.state==='unknown'?'gray':'amber'));dot.setAttribute('aria-hidden','true');notice.append(dot);
    const labels={new_activity:'New session activity since this analysis',changed:'Session evidence changed since this analysis',unknown:'Analysis freshness is unknown'};
    notice.append((labels[fresh.state]||'Analysis freshness is unknown')+' · Last analyzed '+date(report.analysis_at||report.created_at));
    if(fresh.state!=='new_activity'||fresh.comparison_limits?.length){const detail=node('details',undefined,'revision-detail');detail.append(node('summary','Comparison details'),node('p',fresh.reason));for(const limit of fresh.comparison_limits||[])detail.append(node('p',limit));notice.append(detail);}
  }
  const note=$('update-note'),job=selected.job;note.hidden=true;note.textContent='';
  if(localPreview&&analyzed){note.hidden=false;note.textContent='Inspecting the current log locally. The saved analysis remains available through session details.';}
  if(job&&['queued','running','failed','interrupted'].includes(job.status)){
    note.hidden=false;
    note.textContent=['queued','running'].includes(job.status)?(analyzed?'Updating analysis. The saved report remains available.':'Claude is analyzing this session.'):(analyzed?'Update failed. The previous saved analysis is shown. ':'Analysis failed. ')+(job.error||'No new valid report was produced.');
  }
}
function setExport(id){
  for(const format of ['html','md','json']){const a=$('export-'+format);a.hidden=!id;if(id){a.href=base+'downloads/'+id+'.'+format;a.download='ally-session.'+format;}else a.removeAttribute('href');}
  $('export-empty').hidden=!!id;
}
async function showReport(id){
  if(reportId===id)return;
  rememberPosition();reportId=id;displayedSession=selected.id;setExport(id);const frame=$('report');frame.hidden=false;
  // Only the selected session should add a browser-history entry. Assigning src
  // also adds an iframe entry, which makes Back restore a report independently
  // of the selected session and its export controls.
  frame.contentWindow.location.replace(base+'reports/'+id+'.html');$('welcome').hidden=true;
}
async function select(id,{history=true}={}){
  const item=catalog.sessions.find(s=>s.id===id);if(!item)return;
  rememberPosition();setReadingHeader(0);const ticket=++selectTicket;selected=item;localPreview=false;saved.selected=id;persist();
  if(history&&new URLSearchParams(location.hash.slice(1)).get('session')!==id)location.hash=new URLSearchParams({session:id});
  drawSessions();drawSelection();if(narrow.matches)setList(false);
  if(item.latest_report)await showReport(item.latest_report.id);
  else{
    reportId=null;setExport(null);$('report').hidden=true;$('report').contentWindow.location.replace('about:blank');$('welcome').hidden=false;$('welcome').textContent='Opening the session log locally…';
    try{const result=await api('start',{session:id,action:'preview'});if(ticket!==selectTicket)return;if(result.report_id)await showReport(result.report_id);else{watchedJob=result.job_id;poll();}}
    catch(error){if(ticket===selectTicket)$('welcome').textContent=error.message;}
  }
}
async function start(action,options={}){
  const result=await api('start',{session:selected.id,action,...options});
  if(result.report_id){await showReport(result.report_id);return;}
  watchedJob=result.job_id;await poll();
}
async function poll(){
  clearTimeout(pollTimer);
  try{
    const before=selected?.latest_report?.id;drawCatalog(await api('catalog'));
    const job=catalog.jobs.find(j=>j.id===watchedJob)||[...catalog.jobs].reverse().find(j=>['queued','running'].includes(j.status));
    if(job){
      if(['queued','running'].includes(job.status)){watchedJob=job.id;pollTimer=setTimeout(poll,1500);}
      else{
        watchedJob=null;
        if(job.status==='saved'&&selected?.id===job.session_key){
          if(job.action==='preview'){if(localPreview||!reportId)await showReport(job.report_id);}
          else{localPreview=false;await showReport(selected.latest_report.id);drawSelection();}
        }
        if(job.status!=='saved'&&selected?.id===job.session_key&&!selected.latest_report){$('welcome').textContent=job.error||'Analysis did not finish.';}
      }
    }
    if(selected?.latest_report?.id&&selected.latest_report.id!==before&&!localPreview)await showReport(selected.latest_report.id);
  }catch(error){message(error.message);pollTimer=setTimeout(poll,5000);}
}
$('refresh').onclick=async()=>{try{$('refresh').disabled=true;drawCatalog(await api('refresh',{}));if(selected?.latest_report&&!localPreview)await showReport(selected.latest_report.id);message('');}catch(error){message(error.message);}finally{$('refresh').disabled=false;}};
$('toggle-list').onclick=()=>setList(document.body.classList.contains('list-hidden'),true);
$('close-list').onclick=$('drawer-backdrop').onclick=()=>setList(false,true);
$('search').addEventListener('input',()=>{saved.query=$('search').value;saved.searchFolders={};shown=100;persist();drawSessions();});
$('list-scroll').addEventListener('scroll',()=>{if(!restoring&&$('list-scroll').getClientRects().length){saved.listTop=$('list-scroll').scrollTop;persist();}},{passive:true});
$('more').onclick=()=>{shown+=100;drawSessions();};
$('open-log').onclick=async()=>{try{if(localPreview&&selected.latest_report?.kind!=='preview'){localPreview=false;await showReport(selected.latest_report.id);drawSelection();}else{localPreview=true;drawSelection();await start('preview');}}catch(e){message(e.message);}};
$('analyze').onclick=()=>{$('disclosure').checked=false;$('dialog-error').hidden=true;$('investigate-session').textContent=sessionTitle(selected);$('investigate-title').textContent=hasAnalysis(selected.latest_report)?'Update analysis':'Analyze session';$('investigate-dialog').showModal();};
$('close-dialog').onclick=()=>$('investigate-dialog').close();
$('investigate-form').onsubmit=async event=>{event.preventDefault();$('start').disabled=true;try{await start('investigate',{allow_content:$('disclosure').checked,budget:Number($('budget').value),timeout:Number($('timeout').value)*60});$('investigate-dialog').close();}catch(error){$('dialog-error').textContent=error.message;$('dialog-error').hidden=false;}finally{$('start').disabled=false;}};
function setReadingHeader(y){
  const reading=y>120,selection=$('selection'),toggle=$('toggle-title');
  selection.classList.toggle('reading',reading);toggle.hidden=!reading;
  if(!reading){selection.classList.remove('title-expanded');toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-label','Expand session title');}
}
$('toggle-title').onclick=()=>{
  const expanded=$('selection').classList.toggle('title-expanded');
  $('toggle-title').setAttribute('aria-expanded',String(expanded));
  $('toggle-title').setAttribute('aria-label',expanded?'Collapse session title':'Expand session title');
};
$('report').onload=()=>{
  const frame=$('report'),id=reportId,session=selected?.id;
  try{
    const position=saved.positions[session];if(position?.report===id)frame.contentWindow.scrollTo(0,position.y);
    setReadingHeader(frame.contentWindow.scrollY);
    frame.contentWindow.addEventListener('scroll',()=>{saved.positions[session]={report:id,y:frame.contentWindow.scrollY};persist();setReadingHeader(frame.contentWindow.scrollY);},{passive:true});
    frame.contentDocument.addEventListener('click',event=>{
      const control=event.target.closest('[data-export]');if(!control)return;const format=control.dataset.export;if(!['html','md','json'].includes(format))return;
      event.preventDefault();event.stopImmediatePropagation();$('export-'+format).click();
    },true);
  }catch{}
};
$('export').addEventListener('click',event=>{if(event.target.closest('a'))$('export').open=false;});
window.addEventListener('hashchange',()=>{const id=new URLSearchParams(location.hash.slice(1)).get('session');if(catalog&&id&&id!==selected?.id)select(id,{history:false}).catch(e=>message(e.message));});
window.addEventListener('pagehide',rememberPosition);
narrow.addEventListener('change',()=>setList(narrow.matches?false:saved.sidebar));
document.addEventListener('keydown',event=>{
  if(!narrow.matches||document.body.classList.contains('list-hidden'))return;
  if(event.key==='Escape'){event.preventDefault();setList(false,true);}
  if(event.key==='Tab'){
    const focusable=[...$('session-list').querySelectorAll('button:not([disabled]),input,summary')].filter(el=>el.getClientRects().length),first=focusable[0],last=focusable[focusable.length-1];
    if(event.shiftKey&&(document.activeElement===first||!$('session-list').contains(document.activeElement))){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  }
});
async function boot(){try{
  const next=await api('catalog');storageKey='ally-library:'+next.root;
  try{saved={...saved,...JSON.parse(sessionStorage.getItem(storageKey)||'{}')};}catch{}
  restoring=true;$('search').value=saved.query;drawCatalog(next);setList(narrow.matches?false:saved.sidebar);
  const id=new URLSearchParams(location.hash.slice(1)).get('session')||saved.selected;
  if(id&&next.sessions.some(s=>s.id===id))await select(id,{history:false});
  else if(next.sessions.length)await select(next.sessions[0].id,{history:false});
  else{$('welcome').textContent='No session logs found in this directory.';setExport(null);}
  $('list-scroll').scrollTop=saved.listTop;restoring=false;persist();poll();
}catch(error){restoring=false;message(error.message);}}
boot();
