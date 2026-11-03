/* Composer model picker: Auto routing or one installed model. */
(()=>{
 const small=m=>{const n=parseFloat(String(m?.parameters||'').replace(/[^0-9.]/g,''));return n>0&&n<7&&/b/i.test(String(m.parameters))};
 const variantOf=m=>m.remote?'online':['standard','abliterated'].includes(m.variant)?m.variant:/abliterat|huihui/i.test((m.name||'')+' '+(m.description||'')+' '+m.id)?'abliterated':'standard';
 const poolText=(pool,count)=>pool?.mode==='standard'?'Standard models only':pool?.mode==='abliterated'?'Abliterated models only':pool?.mode==='custom'?`${count} chosen model${count===1?'':'s'}`:'All installed models';
 let menu=null,button=null;
 function close(focus=true){if(!menu)return;menu.remove();menu=null;button?.setAttribute('aria-expanded','false');document.removeEventListener('pointerdown',outside,true);if(focus)button?.focus()}
 function outside(e){if(menu&&!menu.contains(e.target)&&!button.contains(e.target))close(false)}
 function place(){const r=button.getBoundingClientRect(),h=menu.offsetHeight,w=menu.offsetWidth;menu.style.left=Math.max(8,Math.min(innerWidth-w-8,r.left))+'px';menu.style.top=(r.top-h-8>8?r.top-h-8:Math.min(innerHeight-h-8,r.bottom+8))+'px'}
 async function choose(action){
  try{
   if(action.auto){await api('/settings','POST',{orchestration_enabled:true});toast('Auto routing on. Each new message picks the best model from your selection.')}
   else{
    if(action.id!==state.model)await api('/models/'+encodeURIComponent(action.id)+'/select','POST');
    if(state.orchestration?.enabled)await api('/settings','POST',{orchestration_enabled:false});
    toast('Using '+action.name+'. It loads on the next message.'+(small(action)?' Models this small often can’t use tools, so for real tasks pick a 14B model or Auto.':''));
   }
   close();await refresh();
  }catch(e){toast(e.message,true)}
 }
 async function open(){
  if(menu)return close();
  button.setAttribute('aria-expanded','true');
  menu=document.createElement('div');menu.className='model-menu';menu.setAttribute('role','menu');menu.setAttribute('aria-label','Choose a model');
  menu.innerHTML='<p class="model-menu-note" role="status">Loading models…</p>';document.body.append(menu);place();
  document.addEventListener('pointerdown',outside,true);
  let data,settings;
  try{[data,settings]=await Promise.all([api('/models'),api('/settings')])}catch(e){if(menu)menu.innerHTML=`<p class="model-menu-note" role="alert">${esc(e.message)}</p>`;return}
  if(!menu)return;
  const models=data.models.filter(m=>m.installed),router=settings.orchestrator_model,auto=Boolean(router)&&settings.orchestration_enabled!==false;
  const pool=settings.orchestration_pool||{mode:'all',models:[]};
  const poolCount=pool.mode==='custom'?models.filter(m=>pool.models.includes(m.id)).length:pool.mode==='all'?models.length:models.filter(m=>variantOf(m)===pool.mode).length;
  const item=(attrs,checked,title,sub,extra='')=>`<button type="button" role="menuitemradio" aria-checked="${checked}" class="model-menu-item ${checked?'checked':''} ${extra}" ${attrs}><span class="model-menu-check" aria-hidden="true">${checked?icon('check'):''}</span><span class="model-menu-text"><strong>${title}</strong>${sub?`<small>${sub}</small>`:''}</span></button>`;
  const group=v=>{const list=models.filter(m=>variantOf(m)===v);return list.length?`<div class="model-menu-group ${v}" role="group" aria-label="${v==='standard'?'Standard':'Abliterated'} models"><h4>${v==='standard'?'Standard':v==='online'?'Model services':'<span class="fractured-mark" aria-hidden="true"></span>Abliterated'}</h4>${list.map(m=>item(`data-pick="${esc(m.id)}"`,!auto&&m.id===data.active,esc(m.name),[small(m)?'Chat only: too small for tasks':'',(m.name||'').includes(m.quantization)?'':m.quantization,(m.strengths||[]).join(', '),m.bytes?formatBytes(m.bytes):'',m.vision?'Vision':''].filter(Boolean).map(esc).join(' · '),v)).join('')}</div>`:''};
  menu.innerHTML=`${router?item('data-auto',auto,'Auto',`Picks the best model for each message · ${esc(poolText(pool,poolCount))}`,'auto'):''}${models.length?group('standard')+group('abliterated')+group('online'):'<p class="model-menu-note">No models are installed yet.</p>'}<div class="model-menu-footer">${router?'<button type="button" role="menuitem" data-go="Orchestration">Choose models for Auto…</button>':'<button type="button" role="menuitem" data-go="Orchestration">Set up Auto routing…</button>'}<button type="button" role="menuitem" data-go="Models">Model library…</button></div>`;
  fillIcons(menu);place();
  menu.querySelector('[data-auto]')?.addEventListener('click',()=>choose({auto:true}));
  menu.querySelectorAll('[data-pick]').forEach(b=>b.onclick=()=>choose({id:b.dataset.pick,name:models.find(m=>m.id===b.dataset.pick)?.name||b.dataset.pick,parameters:models.find(m=>m.id===b.dataset.pick)?.parameters}));
  menu.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>{close(false);window.studioSettingsCategory=b.dataset.go;openPanel(b.dataset.go==='Models'?'models':'settings').catch(e=>toast(e.message,true))});
  (menu.querySelector('[aria-checked="true"]')||menu.querySelector('button'))?.focus();
 }
 function keys(e){
  if(!menu)return;
  const items=[...menu.querySelectorAll('button')];const i=items.indexOf(document.activeElement);
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close()}
  else if(e.key==='ArrowDown'){e.preventDefault();items[(i+1)%items.length]?.focus()}
  else if(e.key==='ArrowUp'){e.preventDefault();items[(i-1+items.length)%items.length]?.focus()}
  else if(e.key==='Home'){e.preventDefault();items[0]?.focus()}
  else if(e.key==='End'){e.preventDefault();items.at(-1)?.focus()}
  else if(e.key==='Tab')close(false);
 }
 function init(){
  button=document.getElementById('model-button');if(!button)return;
  button.onclick=e=>{e.preventDefault();open()};
  document.addEventListener('keydown',keys,true);
  addEventListener('resize',()=>close(false));
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
