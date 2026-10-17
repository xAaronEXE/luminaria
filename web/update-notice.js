/* Brief launch notice when a newer release exists. Checks once, never downloads or installs. */
(()=>{
 const KEY='luminaria-update-seen',DELAY=3000,VISIBLE=8000;
 const seen=()=>{try{return localStorage.getItem(KEY)||''}catch{return ''}};
 const remember=v=>{try{localStorage.setItem(KEY,v)}catch{}};
 function show(u){
  const box=document.createElement('aside');box.className='update-notice';box.setAttribute('role','status');box.setAttribute('aria-live','polite');box.setAttribute('aria-label','Update available');
  box.innerHTML=`<span class="update-notice-mark">${icon('download')}</span><div><strong>Luminaria ${esc(u.version)} is available</strong><small>You have ${esc(u.current)}. Nothing installs until you choose to.</small></div><button class="btn" data-update-view>View</button><button class="icon-btn" data-update-dismiss aria-label="Dismiss update notice">${icon('close')}</button>`;
  document.body.append(box);requestAnimationFrame(()=>box.classList.add('shown'));
  let timer=0,held=false;
  const close=()=>{clearTimeout(timer);box.classList.remove('shown');setTimeout(()=>box.remove(),250)};
  const arm=()=>{clearTimeout(timer);if(!held)timer=setTimeout(close,VISIBLE)};
  const hold=v=>{held=v;v?clearTimeout(timer):arm()};
  box.addEventListener('pointerenter',()=>hold(true));box.addEventListener('pointerleave',()=>hold(box.contains(document.activeElement)));
  box.addEventListener('focusin',()=>hold(true));box.addEventListener('focusout',e=>{if(!box.contains(e.relatedTarget))hold(box.matches(':hover'))});
  box.querySelector('[data-update-dismiss]').onclick=()=>{remember(u.version);close()};
  box.querySelector('[data-update-view]').onclick=safe(async()=>{remember(u.version);close();window.studioSettingsCategory='Updates';try{await openPanel('settings')}finally{window.studioSettingsCategory=null}});
  arm();
 }
 async function check(){
  try{const u=await api('/updates');if(u&&u.available&&u.version&&seen()!==u.version)show(u)}catch{}
 }
 let started=false;
 window.addEventListener('studio-state',()=>{if(started)return;started=true;setTimeout(check,DELAY)});
})();
