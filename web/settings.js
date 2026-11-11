/* Categorized settings backed by the local API. */
(()=>{
 const groups=[['Account',['Profile','Sign-in & devices','Cloud sync','Insights']],['Workspace',['Default folder','Tools & permissions','Memory & context','Extensions']],['Models & voice',['Models','Model roles','Orchestration','Model services','Paired PCs','Hardware & tuning','Voice']],['App',['Appearance','Updates']]];
 const labels={Models:'Model library',Orchestration:'Auto mode','Tools & permissions':'Permissions'};
 const sections=groups.flatMap(([,pages])=>pages);
 const aliases={Inference:'Default folder','Working folder':'Default folder','Model library':'Models',Account:'Profile',Accounts:'Profile','Sign-in methods':'Sign-in & devices','Devices & security':'Sign-in & devices','Auto mode':'Orchestration',Permissions:'Tools & permissions'};
 let library,picking=null,selectedKey,selectedQuant,modelFilter='all',capabilityFilter='',benchmarkOpen=false,libraryGeneration=0,libraryTimer;
 const original=openPanel;
 openPanel=async function(name){if(['settings','models'].includes(name))return settingsView(name==='models'?'Models':({Account:'Profile',Accounts:'Profile'}[window.studioSettingsCategory]||window.studioSettingsCategory||'Profile'));$('.sheet').classList.remove('settings-sheet');return original(name)};
 const row=(title,description,value)=>`<div class="setting-row"><div><h3>${title}</h3><p>${description}</p></div><span class="badge">${value}</span></div>`;
 function stopLibraryPoll(){clearTimeout(libraryTimer);libraryGeneration++}
 async function settingsView(section){
  section=aliases[section]||section;
  if(['Extensions','Integrations','Marketplace'].includes(section))return window.openExtensions(section==='Integrations'?'connectors':section==='Marketplace'?'browse':'installed');
  if(!sections.includes(section))section='Profile';
  stopLibraryPoll();
  const generation=libraryGeneration;
  const oldNav=$('.settings-navigation'),navScroll=oldNav?.scrollTop||0,search=$('#settings-search')?.value||'';
  showPanel('Settings','Your app, configured your way.',`<div class="settings-layout"><nav class="settings-nav" aria-label="Settings categories"><label class="settings-search"><input id="settings-search" type="search" placeholder="Find a setting…" aria-label="Find a setting"></label><div class="settings-navigation">${groups.map(([label,pages])=>`<section class="settings-nav-group"><h3>${label}</h3>${pages.map(s=>`<button data-settings-section="${s}" aria-current="${s===section?'page':'false'}">${labels[s]||s}</button>`).join('')}</section>`).join('')}</div><p>Settings are saved<br>on this PC.</p><button id="settings-logout" class="settings-logout" type="button">Log out</button></nav><section id="settings-body" class="settings-body"></section></div>`);
  $('.sheet').classList.add('settings-sheet');$$('[data-settings-section]').forEach(b=>b.onclick=safe(()=>settingsView(b.dataset.settingsSection)));
  $('#settings-search').oninput=e=>{const q=e.target.value.toLowerCase();$$('[data-settings-section]').forEach(b=>b.hidden=!b.textContent.toLowerCase().includes(q));$$('.settings-nav-group').forEach(g=>g.hidden=![...g.querySelectorAll('button')].some(b=>!b.hidden))};
  $('#settings-logout').onclick=safe(async()=>{if(!confirm('Log out on this PC? Your chats and files stay here.'))return;const button=$('#settings-logout');button.disabled=true;try{const r=await api('/identity/logout','POST',{});closePanel();await showGate({reason:r.message||'Signed out. Choose an account to continue.'})}finally{button.disabled=false}});
  const body=$('#settings-body');body.dataset.accountView=section;
  $('.settings-navigation').scrollTop=navScroll;$('#settings-search').value=search;$('#settings-search').oninput({target:$('#settings-search')});
  body.innerHTML='<p role="status" class="settings-loading">Loading settings…</p>';
  try{
  if(section==='Cloud sync'){await renderCloudSync(body);return}
  if(section==='Model services'||section==='Paired PCs'){
   const services=section==='Model services';
   body.innerHTML=`<h3 class="settings-page-title">${section}</h3><p class="settings-intro">${services?'Use AI models from online services or apps like Ollama and LM Studio alongside the models on this PC. Nothing is sent to them unless you pick one of their models or give it a role.':'Pair your PCs running Luminaria. Their models join yours: Luminaria picks the best one for each job, and can split big models across your graphics cards.'}</p><div class="ext-page"></div>`;
   await window.mountExtensionPage(body.querySelector('.ext-page'),services?'services':'pcs');return}
  if(section==='Model roles'){
   const [s,list]=await Promise.all([api('/settings'),api('/models')]);if(!body.isConnected)return;
   const models=list.models.filter(m=>m.installed),opt=(v,label,cur)=>`<option value="${esc(v)}" ${cur===v?'selected':''}>${esc(label)}</option>`;
   const pick=(name,cur,autoLabel)=>`<select name="${name}">${opt('auto',autoLabel,cur||'auto')}${opt('chat','Same as the chat model',cur)}${models.map(m=>opt(m.id,m.name,cur)).join('')}</select>`;
   const now=id=>esc(list.models.find(m=>m.id===id)?.name||'none installed yet');
   body.innerHTML=`<h3 class="settings-page-title">Model roles</h3><p class="settings-intro">Luminaria gives different jobs to different models and loads them as needed. Automatic picks only use this PC and your paired PCs, never an online service unless you choose one here.</p>
    <div class="s-card">
     <label class="setting-row"><div><h3>Planning model</h3><p>Makes plans with you and checks finished work, with thinking on. Now: ${now(list.roles?.planner)}.</p></div>${pick('planner_model',s.planner_model,'Automatic · strongest reasoning model')}</label>
     <label class="setting-row"><div><h3>Coding model</h3><p>Does the coding steps when a plan is carried out. Choose a model service here to relay that work while this PC plans and checks. Now: ${now(list.roles?.coder)}.</p></div>${pick('coder_model',s.coder_model,'Automatic · best coding model')}</label>
     <label class="setting-row"><div><h3>Spoken replies</h3><p>Choose a fast local model for quick voice conversation.</p></div><select name="voice_model">${opt('','Same as the chat model',s.voice_model||'')}${models.filter(m=>m.model_file).map(m=>opt(m.id,m.name,s.voice_model)).join('')}</select></label>
     <div class="setting-row"><div><h3>Chat model</h3><p>Everything else: the model you pick in the message box, or Auto.</p></div><span class="badge">${esc(list.models.find(m=>m.id===s.model)?.name||s.model||'—')}</span></div>
    </div><p class="small-note" role="status" id="roles-state"></p>`;
   body.querySelectorAll('select').forEach(sel=>sel.addEventListener('change',safe(async()=>{await api('/settings','POST',{[sel.name]:sel.value});toast('Saved');await settingsView('Model roles')})));
   return}
  if(['Profile','Sign-in & devices'].includes(section)){await renderAccounts(body);return}
  if(section==='Integrations'){body.innerHTML='<h3 class="settings-page-title">Integrations</h3><p class="settings-intro">Connect outside services. Each one adds its own tools once you sign in to it.</p><div id="tools-body"></div>';await renderIntegrations(body.querySelector('#tools-body'));return}
  if(section==='Default folder'){await studioSettingsSection('Inference',body);await renderAccountProfiles(body);return}
  if(section==='Models'){
   picking=null;library=await api('/model-library'); if(generation!==libraryGeneration)return; window.studioMachine=library.machine||null;
   const active=library.models.flatMap(m=>m.quants.map(q=>({key:m.key,quant:q}))).find(item=>item.quant.active);
   selectedKey=selectedKey&&library.models.some(m=>m.key===selectedKey)?selectedKey:(active?.key||library.models[0]?.key);
   body.innerHTML=`<h3 class="settings-page-title">Model library</h3><p class="settings-intro">Download a quantization, then measure it on this PC. AI scores rate each model's overall ability out of 100, tested on this PC.</p><section class="model-health" id="model-health" role="status" hidden></section><section class="model-storage" aria-labelledby="storage-drive"><div class="storage-title"><strong id="storage-drive"></strong><span id="storage-free"></span></div><div class="storage-bar" id="storage-bar" role="img"><span class="seg-other" id="seg-other"></span><span class="seg-models" id="seg-models"></span><span class="seg-pending" id="seg-pending"></span></div><ul class="storage-legend" id="storage-legend"></ul><p class="storage-impact" id="storage-impact" aria-live="polite"></p><p class="small-note" id="storage-meta"></p><div class="model-bulk"><button type="button" class="btn" id="download-all">Download all that fit</button><button type="button" class="btn" id="score-all" title="Runs the AI score test on each installed model that has no score yet">Score my models</button><button type="button" class="btn quiet-danger" id="remove-all">Remove all models</button><button type="button" class="btn" id="select-models" aria-pressed="false">Select models</button></div></section><section class="fit-machine" id="fit-machine" aria-label="This PC"></section><div class="model-toolbar"><div class="model-filters" role="group" aria-label="Model groups"><button type="button" data-model-filter="all">All <span></span></button><button type="button" data-model-filter="standard">Standard <span></span></button><button type="button" data-model-filter="abliterated">Abliterated <span></span></button><button type="button" data-model-filter="installed">Installed <span></span></button></div><input class="model-search" id="model-search" type="search" placeholder="Find a model, publisher or quantization" aria-label="Find a model"><select class="model-sort" id="model-sort" aria-label="Sort models"><option value="fit">Best fit for this PC</option><option value="name">Name (A–Z)</option><option value="size-asc">Size (smallest first)</option><option value="size-desc">Size (largest first)</option><option value="params-desc">Parameters (most first)</option><option value="score">Best AI score</option><option value="newest">Recently added</option></select></div><div class="model-capabilities" role="group" aria-label="Filter by capability">${['Coding','Reasoning','Writing','Tools','Vision'].map(c=>`<button type="button" data-capability="${c}">${c}</button>`).join('')}</div><div class="model-browser"><div id="model-options" aria-label="Model choices"></div><article id="model-detail" aria-live="polite"></article></div><details class="advanced-settings"><summary>Advanced model settings</summary><div class="form-actions"><button class="btn" id="advanced-inference">Configure inference</button><button class="btn" id="start-manager">Start model manager</button><button class="btn" id="restart-manager">Restart model manager</button><button class="btn" id="unload-current">Unload model</button></div></details><details class="advanced-settings"><summary>Add a local GGUF model</summary><p class="note">Register a file that is already on this PC. This does not download weights.</p><form id="add-local-model">${field('Model ID','id','','text',true)}${field('Display name','name','','text',true)}${field('GGUF file path','model_file','','text',true)}${field('Vision projector path (optional)','projector_file','')}${field('Context tokens','context',16384,'number')}${field('Quantization','quantization','Unknown')}${field('Description and best uses','description','User-added model; capabilities not yet tested.')}<button class="btn primary" type="submit">Register model</button><p class="small-note">Restart the app after adding a model so the model manager reloads its registry.</p></form></details>`;
   const reload=async()=>{library=await api('/model-library');if(generation===libraryGeneration)draw()};
   body.querySelector('#download-all').onclick=safe(async()=>{
    const plan=await api('/model-library/download-all','POST',{});
    if(!plan.total_models){toast('Every model that fits this PC is already downloaded or downloading.');return}
    if(!plan.count){toast(`Not enough room: ${formatBytes(plan.available)} is available for models. Free up space or remove models first.`,true);return}
    const extra=plan.skipped?`\n\n${plan.skipped} more model${plan.skipped===1?'':'s'} won't fit in the space available, so ${plan.skipped===1?'it is':'they are'} skipped.`:'';
    if(!confirm(`Download ${plan.count} model${plan.count===1?'':'s'} (${formatBytes(plan.bytes)})? Each uses the best-fit size for this PC; models too large for it are left out. Downloads run one at a time and you can cancel any of them.${extra}`))return;
    const done=await api('/model-library/download-all','POST',{confirm:true});toast(`${done.queued} download${done.queued===1?'':'s'} queued.`);await reload();schedule()});
   body.querySelector('#score-all').onclick=safe(async()=>{
    const btn=body.querySelector('#score-all');
    const todo=(library?.models||[]).flatMap(m=>m.quants.filter(q=>q.installed&&q.registered&&!q.evaluations?.some(e=>e.score!=null)).map(q=>({id:q.registry_id,name:m.name+' '+q.label})));
    if(!todo.length){toast('Every installed model already has an AI score.');return}
    if(!confirm(`Score ${todo.length} model${todo.length===1?'':'s'}? Each one is loaded in turn and given the 36-question AI score test. This takes a few minutes per model.`))return;
    btn.disabled=true;let done=0;
    try{for(const item of todo){btn.textContent=`Scoring ${done+1} of ${todo.length}…`;try{await api('/models/'+encodeURIComponent(item.id)+'/evaluate','POST',{})}catch(error){toast(`${item.name}: ${error.message||'could not be scored'}`)}done++;await reload()}}
    finally{btn.disabled=false;btn.textContent='Score my models'}
    toast(`Scored ${done} model${done===1?'':'s'}. Sort by Best AI score to compare them.`)});
   body.querySelector('#remove-all').onclick=safe(async()=>{
    const count=(library.models||[]).reduce((n,m)=>n+(m.quants||[]).filter(q=>q.installed&&q.managed!==false&&q.kind!=='projector').length,0);
    if(!confirm(`Remove all ${count||''} downloaded model${count===1?'':'s'}? The model in use is stopped, every model file in the models folder is deleted and any downloads are cancelled. Chats, memory and settings stay. Models you added from another folder stay on disk. This cannot be undone.`))return;
    const done=await api('/model-library/remove-all','POST',{confirm:true});toast(done.message);await reload();if(typeof refresh==='function')refresh()});
   body.querySelector('#select-models').onclick=()=>{picking=picking?null:new Set();draw()};
   const pickedModels=()=>(library.models||[]).filter(m=>picking?.has(m.key));
   const removable=list=>list.flatMap(m=>m.quants.filter(q=>q.installed&&q.kind!=='projector').map(q=>q.registry_id||q.id));
   function pickBar(shown){
    const toggle=body.querySelector('#select-models');toggle.textContent=picking?'Done selecting':'Select models';toggle.setAttribute('aria-pressed',String(!!picking));
    let bar=body.querySelector('#model-pick-bar');
    if(!picking){bar?.remove();return}
    if(!bar){bar=document.createElement('div');bar.id='model-pick-bar';bar.className='model-pick-bar';bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Selected models');(body.querySelector('.model-browser')||$('#model-options')).before(bar)}
    const list=pickedModels(),ids=removable(list),get=list.filter(m=>!m.quants.some(q=>q.installed)).length;
    bar.innerHTML=`<span class="pick-count">${list.length?`${list.length} selected`:'Click models to select them'}</span><button type="button" class="btn" data-pick="all">Select all shown</button>${list.length?'<button type="button" class="btn" data-pick="none">Clear</button>':''}<span class="pick-actions"><button type="button" class="btn primary" data-pick="download" ${get?'':'disabled'}>Download ${get||''}</button><button type="button" class="btn quiet-danger" data-pick="remove" ${ids.length?'':'disabled'}>Remove ${ids.length||''}</button></span>`;
    bar.querySelector('[data-pick=all]').onclick=()=>{shown.forEach(m=>picking.add(m.key));draw()};
    bar.querySelector('[data-pick=none]')?.addEventListener('click',()=>{picking.clear();draw()});
    bar.querySelector('[data-pick=download]').onclick=safe(async()=>{
     const keys=pickedModels().map(m=>m.key);
     const plan=await api('/model-library/download-all','POST',{keys});
     if(!plan.count){toast(plan.total_models?'Not enough free space for the selected models.':'Nothing to download: the selected models are installed, downloading, or too large for this PC.');return}
     if(!confirm(`Download ${plan.count} model${plan.count===1?'':'s'} (${formatBytes(plan.bytes)})? Each uses the best-fit size for this PC.${plan.skipped?` ${plan.skipped} don't fit in the free space and are skipped.`:''}`))return;
     const done=await api('/model-library/download-all','POST',{keys,confirm:true});toast(`${done.queued} download${done.queued===1?'':'s'} queued.`);picking=null;await reload();schedule()});
    bar.querySelector('[data-pick=remove]').onclick=safe(async()=>{
     const ids=removable(pickedModels());if(!ids.length)return;
     const inUse=pickedModels().some(m=>m.quants.some(q=>q.active))?' The model in use is stopped first, and Luminaria switches to another downloaded model if there is one.':'';
     if(!confirm(`Uninstall ${ids.length} model file${ids.length===1?'':'s'}? They are deleted from the models folder (models added from another folder stay on disk). Chats and settings stay. This cannot be undone.${inUse}`))return;
     const done=await api('/model-library/remove-selected','POST',{ids,confirm:true});toast(done.message);picking=null;await reload();if(typeof refresh==='function')refresh()});
   }
   const busy=job=>job&&['downloading','queued','cancelling'].includes(job.status);
   const jobText=job=>job.status==='queued'?(job.queue_position>1?`Waiting. ${job.queue_position-1} ahead.`:'Waiting to start.'):job.status==='downloading'?`${formatBytes(job.received)} of ${formatBytes(job.total)} · ${Math.floor((job.received||0)*100/(job.total||1))}%`:job.status==='cancelling'?'Stopping…':job.error||job.status;
   const pct=(n,total)=>Math.max(0,Math.min(100,(n||0)*100/(total||1)));
   const tokens=n=>Number(n).toLocaleString();
   function eligibility(quant){
    if(!quant||!quant.downloadable||quant.installed)return {needed:0,ok:true,reason:''};
    const needed=Math.max(0,(quant.bytes||0)-(quant.job?.received||0)),after=library.storage.free-needed;
    if(after<1073741824)return {needed,after,ok:false,reason:`Not enough space. This needs ${formatBytes(needed)} and must leave 1 GB free.`};
    if(library.budget.used+(quant.bytes||0)>library.budget.limit)return {needed,after,ok:false,reason:`This would pass the ${formatBytes(library.budget.limit)} download budget. Remove a downloaded model or pick a smaller quantization.`};
    return {needed,after,ok:true,reason:''};
   }
   // AI score v2: 0-100 across six areas. Older results (the 12-question check) are shown as an old score until rescored.
   const AREA_NAMES={reasoning:'Reasoning',math:'Math',coding:'Coding',knowledge:'Knowledge',instructions:'Following instructions',tools:'Tool use'};
   const areaText=e=>Object.values(e.areas||{}).map(a=>`${a.label} ${a.passed}/${a.total}`).join(', ');
   function aiScore(m){
    const runs=m.quants.map(q=>q.evaluations?.[0]).filter(Boolean);
    const best=runs.filter(e=>e.score!=null).sort((a,b)=>b.score-a.score)[0];
    if(best)return {score:best.score,run:best};
    const old=runs.find(e=>e.coding&&e.reasoning);
    return old?{old:true,passed:old.coding.passed+old.reasoning.passed,total:old.coding.total+old.reasoning.total}:null;
   }
   function scoreChip(m){
    const s=aiScore(m);if(!s)return '';
    if(s.old)return `<small class="option-flag ai-score old" title="From the old 12-question check. Use Score my models to get the full AI score.">Old score ${s.passed}/${s.total}</small>`;
    const tone=s.score>=70?'high':s.score>=45?'mid':'low';
    return `<small class="option-flag ai-score ${tone}" title="AI score ${s.score}/100, tested on this PC. ${esc(areaText(s.run))}. Six areas count equally.">AI score ${s.score}</small>`;
   }
   function rowStatus(m){
    const active=m.quants.find(q=>q.active),installed=m.quants.filter(q=>q.installed),job=m.quants.map(q=>q.job).concat(m.projector?.job).find(j=>j&&['downloading','queued','paused','error','cancelling'].includes(j.status));
    if(active)return ['active','Active · '+active.label];
    if(job)return [job.status==='error'?'attention':'progress',job.status==='downloading'?`Downloading ${Math.floor((job.received||0)*100/(job.total||1))}%`:job.status==='queued'?'Queued':job.status==='error'?'Needs attention':job.status==='cancelling'?'Stopping':'Paused'];
    if(installed.length)return ['installed',installed.map(q=>q.label).join(', ')+' installed'];
    return ['',''];
   }
   function sizeRange(m){const sizes=m.quants.map(q=>q.bytes).filter(n=>n!=null);if(!sizes.length)return '';const lo=Math.min(...sizes),hi=Math.max(...sizes);return lo===hi?formatBytes(lo):`${(lo/1073741824).toFixed(1)}–${formatBytes(hi)}`}
   function actionButtons(model,quant,check){
    const job=quant.job,buttons=[];
    if(quant.downloadable&&!quant.installed){
     if(busy(job))buttons.push('<button class="btn" id="cancel-model" type="button">Pause download</button>');
     else if(job&&(job.status==='paused'||(job.status==='error'&&job.received)))buttons.push(`<button class="btn primary" id="download-model" type="button" ${check.ok?'':'disabled'}>Resume download</button>`,'<button class="btn" id="discard-model" type="button">Cancel and delete partial</button>');
     else if(job&&job.status==='error')buttons.push(`<button class="btn primary" id="download-model" type="button" ${check.ok?'':'disabled'}>Try again</button>`,'<button class="btn" id="discard-model" type="button">Dismiss</button>');
     else buttons.push(`<button class="btn primary" id="download-model" type="button" ${check.ok?'':'disabled'}>Download ${esc(quant.label)} · ${formatBytes(quant.bytes)}</button>`);
     return buttons.join('');
    }
    buttons.push(`<button class="btn ${quant.installed&&!quant.active?'primary':''}" id="choose-model" type="button" ${!quant.installed||quant.active?'disabled':''}>${quant.active?'Active model':quant.installed?'Use this model':'File missing'}</button>`);
    buttons.push(`<button class="btn" id="benchmark-model" type="button" ${!quant.installed||!quant.registered?'disabled':''} aria-expanded="${benchmarkOpen}" aria-controls="benchmark-preview">Benchmark</button>`);
    if(quant.installed||quant.registered)buttons.push(`<button class="btn quiet-danger" id="remove-model" type="button">${quant.managed?'Uninstall':'Remove from library'}</button>`);
    return buttons.join('');
   }
   function projectorBlock(model){
    const p=model.projector;if(!p)return '';
    const job=p.job,check=eligibility({downloadable:true,installed:p.installed,bytes:p.bytes,job});
    let status,actions;
    if(p.installed){status=p.verified?'Downloaded and verified':'Downloaded';actions=`<button class="btn quiet-danger" id="remove-projector" type="button" ${p.active?'disabled title="The active model is using it"':''}>Uninstall</button>`}
    else if(busy(job)){status=jobText(job);actions='<button class="btn" id="cancel-projector" type="button">Pause</button>'}
    else if(job&&(job.status==='paused'||job.status==='error')){status=job.error||'Paused';actions=`<button class="btn" id="download-projector" type="button" ${check.ok?'':'disabled'}>${job.received?'Resume':'Try again'}</button><button class="btn" id="discard-projector" type="button">${job.received?'Cancel and delete partial':'Dismiss'}</button>`}
    else{status='Not downloaded. Without it this model reads text only.';actions=`<button class="btn" id="download-projector" type="button" ${check.ok?'':'disabled'}>Add · ${formatBytes(p.bytes)}</button>`}
    return `<section class="projector-block" aria-label="Vision projector"><div><h4>Vision projector <span>${formatBytes(p.bytes)}</span></h4><p>${esc(status)}</p>${busy(job)?`<progress max="${job.total||1}" value="${job.received||0}" aria-label="Projector download progress"></progress>`:''}${p.note?`<p class="small-note">${esc(p.note)}</p>`:''}${!check.ok&&!p.installed?`<p class="small-note warn">${esc(check.reason)}</p>`:''}</div><div class="projector-actions">${actions}</div></section>`;
   }
   function drawStorage(quant){
    const storage=library.storage,budget=library.budget,total=storage.total||1;
    const check=eligibility(quant),models=storage.model_bytes||0,other=Math.max(0,(storage.used||0)-models),pending=check.needed||0;
    $('#storage-drive').textContent=`${storage.drive||'Model drive'} · ${formatBytes(storage.total)}`;
    $('#storage-free').textContent=`${formatBytes(storage.free)} free now`;
    $('#seg-other').style.width=pct(other,total)+'%';$('#seg-models').style.width=pct(models,total)+'%';
    const pendingSeg=$('#seg-pending');pendingSeg.style.width=pct(Math.min(pending,storage.free),total)+'%';pendingSeg.classList.toggle('over',!check.ok);
    const afterText=pending?formatBytes(Math.max(0,check.after)):formatBytes(storage.free);
    $('#storage-bar').setAttribute('aria-label',`${formatBytes(storage.used)} used of ${formatBytes(storage.total)}, ${formatBytes(models)} in model files${pending?`, selected download ${formatBytes(pending)}, ${afterText} free afterward`:''}`);
    $('#storage-legend').innerHTML=`<li><i class="seg-other"></i>Other files ${formatBytes(other)}</li><li><i class="seg-models"></i>Model files ${formatBytes(models)}</li>${pending?`<li><i class="seg-pending ${check.ok?'':'over'}"></i>Selected download ${formatBytes(pending)}</li>`:''}<li><i class="seg-free"></i>${pending?'Free afterward':'Free'} ${afterText}</li>`;
    $('#storage-impact').textContent=check.ok?'':check.reason;$('#storage-impact').hidden=check.ok;
    $('#storage-meta').textContent=`Downloads used ${formatBytes(budget.used)} of the ${formatBytes(budget.limit)} budget · ${storage.path}${storage.partial_bytes?` · ${formatBytes(storage.partial_bytes)} in unfinished downloads`:''}`;
    return check;
   }
   function draw(){
    const counts={all:library.models.length,standard:library.models.filter(m=>m.variant==='standard').length,abliterated:library.models.filter(m=>m.variant==='abliterated').length,installed:library.models.filter(m=>m.quants.some(q=>q.installed)).length};
    $$('[data-model-filter]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.modelFilter===modelFilter));b.querySelector('span').textContent=counts[b.dataset.modelFilter]});
    $$('[data-capability]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.capability===capabilityFilter)));
    const q=($('#model-search').value||'').toLowerCase().trim();
    const matching=library.models.filter(m=>{
     const hay=[m.name,m.family,m.purpose,m.description,m.provenance,m.repo,m.strengths.join(' '),m.quants.map(item=>item.label).join(' ')].join(' ').toLowerCase();
     if(q&&!q.split(/\s+/).every(word=>hay.includes(word)))return false;
     if(capabilityFilter&&!m.strengths.includes(capabilityFilter))return false;
     if(modelFilter==='installed')return m.quants.some(item=>item.installed);
     return modelFilter==='all'||m.variant===modelFilter;
    });
    const sortBy=$('#model-sort')?.value||'fit';
    const smallest=m=>Math.min(...m.quants.map(q=>q.bytes||Infinity));
    const billions=m=>{const t=String(m.parameters||'');const x=t.match(/(?:(\d+)x)?(\d+(?:\.\d+)?)\s*([BM])/i);if(!x)return 0;const n=parseFloat(x[2])*(x[3].toUpperCase()==='B'?1:0.001);return x[1]?n*+x[1]:n};
    const fitRank=m=>['recommended','good','slow','unstable','too_large','unknown'].indexOf(m.fit?.rating??'unknown');
    const order={name:(a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:'base'}),
     'size-asc':(a,b)=>smallest(a)-smallest(b),'size-desc':(a,b)=>smallest(b)-smallest(a),'params-desc':(a,b)=>billions(b)-billions(a),
     newest:(a,b)=>(b.discovered?1:0)-(a.discovered?1:0),score:(a,b)=>(aiScore(b)?.score??-1)-(aiScore(a)?.score??-1)||fitRank(a)-fitRank(b),fit:(a,b)=>fitRank(a)-fitRank(b)||smallest(b)-smallest(a)}[sortBy];
    if(order)matching.sort((a,b)=>order(a,b)||a.name.localeCompare(b.name));
    try{localStorage.setItem('model-sort',sortBy)}catch{}
    if(!matching.some(m=>m.key===selectedKey))selectedKey=matching[0]?.key;
    $('#model-options').innerHTML=['standard','abliterated'].map(group=>{const items=matching.filter(m=>m.variant===group);return items.length?`<section class="model-group ${group}" aria-label="${group==='standard'?'Standard':'Abliterated'} models"><h4>${group==='standard'?'Standard':'<span class="fractured-mark" aria-hidden="true"></span>Abliterated'} <span>${items.length}</span></h4>${items.map(m=>{const [tone,status]=rowStatus(m);return `<button type="button" class="model-option ${picking?(picking.has(m.key)?'picked':''):m.key===selectedKey?'selected':''}${m.variant==='abliterated'?' abliterated':''}${m.fit?' rated-'+m.fit.rating:''}" data-model-key="${esc(m.key)}" title="${esc(m.name)}" aria-pressed="${picking?picking.has(m.key):m.key===selectedKey}"><span class="option-line"><strong>${picking?`<span class="pick-box" aria-hidden="true">${picking.has(m.key)?'✓':''}</span>`:''}${m.variant==='abliterated'?'<span class="unbound-sigil" aria-hidden="true"></span>':''}${esc(m.name)}</strong>${window.LuminariaFit?LuminariaFit.badge(m.fit,true):''}<small class="option-size">${sizeRange(m)}</small></span><span class="option-line"><small>${esc(m.parameters)}${m.active_parameters?' · '+esc(m.active_parameters)+' active':''} · ${esc(m.purpose)}</small>${m.vision?'<small class="option-flag">Vision</small>':''}${scoreChip(m)}${m.context_supported&&m.context_supported<16384?`<small class="option-flag limit" title="This model can only follow a short conversation. That is a limit of the model, not your PC.">Short memory · ${Math.round(m.context_supported/1024)}k</small>`:''}</span>${status?`<small class="option-status ${tone}">${esc(status)}</small>`:''}</button>`}).join('')}</section>`:''}).join('')||`<div class="model-empty"><p>${modelFilter==='installed'&&!q&&!capabilityFilter?'No models are installed yet. Pick one under Standard or Abliterated to download it.':'No models match these filters.'}</p>${q||capabilityFilter?'<button class="btn" type="button" id="clear-model-filters">Clear filters</button>':''}</div>`;
    $$('[data-model-key]').forEach(b=>b.onclick=()=>{if(picking){const k=b.dataset.modelKey;picking.has(k)?picking.delete(k):picking.add(k);draw();return}selectedKey=b.dataset.modelKey;benchmarkOpen=false;draw()});
    pickBar(matching);
    const clear=$('#clear-model-filters');if(clear)clear.onclick=()=>{$('#model-search').value='';capabilityFilter='';draw()};
    const model=library.models.find(m=>m.key===selectedKey);
    if(!model){$('#model-detail').innerHTML='';$('#model-detail').className='empty';drawStorage(null);return}
    if(!model.quants.some(item=>item.id===selectedQuant))selectedQuant=model.quants.find(item=>item.active)?.id||model.quants.find(item=>item.installed)?.id||model.quants[0]?.id;
    const quant=model.quants.find(item=>item.id===selectedQuant)||model.quants[0];
    const check=drawStorage(quant);
    const kTok=n=>n>=1024?Math.round(n/1024)+'K':String(n);
    const verdict=item=>{const b=item.benchmarks?.[0],ctx=item.fit?.settings?.context;if(!b||!b.tps)return null;const t=b.tps,label=t>=25?'Fast':t>=12?'Good':t>=5?'Slow':'Very slow';return {label,tone:t>=25?'recommended':t>=12?'good':t>=5?'slow':'unstable',text:`${label} · ${t} tok/s`+(ctx?` · comfortable up to ${kTok(ctx)} context`:'')}};
    const benchChip=item=>{const v=verdict(item);return v?`<span class="fit-badge compact fit-${v.tone}" title="Measured on this PC">${esc(v.text)}</span>`:(item.installed?'<span class="quant-untested">Not tested</span>':'')};
    const measured=quant.benchmarks?.[0],job=quant.job;
    const quality=quant.evaluations?.[0];
    const abliterated=model.variant==='abliterated';
    const status=item=>item.active?'Active':item.installed?(item.verified?'Installed · verified':'Installed'):item.job?.status==='downloading'?`Downloading ${Math.floor((item.job.received||0)*100/(item.job.total||1))}%`:item.job?.status==='queued'?'Queued':item.job?.status==='paused'?'Paused':item.job?.status==='error'?'Needs attention':'';
    const context=(quant.context||model.context)?`<dd><span>${tokens(quant.context||model.context)} configured</span>${model.context_supported?`<small>${tokens(model.context_supported)} supported, from the file’s metadata</small>`:''}</dd>`:'<dd>Not recorded</dd>';
    const memory=model.cache_bytes!=null&&quant.memory_bytes?`<dd><span>About ${formatBytes(quant.memory_bytes)}</span><small>${formatBytes(quant.bytes)} weights + ${formatBytes(model.cache_bytes)} context cache${model.projector?(model.projector.installed?` + ${formatBytes(model.projector.bytes)} vision projector`:', plus the projector if added'):''}. An estimate, not a fit guarantee.</small></dd>`:`<dd>${esc(quant.memory||model.hardware)}</dd>`;
    const source=model.source_url?`<dd><a href="${esc(model.source_url)}" target="_blank" rel="noopener noreferrer">${esc(model.repo)}</a><small>Pinned to revision ${esc(model.source.split('@')[1]||'')}</small></dd>`:`<dd>${esc(model.provenance)}</dd>`;
    $('#model-detail').className=abliterated?'abliterated-card':'';
    $('#model-detail').innerHTML=`<header class="detail-head"><div class="detail-badges">${abliterated?'<span class="badge fractured-badge">Abliterated</span>':'<span class="badge">Standard</span>'}<span class="badge">${model.vision?'Text + vision':'Text'}</span>${model.local?'<span class="badge">Added on this PC</span>':''}</div><h3>${esc(model.name)}</h3><p class="detail-purpose">${esc(model.purpose)}</p></header><p class="model-description">${esc(model.description)}</p>${model.caveat?`<p class="abliterated-note">${esc(model.caveat)}</p>`:''}<div class="model-tags">${model.strengths.map(s=>'<span>'+esc(s)+'</span>').join('')}</div>${window.LuminariaFit?LuminariaFit.panel(model,quant):''}<fieldset class="quant-choices"><legend>Quantization</legend>${model.quants.map(item=>`<label><input type="radio" name="library-quant" value="${esc(item.id)}" ${item.id===quant.id?'checked':''}><span class="quant-label">${esc(item.label)}</span><span class="quant-size">${item.bytes==null?'Size unknown':formatBytes(item.bytes)}</span><span class="quant-memory">${item.memory_bytes?'≈ '+formatBytes(item.memory_bytes)+' memory':''}</span><span class="quant-status">${status(item)}</span><span class="quant-bench">${benchChip(item)}</span>${window.LuminariaFit?LuminariaFit.dot(item):''}</label>`).join('')}</fieldset>${job?`<div class="download-progress" aria-live="polite"><progress max="${job.total||1}" value="${job.received||0}" aria-label="Download progress"></progress><p>${esc(jobText(job))}</p></div>`:''}${!check.ok?`<p class="download-blocked" role="status">${esc(check.reason)}</p>`:''}<div class="model-actions">${actionButtons(model,quant,check)}</div>${projectorBlock(model)}<dl class="model-specs"><div><dt>Parameters</dt><dd>${esc(model.parameters)}${model.active_parameters?`<small>${esc(model.active_parameters)} used per token (mixture of experts)</small>`:''}</dd></div><div><dt>Context</dt>${context}</div><div><dt>Estimated memory${quant.context&&quant.context!==model.context&&model.cache_bytes?` at ${tokens(model.context)} tokens`:``}</dt>${memory}</div><div><dt>Source</dt>${source}</div><div><dt>Made by</dt><dd>${esc(model.provenance)}</dd></div><div><dt>License</dt><dd>${esc(model.license)}</dd></div></dl>${model.public_score?`<h4 class="measured-title">Published benchmark</h4><p>Epoch Capabilities Index <strong>${esc(model.public_score.eci)}</strong> <small>90% interval ${esc(model.public_score.low)}–${esc(model.public_score.high)}. Epoch AI, CC BY 4.0. Published model result.</small></p>`:'<p class="small-note">No exact match in the published Epoch AI results.</p>'}<h4 class="measured-title">Measured on this PC</h4>${verdict(quant)?`<p class="fit-meaning">${esc(verdict(quant).text)}. Saved for this quantization.</p>`:''}<dl class="model-specs measured"><div><dt>Generation speed</dt><dd>${measured?measured.tps+' tok/s':'Not measured'}</dd></div><div><dt>First token</dt><dd>${measured&&measured.first_token_seconds!=null?measured.first_token_seconds+' s':'Not measured'}</dd></div><div><dt>Tested context</dt><dd>${measured&&measured.context?tokens(measured.context)+' tokens':'Not measured'}</dd></div><div><dt>AI score</dt><dd>${quality?.score!=null?`<strong>${quality.score}/100</strong><small>${esc(areaText(quality))}</small>`:quality?`Old check: coding ${quality.coding.passed}/${quality.coding.total} · reasoning ${quality.reasoning.passed}/${quality.reasoning.total}`:'Not scored'}</dd></div></dl><p class="benchmark-caveat">${measured?esc(measured.test)+(measured.measurement?' · '+esc(measured.measurement):'')+'. Speed on this PC, not a coding or reasoning score.':quant.installed?'Speed has not been measured on this PC yet. Use Benchmark.':'Download this quantization to use or benchmark it. Nothing downloads until you choose Download.'}</p><section id="benchmark-preview" class="benchmark-preview" ${benchmarkOpen?'':'hidden'}><h4>Speed test</h4><p class="small-note">Runs a fixed 256-token generation test. It may load this model and take several minutes. It is not a coding or reasoning quality score.</p><button class="btn primary" id="run-benchmark">Run speed test</button><p id="benchmark-result" role="status"></p><h4>AI score</h4><p>Tests the model's overall ability with 36 fixed questions in six areas: reasoning, math, coding, knowledge, following instructions and tool use (the skill Luminaria needs to do work). Each area counts equally toward a score out of 100.</p><p class="small-note">Every question is graded automatically. Code is read, never run, and tool calls are checked, never run. Thinking is off and the temperature is 0, so results are repeatable. The score is measured on this PC and kept separate from speed.</p><button class="btn" id="run-quality">Run AI score test</button><p id="quality-result" role="status"></p></section><p class="small-note">One loaded model at a time. Finish active tasks before switching.</p>${quant.benchmarks?.length?'<details class="advanced-settings"><summary>All recorded speed tests</summary>'+quant.benchmarks.map(item=>`<p>${esc(item.test)} · <strong>${item.tps} tok/s</strong>${item.first_token_seconds!=null?' · '+item.first_token_seconds+' s to first token':''}</p>`).join('')+'</details>':''}${quant.evaluations?.length?'<details class="advanced-settings"><summary>All recorded AI scores</summary>'+quant.evaluations.map(item=>`<p>${esc(item.test)} · <strong>${item.score!=null?`AI score ${item.score}/100 · ${esc(areaText(item))}`:`Coding ${item.coding.passed}/${item.coding.total} · Reasoning ${item.reasoning.passed}/${item.reasoning.total}`}</strong></p><ul class="quality-items">${(item.items||[]).map(q=>`<li>${q.passed?'Correct':'Missed'} · ${esc((AREA_NAMES[q.kind]||q.kind)+': '+q.id.replaceAll('-',' '))}${q.passed?'':` · answered ${esc(q.given)}, expected ${esc(q.expected)}`}</li>`).join('')}</ul>`).join('')+'</details>':''}`;
    $$('#model-detail input[name=library-quant]').forEach(input=>input.onchange=()=>{selectedQuant=input.value;benchmarkOpen=false;draw()});
    const bind=(id,fn)=>{const button=$('#'+id);if(button)button.onclick=safe(fn)};
    const libraryCall=async(ident,action,payload={})=>{library=await api('/model-library/'+encodeURIComponent(ident)+'/'+action,'POST',payload);if(generation===libraryGeneration){draw();schedule()}};
    bind('download-model',()=>libraryCall(quant.id,'download'));
    bind('cancel-model',()=>libraryCall(quant.id,'cancel'));
    bind('discard-model',async()=>{if(job?.received&&!confirm('Delete the unfinished download? You can start it again later.'))return;await libraryCall(quant.id,'discard')});
    if(model.projector){const p=model.projector;
     bind('download-projector',()=>libraryCall(p.id,'download'));
     bind('cancel-projector',()=>libraryCall(p.id,'cancel'));
     bind('discard-projector',async()=>{if(p.job?.received&&!confirm('Delete the unfinished projector download?'))return;await libraryCall(p.id,'discard')});
     bind('remove-projector',async()=>{if(!confirm('Uninstall the vision projector? Its file is deleted. Models that use it will read text only until you install it again.'))return;await libraryCall(p.id,'remove',{confirm:true});toast('Vision projector uninstalled.')});
    }
    if(quant.installed){
     const form=document.createElement('form');form.className='model-context-form';form.innerHTML=`<h4>Conversation capacity</h4><label class="field">Context window (tokens)<input name="context" type="number" min="4096" max="${model.context_supported||262144}" step="1024" value="${quant.context||model.context||32768}" required></label><p class="small-note">How much this model can read at once, including tools and its next reply. More context uses more memory and can slow replies. Saving reloads the model manager; older benchmark results keep their original context size.${model.context_supported?'':' This file has no verified maximum recorded; a larger value may fail to load.'}</p><button class="btn" type="submit">Save context size</button><p role="status"></p>`;
     $('#model-detail .model-actions').after(form);form.onsubmit=safe(async e=>{e.preventDefault();const button=form.querySelector('button'),out=form.querySelector('[role=status]');button.disabled=true;out.textContent='Saving and restarting model manager…';try{const result=await api('/models/'+encodeURIComponent(quant.registry_id||quant.id)+'/context','POST',{context:Number(new FormData(form).get('context'))});toast(result.message);await refresh();await reload()}catch(error){out.textContent=error.message;throw error}finally{button.disabled=false}});
    }
    bind('choose-model',async()=>{await api('/model-library/'+encodeURIComponent(quant.registry_id||quant.id)+'/use','POST',{});toast('Model selected. It loads on the next request.');await refresh();await reload()});
    bind('benchmark-model',()=>{benchmarkOpen=!benchmarkOpen;$('#benchmark-preview').hidden=!benchmarkOpen;$('#benchmark-model').setAttribute('aria-expanded',String(benchmarkOpen));if(benchmarkOpen)$('#benchmark-preview').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})});
    bind('run-benchmark',async()=>{const btn=$('#run-benchmark'),result=$('#benchmark-result');btn.disabled=true;result.textContent='Benchmark running…';try{const response=await api('/models/'+encodeURIComponent(quant.registry_id||quant.id)+'/benchmark','POST',{});benchmarkOpen=true;await reload();$('#benchmark-result').textContent=response.tps+' tok/s end-to-end · '+response.first_token_seconds+' s to first token · '+response.completion_tokens+' output tokens'}catch(e){result.textContent=e.message;throw e}finally{if(btn.isConnected)btn.disabled=false}});
    bind('run-quality',async()=>{const btn=$('#run-quality'),result=$('#quality-result');btn.disabled=true;result.textContent='AI score test running. This asks 36 questions and can take a few minutes…';try{const response=await api('/models/'+encodeURIComponent(quant.registry_id||quant.id)+'/evaluate','POST',{});benchmarkOpen=true;await reload();$('#quality-result').textContent=`AI score ${response.score}/100 · ${areaText(response)} · ${response.elapsed} s`}catch(e){result.textContent=e.message;throw e}finally{if(btn.isConnected)btn.disabled=false}});
    bind('remove-model',async()=>{const outside=!quant.managed;const inUse=quant.active?' This is the model in use: it will be stopped first, and Luminaria switches to another downloaded model if there is one.':'';if(!confirm((outside?'Remove this model from the library? The file is outside the models folder and will stay on disk.':'Uninstall this model? Its file is deleted from the models folder. Chats and settings stay. This cannot be undone.')+inUse))return;const result=await api('/model-library/'+encodeURIComponent(quant.registry_id||quant.id)+'/remove','POST',{confirm:true});toast(result?.message||(outside?'Removed from the library.':'Model uninstalled.'));await reload();if(typeof refresh==='function')refresh()});
   }
   function schedule(){clearTimeout(libraryTimer);if(generation!==libraryGeneration)return;if(!(library.downloads||[]).some(job=>job.status==='downloading'||job.status==='queued'||job.status==='cancelling'))return;libraryTimer=setTimeout(async()=>{if(generation!==libraryGeneration)return;const signature=JSON.stringify(library.downloads);try{library=await api('/model-library')}catch(e){toast(e.message,true);return}if(generation!==libraryGeneration)return;if(JSON.stringify(library.downloads)!==signature)draw();schedule()},1000)}
   $('#start-manager').onclick=safe(async()=>{const r=await api('/model/start','POST',{});toast(r.message);await health()});
   const restart=safe(async()=>{for(const b of $$('#restart-manager,#health-restart'))b.disabled=true;try{const r=await api('/model/restart','POST',{});toast(r.message);await health();await showModelHealth()}finally{for(const b of $$('#restart-manager,#health-restart'))b.disabled=false}});
   $('#restart-manager').onclick=restart;
   async function showModelHealth(){const box=$('#model-health');if(!box)return;let h;try{h=await api('/model/status')}catch{return}const stopped=h.manager?.owned&&!h.manager.running;if(h.connected||(!stopped&&!h.problem)){box.hidden=true;return}box.hidden=false;box.innerHTML=`<strong>${stopped?'The model manager stopped'+(h.manager.exit_code!=null?' (exit code '+esc(String(h.manager.exit_code))+')':''):'The model server is not reachable'}</strong><p>${esc(h.problem||'Luminaria could not find a reason in the model manager log. Restarting usually fixes a one-off crash.')}</p><button class="btn primary" id="health-restart">Restart model manager</button>`;$('#health-restart').onclick=restart}
   showModelHealth();
   $('#unload-current').onclick=safe(async()=>{await api('/model/unload','POST',{});toast('Model unloaded');await health()});
   $('#add-local-model').onsubmit=safe(async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(e.target));v.context=Number(v.context);await api('/models','POST',v);toast('Model registered. Restart the app to load it.');await settingsView('Models')});
   $('#model-search').oninput=draw;{const sel=$('#model-sort');try{const saved=localStorage.getItem('model-sort');if(saved&&[...sel.options].some(o=>o.value===saved))sel.value=saved}catch{};sel.onchange=draw}$$('[data-model-filter]').forEach(b=>b.onclick=()=>{modelFilter=b.dataset.modelFilter;draw()});$$('[data-capability]').forEach(b=>b.onclick=()=>{capabilityFilter=capabilityFilter===b.dataset.capability?'':b.dataset.capability;draw()});draw();schedule();$('#advanced-inference').onclick=()=>{stopLibraryPoll();studioSettingsSection('Inference',body)};
  }else{
   await studioSettingsSection(section,body);
  }
  }catch(error){if(body.isConnected){body.replaceChildren();const text=document.createElement('p');text.setAttribute('role','alert');text.textContent=error.message;const retry=document.createElement('button');retry.className='btn';retry.textContent='Try again';retry.onclick=safe(()=>settingsView(section));body.append(text,retry)}}
 }
 /* Group loose rows on every settings page into cards, so pages read as tidy blocks. */
 function cardRows(root){
  for(const row of root.querySelectorAll('.setting-row')){
   const parent=row.parentElement;if(!parent||parent.closest('.s-card')||parent.closest('.pool-list'))continue;
   const before=row.previousElementSibling;
   if(before&&before.matches('.s-card[data-auto]')){before.append(row);continue}
   const card=document.createElement('div');card.className='s-card';card.dataset.auto='';row.before(card);card.append(row);
  }
 }
 new MutationObserver(()=>{const body=$('#settings-body');if(body)cardRows(body)}).observe(document.body,{childList:true,subtree:true});
 const originalClose=closePanel;closePanel=function(){stopLibraryPoll();$('.sheet').classList.remove('settings-sheet');return originalClose()};
})();
