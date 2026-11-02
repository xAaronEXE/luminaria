/* File-first operation lives under Tools; existing sidebar and composer stay intact. */
(()=>{
 const original=openPanel;
 openPanel=async function(name){await original(name);if(name==='tools'){
  const body=document.querySelector('#tools-body');if(!body)return;
  const button=document.createElement('button');button.className='btn';button.textContent='File workflows';button.onclick=safe(()=>view());body.prepend(button);
 }};
 let chosen='',timer;
 window.openFileWorkflows=()=>view();
 async function view(){
  clearTimeout(timer);const data=await api('/file-workflows');
  showPanel('File workflows','Bounded file tasks with observations, recovery copies, and verified results.',`<p class="note">Declare the objective and allowed locations before running. Review mode approves one step at a time. Full Access can run the remaining file steps. No shell, permanent deletion, or application control is included.</p>
   <div class="form-actions"><button class="btn" id="workflow-new">New file workflow</button></div><div id="workflow-list">${data.workflows.map(p=>`<button class="file-row" data-workflow="${esc(p.id)}"><span>${esc(p.objective)}</span><small>${esc(p.state)}</small></button>`).join('')||'<p class="note">No file workflows yet. Create one here or ask Luminaria to propose one.</p>'}</div><section id="workflow-detail"></section>`);
  document.querySelector('#workflow-new').onclick=()=>createForm();
  document.querySelectorAll('[data-workflow]').forEach(b=>{const p=data.workflows.find(p=>p.id===b.dataset.workflow);b.querySelector('small').textContent=' · '+p.state;b.onclick=()=>{chosen=b.dataset.workflow;details(data)}});
  if(chosen)details(data);
 }
 function details(data){
  const plan=data.workflows.find(p=>p.id===chosen);if(!plan)return;
  const el=document.querySelector('#workflow-detail');if(!el)return;
  document.querySelectorAll('[data-workflow]').forEach(b=>{const p=data.workflows.find(p=>p.id===b.dataset.workflow);if(p)b.querySelector('small').textContent=' · '+p.state});
  const active=data.active===plan.id,ready=plan.steps.find(s=>s.state!=='Verified');
  el.innerHTML=`<h3 class="section-heading">${esc(plan.objective)}</h3><p>${esc(plan.completion_criteria)}</p><p class="small-note">Allowed locations: ${plan.allowed_locations.map(esc).join(', ')} · ${esc(plan.state)}</p>${plan.error?`<p role="alert">${esc(plan.error)}</p>`:''}
   <ol class="plan-steps">${plan.steps.map(s=>`<li><strong>${esc(s.action)} · ${esc(s.path)}</strong><span class="badge">${esc(s.state)}</span>${s.reason?`<p>${esc(s.reason)}</p>`:''}<details><summary>Planned text and file checks</summary>${s.content!==undefined?`<p>New content</p><pre>${esc(s.content)}</pre>`:''}${s.old_text!==undefined?`<p>Replace</p><pre>${esc(s.old_text)}</pre><p>With</p><pre>${esc(s.new_text)}</pre>`:''}<p class="small-note">Source: ${esc(s.before.sha256||'must not exist')}<br>Expected: ${esc(s.expected.sha256||'absent')}</p>${s.result?`<pre>${esc(s.result.text||'')}</pre>`:''}</details>${s.recovery_available&&s.action==='trash'?`<button class="btn" data-workflow-restore="${esc(s.id)}" ${active?'disabled':''}>Restore recovery copy</button>`:''}</li>`).join('')}</ol>
   <div class="form-actions"><button class="btn primary" id="workflow-next" ${active||!ready||ready.state!=='Ready'?'disabled':''}>Approve ${ready?esc(ready.action)+' '+esc(ready.path):'next step'}</button>${data.full_access?`<button class="btn" id="workflow-all" ${active||!ready||ready.state!=='Ready'?'disabled':''}>Run remaining steps</button>`:''}<button class="btn danger" id="workflow-stop" ${active?'':'disabled'}>Stop</button><button class="btn" id="workflow-inspect" ${active?'disabled':''}>Inspect recovery</button><button class="btn" id="workflow-accept" ${plan.state==='Awaiting review'?'':'disabled'}>Results meet my objective</button></div><p class="small-note">Stop prevents subsequent effects; a current atomic file operation must settle before its outcome can be verified. Recovery never overwrites an existing file.</p>`;
  const nextButton=document.querySelector('#workflow-next');if(nextButton){nextButton.textContent=ready?'Approve '+ready.action+' step':'Approve next step';nextButton.title=ready?.path||''}
  const bind=(id,action)=>{const b=document.querySelector(id);if(b)b.onclick=safe(async()=>{b.disabled=true;await action();await view()})};
  bind('#workflow-next',()=>api('/file-workflows/'+plan.id+'/run','POST',{approved:true}));
  bind('#workflow-all',()=>api('/file-workflows/'+plan.id+'/run','POST',{approved:true,all_steps:true}));
  bind('#workflow-stop',()=>api('/file-workflows/'+plan.id+'/stop','POST'));
  bind('#workflow-inspect',()=>api('/file-workflows/'+plan.id+'/inspect','POST'));
  bind('#workflow-accept',()=>api('/file-workflows/'+plan.id+'/accept','POST'));
  el.querySelectorAll('[data-workflow-restore]').forEach(b=>b.onclick=safe(async()=>{b.disabled=true;await api('/file-workflows/'+plan.id+'/restore','POST',{step:b.dataset.workflowRestore,approved:true});await view()}));
  if(active)timer=setTimeout(()=>{if(document.querySelector('#workflow-detail'))safe(async()=>details(await api('/file-workflows')))()},1000);
 }
 function createForm(){
  clearTimeout(timer);chosen='';showPanel('New file workflow','Review the full plan before running any steps.',`<form id="file-workflow-form"><div class="form-grid">${field('Objective','objective','','text',true)}${field('Completion criteria','completion_criteria','','text',true)}${field('Allowed workspace folders or files (comma separated)','locations','','text',true)}</div><p class="small-note">Use relative paths. A dot explicitly allows the whole selected workspace. Individual files are limited to 2 MB. Create never overwrites; edit requires one exact matching passage; trash preserves a recovery copy.</p><div id="workflow-steps"></div><div class="form-actions"><button class="btn" type="button" id="workflow-add">Add step</button><button class="btn primary" type="submit">Save plan for review</button></div></form>`);
  function add(){const el=document.createElement('fieldset');el.className='workflow-step';el.innerHTML=`<legend>File step</legend><label class="field">Action<select name="action"><option value="read">Read</option><option value="create">Create</option><option value="edit">Edit</option><option value="trash">Move to recovery trash</option></select></label><label class="field">Relative file path<input name="path" required></label><label class="field" data-content hidden>File content<textarea name="content"></textarea></label><div data-edit hidden><label class="field">Exact text to replace<textarea name="old_text"></textarea></label><label class="field">Replacement<textarea name="new_text"></textarea></label></div><button class="text-button" type="button">Remove step</button>`;el.querySelector('select').onchange=e=>{el.querySelector('[data-content]').hidden=e.target.value!=='create';el.querySelector('[data-edit]').hidden=e.target.value!=='edit'};el.querySelector('button').onclick=()=>el.remove();document.querySelector('#workflow-steps').append(el)}
  document.querySelector('#workflow-add').onclick=add;add();
  document.querySelector('#file-workflow-form').onsubmit=safe(async event=>{event.preventDefault();const form=new FormData(event.target);const steps=[...event.target.querySelectorAll('.workflow-step')].map(el=>{const val=name=>el.querySelector(`[name=${name}]`).value;const action=val('action');return {action,path:val('path'),...(action==='create'?{content:val('content')}:{}),...(action==='edit'?{old_text:val('old_text'),new_text:val('new_text')}: {})}});const result=await api('/file-workflows','POST',{objective:form.get('objective'),completion_criteria:form.get('completion_criteria'),allowed_locations:String(form.get('locations')).split(',').map(s=>s.trim()).filter(Boolean),steps});chosen=result.id;await view()});
 }
})();
