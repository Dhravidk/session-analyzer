'use strict';
(() => {
  const data = JSON.parse(document.getElementById('report-data').textContent);
  const sources = data.sources || {};
  const accounting = data.main_accounting || data.accounting;
  const turns = new Map(accounting.turns.map(t => [t.id,t]));
  const agents = data.agents || {};
  const delegations = new Map((data.delegations || []).map(d => [d.tool_id,d]));
  const proposals = new Map(data.recommendations.map(p => [p.id,p.recommendation]));
  const tools = new Map((data.tools || []).map(t => [t.id,t]));
  const sourceDialog = document.getElementById('source-dialog');
  const cursors = new Map();
  const agentCursors = new Map();
  let parentEvidenceDialog = null;
  let copyTimer;
  let selectedSource=null, sourceReturnFocus=null, sourceReportAnchor=null;
  let sourceExpanded=false, sourceScrollTop=0;
  const mobileInspector=window.matchMedia('(max-width: 760px)');
  const embedded=document.body.classList.contains('library-embedded');
  if(embedded){
    const reopen=document.querySelector('[data-source-reopen]');
    reopen.textContent='Sources';reopen.prepend(document.getElementById('icon-file').content.cloneNode(true));
    reopen.setAttribute('aria-label','Open sources');
    document.querySelector('.report-nav').append(reopen);
  }
  const sourceTurns=new Map();
  accounting.turns.forEach((t,index)=>t.event_ids.forEach(id=>sourceTurns.set(id,{id:t.id,index:index+1})));
  function icon(name) { return document.getElementById('icon-'+name).content.cloneNode(true); }
  function iconButton(text,name,action,className='link') { const b=button(text,action,className); b.prepend(icon(name)); return b; }
  const wrapTooltip=document.createElement('div');wrapTooltip.id='word-wrap-tooltip';wrapTooltip.className='wrap-tooltip';wrapTooltip.setAttribute('role','tooltip');wrapTooltip.hidden=true;document.body.append(wrapTooltip);
  let wrapTooltipTarget=null,wrapTooltipTimer,codePanelSequence=0;
  function hideWrapTooltip(){clearTimeout(wrapTooltipTimer);wrapTooltip.hidden=true;wrapTooltipTarget?.removeAttribute('aria-describedby');wrapTooltipTarget=null;}
  wrapTooltip.addEventListener('pointerenter',()=>clearTimeout(wrapTooltipTimer));
  wrapTooltip.addEventListener('pointerleave',()=>{if(document.activeElement!==wrapTooltipTarget)hideWrapTooltip();});
  function showWrapTooltip(control){
    if(!control.isConnected){hideWrapTooltip();return;}
    const rect=control.getBoundingClientRect();
    if(rect.bottom<=0||rect.top>=innerHeight){hideWrapTooltip();return;}
    hideWrapTooltip();wrapTooltipTarget=control;wrapTooltip.textContent=control.dataset.tooltip;wrapTooltip.hidden=false;control.setAttribute('aria-describedby',wrapTooltip.id);
    const box=wrapTooltip.getBoundingClientRect();
    wrapTooltip.style.left=Math.max(8,Math.min(innerWidth-box.width-8,rect.left+rect.width/2-box.width/2))+'px';
    wrapTooltip.style.top=(rect.top>box.height+16?rect.top-box.height-8:rect.bottom+8)+'px';
  }
  document.addEventListener('scroll',()=>{if(wrapTooltipTarget)showWrapTooltip(wrapTooltipTarget);},true);
  window.addEventListener('resize',hideWrapTooltip);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!wrapTooltip.hidden){hideWrapTooltip();event.stopImmediatePropagation();event.preventDefault();}},true);
  const label = value => (value || 'Unknown').replaceAll('_',' ');
  function button(text, action, className='link') {
    const b = document.createElement('button'); b.type='button'; b.className=className;
    b.textContent=text; b.addEventListener('click',event=>action(event.currentTarget)); return b;
  }
  function showEvidenceDialog(prefix,id) {
    const dialog = document.getElementById(prefix+id);
    if (!dialog) return;
    for (const open of document.querySelectorAll('dialog[open]')) open.close();
    parentEvidenceDialog=null; dialog.showModal();
  }
  function showSubagent(id) {
    showEvidenceDialog('subagent-',id);
    const dialog=document.getElementById('subagent-'+id);
    if (!dialog) return;
    for (const container of dialog.querySelectorAll('[data-agent-events]')) {
      const key=dialog.id+':'+container.dataset.agentEvents;
      if (!agentCursors.has(key)) renderAgentEvents(container.dataset.agentEvents,dialog);
    }
  }
  function sourceText(s) {
    return Object.hasOwn(s,'text') ? s.text : 'Source text was not included in this export. Export this investigation locally with --include-source-text to inspect the retained masked text. No model rewrite is needed.';
  }
  function hasSourceText(s) { return typeof s?.text==='string' && s.text.trim().length>0; }
  function sourceName(s) {
    if(['tool_call','tool_result','system_status','artifact'].includes(s.role))return label(s.role).replace(/^./,c=>c.toUpperCase());
    if(s.content_metadata?.kind==='thinking' || s.role==='assistant_thinking')return 'Assistant record · thinking';
    if(s.kind==='assistant' && s.content_metadata?.kind==='mixed')return 'Assistant record · '+(s.content_metadata.has_visible_text?'text and thinking':'thinking and other content');
    if(s.kind==='assistant' && !hasSourceText(s))return 'Assistant record';
    return label(s.role).replace(/^./,c=>c.toUpperCase());
  }
  function contentReasons(s) {
    if(s.text===undefined)return ['Source text was not included in this report export. This does not establish that the original record was empty.'];
    const info=s.content_metadata,shown=new Set((info?.thinking_text || []).map(b=>b.path));
    const reasons=(info?.blocks || []).filter(b=>b.status!=='available').map(b=>shown.has(b.path)?'Captured thinking is retained in this local report and excluded from the analyzer evidence projection.':b.reason);
    for(const omission of info?.projection_omissions || [])reasons.push(omission.reason);
    if(!info && s.disclosure?.omitted_categories?.length && hasSourceText(s))reasons.push('This older export records omitted content without identifying its exact type. Re-export from the retained log for the specific reason.');
    if(!reasons.length && !hasSourceText(s)) {
      const old=s.disclosure?.omitted_categories || [];
      reasons.push(old.length?'This older export does not identify the exact content omission. Re-export from the retained log to distinguish thinking, media and unsupported content.':'This saved source excerpt is empty; no textual evidence is available.');
    }
    return [...new Set(reasons)];
  }
  function sourceNotice(s,title=null) {
    const section=document.createElement('section');section.className='source-absence';
    if(title && title!=='Record'){const h=document.createElement('h4');h.textContent=title;section.append(h);}
    const reasons=contentReasons(s);
    if(!reasons.length)reasons.push('No readable '+(title || 'source').toLowerCase()+' text is available.');
    for(const reason of reasons){const p=document.createElement('p');p.className='source-availability';p.textContent=reason;section.append(p);}
    return section;
  }
  function sourceAccounting(s) {
    const container=document.getElementById('source-accounting');container.replaceChildren();
    const responses=(s.response_ids || []).map(id=>data.response_usage?.[id]).filter(Boolean);
    if(!responses.length){
      if(s.kind==='assistant'){const p=document.createElement('p');p.className='small muted';p.textContent='Response-level usage is not available in this export.';container.append(p);}return;
    }
    const fields={total_input_tokens:'Input total',input_tokens:'Uncached input',cache_creation_input_tokens:'Cache write',cache_read_input_tokens:'Cache read',output_tokens:'Output',thinking_tokens:'Thinking (included in output)'};
    for(const response of responses){
      const details=document.createElement('details'),summary=document.createElement('summary');
      const thinking=response.tokens.thinking_tokens;
      const thinkingValue=thinking==null?(response.thinking_tokens_status==='not_separately_reported'?'Not reported separately':'Unknown'):thinking.toLocaleString('en-US');
      summary.textContent='Response usage · thinking: '+thinkingValue;details.append(summary);
      const note=document.createElement('p');note.className='small muted';note.textContent=(response.eligible?'Counted once':'Excluded from eligible usage')+' across '+response.evidence.length+' captured record'+(response.evidence.length===1?'':'s')+'. These values belong to the model response, not this content block. Cache reads/writes are included in input; thinking is included in output.';details.append(note);
      const dl=document.createElement('dl');dl.className='source-usage';
      for(const [key,name] of Object.entries(fields)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=key==='thinking_tokens'?thinkingValue:response.tokens[key]==null?'Unknown':response.tokens[key].toLocaleString('en-US');dl.append(dt,dd);}
      details.append(dl);
      const status=document.createElement('p');status.className='small muted';status.textContent='Accounting: '+label(response.usage_status)+'. Response '+response.id;details.append(status);
      for(const warning of response.warnings || []){const p=document.createElement('p');p.className='limit small';p.textContent=warning;details.append(p);}
      container.append(details);
    }
  }
  function inputFields(source,tool) {
    const prefix='Tool '+tool?.name+'\nInput: ';
    if (!source?.text?.startsWith(prefix) || source.tool_ids?.length!==1) return null;
    const raw=source.text.slice(prefix.length);
    try { return {raw,values:JSON.parse(raw)}; } catch (_) { return null; }
  }
  function attemptInputs(attempt) {
    return attempt.tool_ids.map(id=>{
      const tool=tools.get(id),source=sources[tool?.evidence_id];
      return {id,tool,source,fields:inputFields(source,tool)};
    });
  }
  function compareAttempts(container) {
    const saved=data.incidents.find(i=>i.id===container.dataset.episode),ep=saved?.incident.episode;
    if(!ep)return;
    const chosen=['left','right'].map(side=>ep.attempts[Number(container.querySelector('[data-compare-side='+side+']').value)]);
    const inputs=chosen.map(attemptInputs),columns=container.querySelector('.comparison-columns');columns.replaceChildren();
    const difference=container.querySelector('.comparison-difference');difference.replaceChildren();
    let changed=[];
    if(inputs.every(group=>group.length===1&&group[0].fields?.values&&typeof group[0].fields.values==='object'&&!Array.isArray(group[0].fields.values)) && inputs[0][0].tool.name===inputs[1][0].tool.name){
      const [a,b]=inputs.map(group=>group[0].fields.values);
      changed=[...new Set([...Object.keys(a),...Object.keys(b)])].filter(key=>Object.hasOwn(a,key)!==Object.hasOwn(b,key)||JSON.stringify(a[key])!==JSON.stringify(b[key]));
      const p=document.createElement('p');p.className='small';p.textContent=changed.length?'Changed input fields: '+changed.join(', ')+'.':'Tool inputs are identical. Results and verification scope may differ.';difference.append(p);
    }else{
      const p=document.createElement('p');p.className='small muted';p.textContent='These attempts do not contain a single comparable tool input each. Their explicitly linked records are shown separately.';difference.append(p);
    }
    chosen.forEach((attempt,index)=>{
      const column=document.createElement('div'),heading=document.createElement('h4');column.className='comparison-column';heading.textContent=label(attempt.role).replace(/^./,c=>c.toUpperCase())+' attempt';column.append(heading);
      if(!inputs[index].length){const p=document.createElement('p');p.className='limit small';p.textContent='No tool identities were saved for this attempt.';column.append(p);}
      for(const item of inputs[index]){
        const h=document.createElement('h4');h.textContent=(item.tool?.name||item.id)+' · '+label(item.tool?.outcome);column.append(h);
        if(item.source){
          const fields=item.fields?.values,command=fields?.command;
          column.append(codePanel(typeof command==='string'?'Command':'Input',typeof command==='string'?command:item.fields?.raw||sourceText(item.source),typeof command==='string'?'shell':item.fields?'json':'text',item.source.id,{available:hasSourceText(item.source),selectable:true}));
          if(fields && typeof command==='string')for(const key of changed.filter(k=>k!=='command')){
            const p=document.createElement('p');p.className='small prose';p.textContent=key+': '+(Object.hasOwn(fields,key)?JSON.stringify(fields[key]):'Absent');column.append(p);
          }
        }else{const p=document.createElement('p');p.className='limit small';p.textContent='Input source unavailable in this export.';column.append(p);}
        for(const sid of item.tool?.evidence||[]){
          if(sid===item.tool.evidence_id)continue;
          const source=sources[sid];
          if(source)column.append(iconButton(source.role==='tool_result'?'Inspect result':'Inspect linked record','link-2',trigger=>showSource({source_id:sid}, {owner_id:saved.id,label:attempt.description,text:attempt.same_goal_basis,limitations:ep.limitations},trigger)));
        }
      }
      columns.append(column);
    });
  }
  function languageForResult(tool,fields) {
    if (!['Read','read_file'].includes(tool?.name)) return 'text';
    const path=fields?.values?.file_path || fields?.values?.path || '';
    const ext=path.split('.').pop().toLowerCase();
    return ({js:'javascript',jsx:'javascript',ts:'typescript',tsx:'typescript',json:'json',py:'python',sh:'shell',bash:'shell',css:'css',html:'html',xml:'xml'})[ext] || 'text';
  }
  function highlightLine(line,language) {
    const frag=document.createDocumentFragment();
    if (language==='text') { frag.append(document.createTextNode(line)); return frag; }
    // Conservative lexical color only. No evaluation, HTML injection or source rewriting.
    const pattern=/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?:\/\/|#).*?$|\$[A-Za-z_][\w]*|\b(?:const|let|var|function|return|if|else|for|while|do|done|then|fi|in|class|def|import|from|export|async|await|new|true|false|null|None)\b|\b\d+(?:\.\d+)?\b)/gm;
    let offset=0;
    for (const match of line.matchAll(pattern)) {
      frag.append(document.createTextNode(line.slice(offset,match.index)));
      const span=document.createElement('span'),token=match[0];
      span.className='syntax-'+(/^["']/.test(token)?'string':/^(#|\/\/)/.test(token)?'comment':/^\d/.test(token)?'number':token.startsWith('$')?'variable':'keyword');
      span.textContent=token;frag.append(span);offset=match.index+token.length;
    }
    frag.append(document.createTextNode(line.slice(offset)));return frag;
  }
  function codePanel(title,text,language,sourceId,options={}) {
    if(options.available===false || !text.trim())return sourceNotice(sources[sourceId] || {},title);
    const panel=document.createElement('section');panel.className='code-panel';panel.dataset.sourceId=sourceId;
    const heading=document.createElement('div');heading.className='code-heading';
    const h=document.createElement('h4');h.textContent=title;
    const type=document.createElement('span');type.className='code-language';type.textContent=language==='text'?'Plain text':label(language);
    const controls=document.createElement('div');controls.className='code-controls';
    const copy=iconButton('','copy',()=>copyExact(text,title+' copied exactly.'),'icon-button');copy.setAttribute('aria-label','Copy '+title.toLowerCase());copy.title='Copy full '+title.toLowerCase();copy.disabled=options.available===false;
    const viewport=document.createElement('div');viewport.className='code-viewport';viewport.id='source-code-'+(++codePanelSequence);viewport.tabIndex=0;viewport.setAttribute('aria-label',title+' source');
    const pre=document.createElement('pre');pre.className='code-lines';viewport.append(pre);
    let full=false,wrap=false;
    const displayed=options.displayText ?? text;
    const lines=displayed.split('\n');
    const numbered=options.savedLineNumbers && lines.filter(Boolean).length>0 && lines.filter(Boolean).every(line=>/^\d+\t/.test(line));
    const large=displayed.length>12000 || lines.length>120;
    function draw() {
      pre.replaceChildren();
      let used=0;
      for (let index=0;index<lines.length;index++) {
        if (!full && (index>=120 || used>=12000)) break;
        const saved=lines[index],parts=numbered?saved.match(/^(\d+)\t(.*)$/):null;
        let value=parts?parts[2]:saved;
        if (!full && used+value.length>12000) value=value.slice(0,12000-used);
        const row=document.createElement('span');row.className='code-line';
        const gutter=document.createElement('span');gutter.className='line-number';gutter.setAttribute('aria-hidden','true');gutter.textContent=parts?parts[1]:String(index+1);
        const content=document.createElement('span');content.className='line-content';
        content.append(highlightLine(value,full && text.length>100000?'text':language));row.append(gutter,content);pre.append(row);used+=value.length+1;
      }
    }
    function syncWrapControl(){
      const action=wrap?'Disable word wrap':'Enable word wrap';
      viewport.classList.toggle('wrap',wrap);wrapControl.setAttribute('aria-pressed',String(wrap));wrapControl.setAttribute('aria-label',action+' for '+title.toLowerCase());wrapControl.dataset.tooltip=action;
      wrapControl.replaceChildren(icon(wrap?'word-wrap-on':'word-wrap-off'));
      if(wrapControl.matches(':hover')||document.activeElement===wrapControl)showWrapTooltip(wrapControl);
    }
    const wrapControl=iconButton('','word-wrap-off',()=>{wrap=!wrap;syncWrapControl();},'icon-button wrap-toggle');
    wrapControl.setAttribute('aria-controls',viewport.id);syncWrapControl();
    wrapControl.addEventListener('pointerenter',()=>showWrapTooltip(wrapControl));
    wrapControl.addEventListener('pointerleave',event=>{if(event.relatedTarget!==wrapTooltip&&document.activeElement!==wrapControl)wrapTooltipTimer=setTimeout(hideWrapTooltip,150);});
    wrapControl.addEventListener('focus',()=>showWrapTooltip(wrapControl));wrapControl.addEventListener('blur',()=>{if(!wrapControl.matches(':hover'))hideWrapTooltip();});
    controls.append(wrapControl,copy);heading.append(h,type,controls);panel.append(heading,viewport);
    const footer=document.createElement('div');footer.className='code-footer';
    if (large) {
      const state=document.createElement('span');state.textContent='Excerpt · ';
      const more=button('Open full '+title.toLowerCase(),()=>{full=!full;draw();state.textContent=full?'Full saved text · ':'Excerpt · ';more.textContent=full?'Show excerpt':'Open full '+title.toLowerCase();more.setAttribute('aria-expanded',String(full));});more.setAttribute('aria-expanded','false');footer.append(state,more);
    }
    if (numbered) { const note=document.createElement('span');note.className='line-prefix-note';note.textContent='Saved line numbers in gutter; copy retains prefixes.';footer.append(note); }
    if (options.selectable) footer.append(button('Select this record',trigger=>showSource({source_id:sourceId},null,trigger)));
    panel.append(footer);draw();return panel;
  }
  function syncInspectorMode() {
    const opened=!sourceDialog.hidden;
    const modal=opened && (mobileInspector.matches || sourceExpanded);
    sourceDialog.setAttribute('role',modal?'dialog':'complementary');
    if (modal) sourceDialog.setAttribute('aria-modal','true');else sourceDialog.removeAttribute('aria-modal');
    for (const el of document.querySelectorAll('#report-column,.product,.report-nav')) el.inert=modal;
    document.body.classList.toggle('modal-source-open',modal);
    document.body.classList.toggle('source-expanded',opened && sourceExpanded && !mobileInspector.matches);
    const reopen=document.querySelector('[data-source-reopen]');
    reopen.hidden=embedded?opened:!selectedSource || opened;
    const expand=document.querySelector('[data-source-expand]');
    expand.hidden=mobileInspector.matches;
    expand.setAttribute('aria-pressed',String(sourceExpanded));
    expand.setAttribute('aria-label',sourceExpanded?'Restore source width':'Expand source');
    expand.title=sourceExpanded?'Restore side-by-side view':'Expand source to full width';
    expand.querySelector('span:last-child').textContent=sourceExpanded?'Restore':'Expand';
  }
  function preserveReportPosition(change) {
    // Keep a visible report element at the same height when the side panel
    // changes the document width. Do not anchor to the inspector's controls.
    const visible=el=>{const r=el?.getBoundingClientRect();return el?.isConnected && r.height && r.bottom>120 && r.top<innerHeight;};
    const anchor=visible(sourceReportAnchor)?sourceReportAnchor:
      [...document.querySelectorAll('#report-column h1,#report-column h2,#report-column p,#report-column tr,#report-column summary')].find(visible);
    sourceReportAnchor=anchor;
    const top=anchor?.getBoundingClientRect().top,scroll=window.scrollY;
    change();
    if(anchor)window.scrollBy(0,anchor.getBoundingClientRect().top-top);
    else window.scrollTo(0,scroll);
  }
  function closeSource(restore=true,retainSelection=true) {
    hideWrapTooltip();
    sourceScrollTop=sourceDialog.scrollTop;
    preserveReportPosition(()=>{
      sourceDialog.hidden=true;document.body.classList.remove('has-source');
      if(!retainSelection){selectedSource=null;sourceExpanded=false;delete sourceDialog.dataset.selectedSource;}
      syncInspectorMode();
    });
    if (restore && sourceReturnFocus?.isConnected) sourceReturnFocus.focus({preventScroll:true});
    if(!retainSelection)document.querySelectorAll('.selected-source,.source-selected').forEach(el=>el.classList.remove('selected-source','source-selected'));
  }
  function syncSourceBack() {
    const back=document.querySelector('[data-source-back]');back.hidden=!parentEvidenceDialog;
    back.textContent=parentEvidenceDialog?.classList.contains('subagent-dialog')?'Back to subagent':parentEvidenceDialog?.classList.contains('failure-dialog')?'Back to failures':'Back to finding';
  }
  function reopenSource(trigger) {
    if(!selectedSource){
      const first=accounting.turns[0]?.request_event_id || Object.values(sources).find(s=>s.agent_id==='main')?.id;
      if(embedded && first)showSource({source_id:first},null,trigger);
      return;
    }
    sourceReturnFocus=trigger;
    parentEvidenceDialog=document.querySelector('.finding-dialog[open],.failure-dialog[open],.subagent-dialog[open]');
    parentEvidenceDialog?.close();syncSourceBack();
    preserveReportPosition(()=>{sourceDialog.hidden=false;document.body.classList.add('has-source');syncInspectorMode();});
    sourceDialog.scrollTop=sourceScrollTop;sourceDialog.focus({preventScroll:true});
  }
  function toggleSourceWidth() {
    const scroll=sourceDialog.scrollTop;
    preserveReportPosition(()=>{sourceExpanded=!sourceExpanded;syncInspectorMode();});
    sourceDialog.scrollTop=scroll;
  }
  function returnFromSource() {
    const parent=parentEvidenceDialog;
    closeSource(!parent);parentEvidenceDialog=null;
    if(parent)parent.showModal();
  }
  function sourceRelevance(ref,s,context) {
    const container=document.getElementById('source-relevance');container.replaceChildren();
    let explanation=ref.explanation, quote=null, range=null, origin='Saved citation · Claude';
    // A review note belongs to a specific immutable record, not to every claim
    // that happens to cite the same source. Never borrow a superseded review.
    const reviews=(data.review_checks || []).filter(r=>context?.owner_id && r.check.record_id===context.owner_id);
    const review=reviews[reviews.length-1];
    if(!explanation && review) {
      for(const [index,item] of review.check.evidence_checks.entries()) {
        const exact=review.verified_quote_ranges?.[index];
        const sameSource=item.reference.source_id===s.id && exact?.source_id===s.id && exact.text_sha256===s.text_sha256;
        const inside=!ref.text_sha256 || ref.text_sha256===exact?.text_sha256 && ref.start_char<=exact.start_char && ref.end_char>=exact.end_char;
        if(sameSource && inside) {
          explanation=item.supports_or_contradicts;quote=item.quote;range=exact;
          origin='Saved review · Claude · '+label(review.check.verdict);break;
        }
      }
    }
    const heading=document.createElement('p');heading.className='small muted';heading.textContent=explanation?'Why this source':'Source context';
    const sentence=document.createElement('p');sentence.className='prose source-explanation';
    if(explanation) sentence.textContent=explanation;
    else if(context) sentence.textContent='This record is cited in the linked analysis; no source-specific explanation was saved.';
    else {
      const turn=sourceTurns.get(s.id),where=turn?' for turn '+turn.index:s.agent_id && s.agent_id!=='main'?' in this child trajectory':'';
      const kind=({user_statement:'the recorded user request',tool_call:'the recorded tool input',tool_result:'the captured tool result',assistant_statement:'the assistant’s recorded statement',assistant_thinking:'the captured assistant thinking record',assistant_record:'an assistant record without statement text',system_status:'the recorded system status',artifact:'the admitted artifact snapshot'})[s.role] || 'a saved trajectory record';
      sentence.textContent='This is '+kind+where+'.';
    }
    container.append(heading,sentence);
    if(explanation) {const provenance=document.createElement('p');provenance.className='small muted';provenance.textContent=origin;container.append(provenance);}
    if(quote) {const excerpt=document.createElement('blockquote');excerpt.className='source-excerpt';excerpt.textContent=quote;container.append(excerpt);}
    const limits=[...(context?.limitations || []),...(explanation && review?review.check.remaining_uncertainty || []:[])];
    if(context?.text || limits.length) {
      const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=context?.label || 'Interpretation limits';details.append(summary);
      if(context?.text){const p=document.createElement('p');p.className='prose';p.textContent=context.text;details.append(p);}
      for(const limit of new Set(limits)){const p=document.createElement('p');p.className='limit small prose';p.textContent=limit;details.append(p);}
      container.append(details);
    }
    return range;
  }
  function showSource(ref,citationContext=null,trigger=null) {
    hideWrapTooltip();
    const s = sources[ref.source_id];
    if (!s) { announce('Source is not embedded in this report. Its identifier remains in the saved evidence.'); return; }
    // Some browsers do not focus buttons on pointer activation.
    const origin=trigger || document.activeElement;
    // Preserve the clicked control itself: a panel above it can reflow when
    // the inspector narrows the report, even if its turn heading stays put.
    const anchor=origin?.closest('#report-column') ? origin : null;
    const anchorY=anchor?.getBoundingClientRect().top;
    if(anchor)sourceReportAnchor=anchor;
    if (sourceDialog.hidden) sourceReturnFocus=origin;
    const openParent=document.querySelector('.finding-dialog[open],.failure-dialog[open],.subagent-dialog[open]');
    if (openParent) { parentEvidenceDialog=openParent; openParent.close(); }
    selectedSource=s.id;sourceDialog.dataset.selectedSource=s.id;
    const reviewRange=sourceRelevance(ref,s,citationContext);
    const selectedCitation=reviewRange || ref;
    document.querySelector('[data-copy-source]').hidden=!hasSourceText(s);
    document.querySelector('[data-copy-source]').disabled=!hasSourceText(s);
    document.getElementById('source-title').textContent='Source';
    const linkedTools=(s.tool_ids || []).map(id=>tools.get(id)).filter(Boolean);
    const tool=linkedTools.length===1?linkedTools[0]:null;
    const turn=sourceTurns.get(s.id);
    document.getElementById('source-kind').textContent=sourceName(s)+(tool?' · '+tool.name:'');
    document.getElementById('source-time').textContent=s.timestamp?s.timestamp.replace('T',' · ').replace('+00:00',' UTC').replace(/Z$/,' UTC'):'Timestamp unavailable';
    document.getElementById('source-meta').textContent=[s.agent_id ? 'Agent '+s.agent_id : null,...(s.source_refs || []).map(r=>'Member '+r.member_id+' · line '+r.line)].filter(Boolean).join(' · ');
    const nav=document.getElementById('source-nav');nav.replaceChildren();
    const previous=iconButton('Previous','chevron-left',trigger=>showSource({source_id:s.previous},null,trigger));previous.disabled=!s.previous;previous.setAttribute('aria-label','Previous source record');
    const next=iconButton('Next','chevron-right',trigger=>showSource({source_id:s.next},null,trigger));next.disabled=!s.next;next.setAttribute('aria-label','Next source record');
    const owner=document.createElement('strong');owner.textContent=turn?'Turn '+turn.index:s.agent_id && s.agent_id!=='main'?'Child agent':'Source record';
    nav.append(previous,owner,next);
    const disclosure=s.disclosure || {},limits=[];
    if (disclosure.redaction_matches) limits.push(disclosure.redaction_matches+' pattern redactions');
    if(citationContext && !hasSourceText(s))limits.push('This record has no available evidence text and cannot substantiate the linked claim.');
    const content=document.getElementById('source-text');content.replaceChildren();
    const text=sourceText(s),chars=Array.from(text);
    const cited=hasSourceText(s) && selectedCitation.text_sha256===s.text_sha256 && Number.isInteger(selectedCitation.start_char) && Number.isInteger(selectedCitation.end_char) && selectedCitation.end_char>selectedCitation.start_char;
    if (cited) {
      content.append(document.createTextNode(chars.slice(0,selectedCitation.start_char).join('')));
      const mark=document.createElement('mark');mark.textContent=chars.slice(selectedCitation.start_char,selectedCitation.end_char).join('');content.append(mark,document.createTextNode(chars.slice(selectedCitation.end_char).join('')));
      limits.push('Citation highlighted in Saved source and citation');
    } else { content.textContent=text;if(ref.text_sha256 && ref.text_sha256!==s.text_sha256)limits.push('Citation fingerprint differs; range not highlighted'); }
    document.getElementById('source-raw').open=cited;
    document.getElementById('source-raw').hidden=!hasSourceText(s);
    document.getElementById('source-limit').textContent=limits.join(' · ');
    const {text:ignoredText,previous:ignoredPrevious,next:ignoredNext,content_metadata:contentMetadata,...identity}=s;
    if(contentMetadata){const {thinking_text:ignoredThinking,...metadata}=contentMetadata;identity.content_metadata=metadata;}
    document.getElementById('source-identity').textContent=JSON.stringify({...identity,citation:ref,highlighted_review_quote:reviewRange},null,2);
    const panels=document.getElementById('source-panels');panels.replaceChildren();
    if (tool) {
      const input=sources[tool.evidence_id],fields=inputFields(input,tool);
      if (input) {
        const command=['Bash','Shell','shell'].includes(tool.name) && typeof fields?.values?.command==='string'?fields.values.command:null;
        panels.append(codePanel('Input',command ?? fields?.raw ?? sourceText(input),command!==null?'shell':fields?'json':'text',input.id,{selectable:input.id!==s.id,available:input.text!==undefined,displayText:command===null && fields?JSON.stringify(fields.values,null,2):undefined}));
        if (command!==null) { const all=document.createElement('details');const summary=document.createElement('summary');summary.textContent='All input fields';all.append(summary,codePanel('Input fields',fields.raw,'json',input.id,{displayText:JSON.stringify(fields.values,null,2)}));panels.append(all); }
      }
      const results=tool.evidence.map(id=>sources[id]).filter(x=>x?.role==='tool_result');
      for (const [index,result] of results.entries()) panels.append(codePanel('Result'+(results.length>1?' '+(index+1):''),sourceText(result),languageForResult(tool,fields),result.id,{savedLineNumbers:true,selectable:result.id!==s.id,available:result.text!==undefined}));
      if (!results.length) { const note=document.createElement('p');note.className='limit small';note.textContent='No result record was captured for this invocation.';panels.append(note); }
    } else panels.append(codePanel('Record',text,'text',s.id,{available:s.text!==undefined}));
    if(hasSourceText(s) && contentReasons(s).length)panels.append(sourceNotice(s));
    for(const [index,block] of (s.content_metadata?.thinking_text || []).entries()){
      panels.append(codePanel('Captured thinking'+(s.content_metadata.thinking_text.length>1?' '+(index+1):''),block.text,'text',s.id));
    }
    if(s.content_metadata?.thinking_text?.length){const p=document.createElement('p');p.className='small muted';p.textContent='Captured thinking is a planning record, not proof that an action ran.';panels.append(p);}
    sourceAccounting(s);
    const related=document.getElementById('source-related');related.replaceChildren();
    for (const t of linkedTools) {
      if (delegations.has(t.id)) related.append(button('Subagent details',()=>showSubagent(t.id)));
      if (!tool) for (const sid of t.evidence) if (sid!==s.id) related.append(button(t.name+' · '+label(sources[sid]?.role),trigger=>showSource({source_id:sid},null,trigger)));
    }
    const context=document.getElementById('source-context-records');context.replaceChildren();
    const before=[],after=[];let cursor=s;
    for(let i=0;i<2 && sources[cursor.previous];i++){cursor=sources[cursor.previous];before.unshift(cursor.id);}
    cursor=s;for(let i=0;i<2 && sources[cursor.next];i++){cursor=sources[cursor.next];after.push(cursor.id);}
    for(const sid of [...before,s.id,...after])appendEvent(context,sid);
    syncSourceBack();
    document.querySelectorAll('.selected-source,.source-selected').forEach(el=>el.classList.remove('selected-source','source-selected'));
    if(turn){if(document.getElementById(turn.id)?.hidden)showAllTurns();document.getElementById(turn.id)?.classList.add('source-selected');}
    document.querySelectorAll('[data-source-record]').forEach(el=>el.classList.toggle('selected-source',el.dataset.sourceRecord===s.id));
    sourceDialog.hidden=false;document.body.classList.add('has-source');syncInspectorMode();sourceDialog.scrollTop=0;
    if(anchor?.isConnected && anchorY!==undefined && !openParent && !mobileInspector.matches)window.scrollBy(0,anchor.getBoundingClientRect().top-anchorY);
    sourceDialog.focus({preventScroll:true});
    if(cited){const mark=content.querySelector('mark');content.scrollTop=Math.max(0,mark.offsetTop-content.offsetTop-30);}
  }
  function appendEvent(parent,sid) {
    const s=sources[sid] || {id:sid};
    const row=document.createElement('div'); row.className='event-row';row.dataset.sourceRecord=sid;row.classList.toggle('selected-source',sid===selectedSource);
    const time=document.createElement('span'); time.textContent=s.timestamp || 'Timestamp unavailable';
    const invocations=(s.tool_ids || []).filter(tid=>delegations.has(tid) && tools.get(tid)?.evidence_id===sid);
    const controls=document.createElement('div');
    if (invocations.length) {
      for (const tid of invocations) controls.append(button(delegations.get(tid).name+' invocation',()=>showSubagent(tid)));
    } else controls.append(iconButton(sourceName(s),'link-2',trigger=>showSource({source_id:sid},null,trigger)));
    row.append(time,controls);
    const preview=document.createElement('p'); preview.className='event-preview';
    const text=hasSourceText(s)?s.text:contentReasons(s).join(' '); preview.textContent=text.slice(0,240)+(text.length>240?'…':'');
    row.append(preview); parent.append(row);
  }
  function renderAgentEvents(id,dialog) {
    const a=agents[id]; if (!a || !dialog) return;
    const parent=dialog.querySelector('[data-agent-events="'+CSS.escape(id)+'"]');
    const key=dialog.id+':'+id, offset=agentCursors.get(key)||0;
    const ids=a.event_ids.slice(offset,offset+20);
    for (const sid of ids) appendEvent(parent,sid);
    const next=offset+ids.length; agentCursors.set(key,next);
    const more=dialog.querySelector('[data-agent-more="'+CSS.escape(id)+'"]');
    more.hidden=next>=a.event_ids.length;
    more.textContent='Show next child records ('+next+' of '+a.event_ids.length+' shown)';
  }
  function renderEvents(id) {
    const t=turns.get(id); if (!t) return;
    const parent=document.querySelector('[data-events="'+CSS.escape(id)+'"]');
    const offset=cursors.get(id)||0;
    const ids=t.event_ids.slice(offset,offset+20);
    for (const sid of ids) appendEvent(parent,sid);
    const next=offset+ids.length; cursors.set(id,next);
    const more=document.querySelector('[data-more="'+CSS.escape(id)+'"]');
    more.hidden=next>=t.event_ids.length;
    more.textContent='Show next records ('+next+' of '+t.event_ids.length+' shown)';
  }
  function toggleTurn(id,forceOpen=false) {
    const t=turns.get(id); if (!t) return;
    if(document.getElementById(id).hidden)showAllTurns();
    const detail=document.getElementById('detail-'+id);
    const control=document.querySelector('.turn-toggle[data-turn="'+CSS.escape(id)+'"]');
    const open=forceOpen || detail.hidden; detail.hidden=!open;
    control.setAttribute('aria-expanded',String(open));
    document.querySelector('.request-control[data-turn="'+CSS.escape(id)+'"]')?.setAttribute('aria-expanded',String(open));
    control.setAttribute('aria-label',(open?'Collapse':'Expand')+' turn '+(accounting.turns.indexOf(t)+1));
    control.replaceChildren(icon('chevron-right'));
    document.getElementById(id).classList.toggle('expanded-turn',open);
    document.getElementById(id).hidden=false;
    if (open && !cursors.has(id)) {
      const request=detail.querySelector('[data-request]'); request.textContent=sourceText(sources[t.request_event_id]||{});
      renderEvents(id);
    }
  }
  function announce(message) {
    clearTimeout(copyTimer); document.getElementById('copy-status').textContent=message;
    copyTimer=setTimeout(()=>document.getElementById('copy-status').textContent='',5000);
  }
  async function copyExact(exact,message) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(exact);
      else {
        const input=document.createElement('textarea');input.value=exact;input.style.position='fixed';input.style.left='-10000px';document.body.append(input);input.select();
        const copied=document.execCommand('copy');input.remove();if (!copied) throw new Error('Clipboard unavailable');
      }
      announce(message);
    } catch (_) { announce('Copy failed. Select the saved text to copy it manually.'); }
  }
  function copyProposal(id) {
    const edit=proposals.get(id)?.edit;if(!edit)return;
    return copyExact(edit.operation==='invoke'?edit.invocation:edit.replacement_text,edit.operation==='invoke'?'Invocation copied.':'Exact proposed text copied.');
  }
  function showAllTurns() {
    filterTurns(null);
  }
  function filterTurns(ids) {
    const selected=ids?new Set(ids):null;
    let count=0;
    for(const t of turns.values()){
      const row=document.getElementById(t.id),shown=!selected||selected.has(t.id);
      row.hidden=!shown;if(shown)count++;
      document.getElementById('detail-'+t.id).hidden=!shown||!row.classList.contains('expanded-turn');
    }
    document.getElementById('turn-selection-status').textContent=selected?count+' of '+turns.size+' turns · explicit evidence links':turns.size+' turns · complete chronology';
    document.querySelector('[data-all-turns]')?.setAttribute('aria-pressed',String(!selected));
  }
  function openRequirement(id,forceOpen=false) {
    const row=document.getElementById(id),detail=document.getElementById('detail-'+id);
    if(!row||!detail)return;
    document.getElementById('requirements').open=true;
    const open=forceOpen||detail.hidden;detail.hidden=!open;
    row.classList.toggle('expanded-requirement',open);
    row.querySelector('[data-requirement]').setAttribute('aria-expanded',String(open));
    if(forceOpen){row.scrollIntoView({block:'start'});row.querySelector('button').focus({preventScroll:true});}
  }
  function exportReport(format) {
    const content=format==='json'?JSON.stringify(data,null,2)+'\n':'<!doctype html>\n'+document.documentElement.outerHTML;
    const blob=new Blob([content],{type:format==='json'?'application/json':'text/html'});
    const url=URL.createObjectURL(blob); const a=document.createElement('a');
    a.href=url; a.download='ally-'+data.investigation.id+'.'+format; document.body.append(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000); document.querySelector('.export').open=false;
  }
  function resourcePage(container, reset=false) {
    const rows=Array.from(container.querySelector('table > tbody').children);
    const shown=reset?30:Number(container.dataset.shown || 30)+30;
    rows.forEach((row,index)=>{row.hidden=index>=shown;});container.dataset.shown=String(shown);
    const more=container.querySelector('[data-resource-more]');more.hidden=shown>=rows.length;
    more.textContent='Show next records ('+Math.min(shown,rows.length)+' of '+rows.length+' shown)';
  }
  document.addEventListener('click',event=>{
    const control=event.target.closest('button,a'); if (!control) return;
    if (control.hasAttribute('data-all-turns')) showAllTurns();
    else if(control.hasAttribute('data-focus-turns')) {
      control.closest('dialog')?.close();filterTurns(JSON.parse(control.dataset.focusTurns));
      document.getElementById('turns-heading').scrollIntoView({block:'start'});
      document.querySelector('[data-all-turns]')?.focus({preventScroll:true});
    }
    else if(control.dataset.requirement)openRequirement(control.dataset.requirement);
    else if(control.dataset.openRequirement)openRequirement(control.dataset.openRequirement,true);
    else if(control.hasAttribute('data-map-review')){
      const map=document.getElementById('requirements');map.open=true;
      const assessment=map.querySelector('.review-qualification');
      assessment?.querySelector('details')?.setAttribute('open','');
      if(assessment){assessment.setAttribute('tabindex','-1');assessment.scrollIntoView({block:'start'});assessment.focus({preventScroll:true});}
    }
    else if(control.hasAttribute('data-resource-more')) resourcePage(control.closest('.resource-page'));
    else if(control.hasAttribute('data-copy-field')) {
      const field=document.getElementById(control.dataset.copyField);
      if(field)copyExact(field.textContent,'Saved field copied exactly.');
    }
    else if(control.hasAttribute('data-copy-source') && selectedSource) copyExact(sourceText(sources[selectedSource]),'Selected source copied exactly.');
    else if(control.hasAttribute('data-source-close')) returnFromSource();
    else if(control.hasAttribute('data-source-reopen')) reopenSource(control);
    else if(control.hasAttribute('data-source-expand')) toggleSourceWidth();
    else if (control.hasAttribute('data-ref')) showSource(JSON.parse(control.dataset.ref),control.dataset.sourceContext?JSON.parse(control.dataset.sourceContext):null,control);
    else if (control.dataset.finding) showEvidenceDialog('finding-',control.dataset.finding);
    else if (control.dataset.failures) showEvidenceDialog('failures-',control.dataset.failures);
    else if (control.dataset.subagent) showSubagent(control.dataset.subagent);
    else if (control.dataset.agentMore) renderAgentEvents(control.dataset.agentMore,control.closest('dialog'));
    else if (control.dataset.turn) toggleTurn(control.dataset.turn);
    else if (control.dataset.more) renderEvents(control.dataset.more);
    else if (control.dataset.copy) copyProposal(control.dataset.copy);
    else if (control.dataset.export) exportReport(control.dataset.export);
    else if (control.hasAttribute('data-close')) {
      control.closest('dialog').close();
    }
    else if (control.hasAttribute('data-source-back') && parentEvidenceDialog) {
      closeSource(false); parentEvidenceDialog.showModal(); parentEvidenceDialog=null;
    } else if (control.hasAttribute('data-proposal-link')) {
      control.closest('dialog').close(); const target=document.querySelector(control.getAttribute('href'));
      target?.setAttribute('tabindex','-1'); target?.focus();
    } else if (control.dataset.turnLink) {
      control.closest('dialog')?.close(); toggleTurn(control.dataset.turnLink,true);
      document.querySelector('[data-turn="'+CSS.escape(control.dataset.turnLink)+'"]')?.focus();
    }
  });
  mobileInspector.addEventListener('change',syncInspectorMode);
  document.addEventListener('keydown',event=>{
    if(sourceDialog.hidden || document.querySelector('dialog[open]'))return;
    if(event.key==='Escape'){event.preventDefault();returnFromSource();}
    if(event.key==='Tab' && (mobileInspector.matches || sourceExpanded)){
      const focusable=[...sourceDialog.querySelectorAll('button:not([disabled]),summary,[tabindex="0"]')].filter(el=>el.getClientRects().length);
      const first=focusable[0],last=focusable[focusable.length-1];
      if(event.shiftKey && (document.activeElement===first || document.activeElement===sourceDialog)){event.preventDefault();last?.focus();}
      else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
    }
  });
  for(const link of document.querySelectorAll('.report-nav a'))link.addEventListener('click',()=>{
    document.querySelectorAll('.report-nav a').forEach(a=>a.removeAttribute('aria-current'));link.setAttribute('aria-current','location');
    const target=document.querySelector(link.getAttribute('href'));if(target?.tagName==='DETAILS')target.open=true;
  });
  for(const container of document.querySelectorAll('[data-episode]')){
    container.addEventListener('toggle',()=>{if(container.open)compareAttempts(container);});
    container.addEventListener('change',()=>compareAttempts(container));
    if(container.open)compareAttempts(container);
  }
  // Exported HTML may retain expanded rows; discard transient rendering, then rebuild once.
  for (const t of turns.values()) {
    const detail=document.getElementById('detail-'+t.id);
    const events=detail?.querySelector('[data-events]'); events?.replaceChildren();
    if (detail && !detail.hidden) toggleTurn(t.id,true);
  }
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.removeAttribute('open');
  for (const container of document.querySelectorAll('[data-agent-events]')) container.replaceChildren();
  for (const container of document.querySelectorAll('.resource-page')) resourcePage(container,true);
  closeSource(false,false);parentEvidenceDialog=null;
  document.getElementById('copy-status').textContent='';
})();
