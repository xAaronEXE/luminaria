/* Gentle first-run pointer to the Model library when no model is installed yet.
   Waits for onboarding to finish, stays until dismissed or a model is installed, and returns next launch if still needed. */
(()=>{
 let box=null,dismissed=false,checking=false;
 const onboarding=()=>document.getElementById('account-onboarding');
 function close(){if(!box)return;const b=box;box=null;b.classList.remove('shown');setTimeout(()=>b.remove(),250)}
 function show(){
  if(box||dismissed)return;
  box=document.createElement('aside');box.className='update-notice model-nudge';box.setAttribute('role','status');box.setAttribute('aria-live','polite');box.setAttribute('aria-label','Get a model');
  box.innerHTML=`<span class="update-notice-mark">${icon('download')}</span><div><strong>Get your first AI model</strong><small>Luminaria runs AI on this PC. The Model library shows which models fit it best.</small></div><button class="btn primary" data-nudge-open>Open Model library</button><button class="icon-btn" data-nudge-dismiss aria-label="Dismiss">${icon('close')}</button>`;
  document.body.append(box);requestAnimationFrame(()=>box&&box.classList.add('shown'));
  box.querySelector('[data-nudge-dismiss]').onclick=()=>{dismissed=true;close()};
  box.querySelector('[data-nudge-open]').onclick=safe(async()=>{close();window.studioSettingsCategory='Models';try{await openPanel('settings')}finally{window.studioSettingsCategory=null}});
 }
 async function check(){
  if(checking||dismissed)return;checking=true;
  try{
   if(onboarding()){setTimeout(()=>{checking=false;check()},1500);return}
   const data=await api('/models');
   const any=(data.models||[]).some(m=>m.installed);
   any?close():show();
  }catch{}finally{checking=false}
 }
 let started=false;
 window.addEventListener('studio-state',()=>{if(!started){started=true;setTimeout(check,2500)}else if(box)check()});
})();
