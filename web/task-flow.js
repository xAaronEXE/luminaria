/* Polish existing controls without changing the workspace or spatial layout. */
(()=>{
 function effect(action){
  const a=action.args||{};
  if(action.name==='write_file')return 'Create or replace this file. Existing content is backed up.';
  if(action.name==='edit_file')return 'Replace one matching passage in this file.';
  if(action.name==='delete_file')return 'Remove this file after saving a recovery copy.';
  if(action.name==='web_fetch')return a.browser_fallback?'Fetch this page; if needed, navigate the connected browser and read its snapshot.':'Request this page and read its public content.';
  if(['run_command','run_code'].includes(action.name))return 'Execute code with your Windows account permissions. It may change files or external state.';
  if(action.name.includes('__'))return 'Call this connected service. Its tool may change external state; review the arguments.';
  return 'Run this action with the shown arguments and your current permissions.';
 }
 function update(){
  const status=document.querySelector('#run-status');
  if(status){
   let progress=document.querySelector('#task-progress');
   if(!progress){progress=document.createElement('div');progress.id='task-progress';progress.className='task-progress';progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');status.before(progress)}
   const run=state.run,actions=(state.actions||[]).filter(a=>!run||a.created>=run.started),current=actions.find(a=>a.status==='running'),latest=[...actions].reverse().find(a=>['done','error','interrupted'].includes(a.status));
   progress.hidden=!run||Boolean(run.finished);
   const label=current?'Running '+current.name.replaceAll('__',' · '):run?.phase||'';
   const result=latest?' · Last action '+(latest.status==='done'?'reported success':latest.status==='interrupted'?'has an uncertain outcome':'failed'):'';
   const line=label+result;
   if(progress.dataset.line!==line){progress.dataset.line=line;progress.replaceChildren(document.createTextNode(line));const b=document.createElement('button');b.type='button';b.className='text-button';b.textContent='Activity details';b.onclick=()=>document.querySelector('[data-tab="activity"]').click();progress.append(' ',b)}
  }
  document.querySelectorAll('.approval').forEach(card=>{
   const button=card.querySelector('[data-action]'),action=(state.actions||[]).find(a=>a.id===button?.dataset.action);
   const pre=card.querySelector(':scope > pre');if(!action||!pre)return;
   const summary=document.createElement('p');summary.className='approval-effect';summary.textContent=effect(action);
   const destination=action.args?.path||action.args?.url||action.args?.title;
   if(destination){const target=document.createElement('p');target.className='approval-target';target.textContent='Target: '+destination;pre.before(target)}
   pre.before(summary);const details=document.createElement('details');const heading=document.createElement('summary');heading.textContent='Exact arguments';details.append(heading);pre.replaceWith(details);details.append(pre);
  });
  const path=document.querySelector('.file-path span');
  if(path&&filePath==='.'&&/^[a-f0-9]{32}$/i.test(path.textContent)){path.title=state.workspace||'';path.textContent='This profile’s files'}
 }
 window.addEventListener('studio-state',update);
 const originalSkills=renderSkills;
 renderSkills=async function(){
  await originalSkills();const rows=await api('/skills');
  if(!document.querySelector('#skill-groups'))return;
  function annotate(){
   document.querySelectorAll('.skill-row').forEach(card=>{
    if(card.querySelector('.skill-runtime-detail'))return;
    const name=card.querySelector('[data-skill]')?.dataset.skill,row=rows.find(s=>s.name===name);if(!row)return;
    const setup=document.createElement('button');setup.type='button';setup.className='btn';setup.textContent=row.available?'Check setup':'Set up skill';setup.onclick=safe(()=>skillSetup(name));card.querySelector('.row-actions')?.append(setup);
    const details=document.createElement('details');details.className='skill-runtime-detail';const title=document.createElement('summary');title.textContent=row.last_run?'Last workflow: '+row.last_run.state:'Prerequisites and output checks';details.append(title);
    for(const text of [row.last_run?.reason,row.reason,'Inputs: '+row.inputs,'Outputs: '+row.outputs,row.permissions].filter(Boolean)){const p=document.createElement('p');p.className='small-note';p.textContent=text;details.append(p)}
    card.append(details);
   });
  }
  annotate();document.querySelector('#filter-skills')?.addEventListener('input',annotate);
  document.querySelectorAll('[data-skill-show]').forEach(b=>b.addEventListener('click',annotate));
 };
 async function skillSetup(name){
  panel='skill-setup';showPanel('Set up '+name.replaceAll('-',' '),'Connect the prerequisites, then verify readiness.','<p role="status">Checking prerequisites…</p>');$('.sheet').classList.remove('settings-sheet');
  const guide=await api('/skills/'+encodeURIComponent(name)+'/setup');if(panel!=='skill-setup')return;
  $('#panel-content').innerHTML=`<p class="note">${esc(guide.note)}</p><p role="status"><strong>${guide.ready?'Declared prerequisites are ready':'Setup is still needed'}</strong></p>${guide.steps.map(s=>`<section class="setting-row"><div><h3>${esc(s.title)} · ${s.ready?'Ready':'Needs setup'}</h3><p>${esc(s.description)}</p>${s.status?`<p class="small-note">${esc(s.status)}</p>`:''}</div>${s.ready?'':`<button class="btn" data-setup-step="${esc(s.id)}">${s.action==='connector'?s.configured?'Reconnect':'Set up connector':'Open setup'}</button>`}</section>`).join('')||'<p>No additional prerequisites are declared for this skill. Review its instructions before use.</p>'}<p id="skill-setup-status" role="status" aria-live="polite"></p><div class="form-actions"><button class="btn primary" id="skill-check-again">Check again</button><button class="btn" id="skill-setup-back">Back to skills</button></div>`;
  $('#skill-check-again').onclick=safe(()=>skillSetup(name));$('#skill-setup-back').onclick=safe(()=>openPanel('skills'));
  $$('[data-setup-step]').forEach(button=>button.onclick=safe(async()=>{
   const step=guide.steps.find(s=>s.id===button.dataset.setupStep);
   if(step.action==='connector'){
    if(!confirm('Start this local '+step.id+' connector? It runs with your Windows account permissions. Tool actions will still follow your saved approval mode.'))return;
    button.disabled=true;
    try{await api('/skills/'+encodeURIComponent(name)+'/setup/connector','POST',{connector:step.id,approved:true});await skillSetup(name)}catch(error){$('#skill-setup-status').textContent=error.message;button.disabled=false}return;
   }
   if(step.action==='github'){
    await openPanel('integrations');const target=document.querySelector('[data-integration="github"]');if(target){target.open=true;target.scrollIntoView({block:'start'})}
   }else{window.studioSettingsCategory=step.action==='workspace'?'Inference':'Tools & permissions';try{await openPanel('settings')}finally{window.studioSettingsCategory=null}}
   const back=document.createElement('button');back.type='button';back.className='btn';back.textContent='Return to skill setup';back.onclick=safe(()=>skillSetup(name));$('#panel-content').prepend(back);
  }));
 }
})();
