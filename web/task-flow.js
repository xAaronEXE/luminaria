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
   const run=state.run,actions=state.actions||[],current=actions.find(a=>a.status==='running'),latest=[...actions].reverse().find(a=>['done','error','interrupted'].includes(a.status));
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
})();
