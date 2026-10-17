/* Identity login is distinct from service connectors and local profile storage. */
async function renderAccounts(body){
 const loading=document.createElement('div');loading.innerHTML='<h3 class="settings-page-title">Accounts</h3><p class="note" role="status">Checking account status…</p>';body.replaceChildren(loading);
 const a=await api('/accounts');if(!loading.isConnected)return;const identity=a.identity||{},names={google:'Google',github:'GitHub',discord:'Discord'};
 const connections=identity.connections||(identity.signed_in?[identity.user]:[]);
 body.innerHTML=`<h3 class="settings-page-title">Your account</h3><p class="settings-intro">One place for your identity and settings. You can stay signed in with Google, GitHub and Discord at the same time.</p><p class="note">${esc(identity.message||'Sign-in is unavailable.')}</p>${identity.signed_in?`<div class="account-summary"><span class="profile-symbol">${esc(identity.user.name.slice(0,1))}</span><div><h3>${esc(identity.user.name)}</h3><p>${connections.length} verified sign-in method${connections.length===1?'':'s'} on this PC</p></div><button class="btn" id="identity-logout">Sign out of all</button></div>`:''}<h4 class="section-heading">Sign-in methods</h4>${Object.entries(names).map(([id,name])=>{const ready=identity.providers?.some(p=>p.id===id&&p.configured),connected=connections.find(u=>u.provider===id);return `<div class="setting-row"><div><h3>${name}</h3><p>${connected?esc(connected.name)+' · Signed in':ready?'Sign in securely in your browser':'Publisher setup pending'}</p></div><button class="btn" data-signin="${id}" ${!ready||connected?'disabled':''}>${connected?'Connected':'Sign in with '+name}</button></div>`}).join('')}<div id="identity-progress" role="status"></div><p class="small-note">These are verified provider sessions saved on this PC, not a merged cloud account. Sign-in does not connect email, repositories, Drive or cloud sync; connect those in Tools & integrations.</p>${identity.signed_in||a.require_sign_in?`<div class="setting-row"><div><h3>Require sign-in when opening Luminaria</h3><p>When enabled, a verified session is required. Offline use is allowed for seven days after the last online check.</p></div><label class="switch"><input type="checkbox" id="require-sign-in" ${a.require_sign_in?'checked':''}> Required</label></div>`:''}<details class="advanced-settings"><summary>Previous local profiles</summary><p class="note">Existing chats remain in their original profiles. This recovery list keeps older data accessible; new sign-ins stay in the current profile.</p>${a.profiles.map(x=>`<div class="setting-row"><div><h3>${esc(x.name)}</h3><p>${x.id===a.active?'Open now':x.id===a.selected?'Selected for next launch':'Saved on this PC'}</p></div><button class="btn" data-profile="${esc(x.id)}" ${x.id===a.selected?'disabled':''}>Open after restart</button></div>`).join('')}</details>`;
 const label=document.getElementById('profile-label');if(label)label.innerHTML=identity.signed_in?esc(identity.user.name)+'<small>Account & settings</small>':'Account & settings<small>Sign in</small>';
 body.querySelectorAll('[data-profile]').forEach(b=>b.onclick=safe(async()=>{const r=await api('/accounts/'+b.dataset.profile+'/select','POST',{});toast(r.message);await renderAccounts(body)}));
 body.querySelector('#require-sign-in')?.addEventListener('change',safe(async e=>{const box=e.target;box.disabled=true;try{if(!box.checked&&!confirm('Turn off required sign-in? Anyone using this Windows account will be able to open Luminaria.')){box.checked=true;return}const r=await api('/identity/require','POST',{enabled:box.checked});toast(r.required?'Sign-in is now required when Luminaria opens.':'Sign-in is no longer required.')}catch(error){box.checked=!box.checked;throw error}finally{await renderAccounts(body)}}));
 body.querySelector('#identity-logout')?.addEventListener('click',safe(async()=>{await api('/identity/logout','POST',{});await renderAccounts(body)}));
 body.querySelectorAll('[data-signin]').forEach(b=>b.onclick=safe(async()=>{
  const out=body.querySelector('#identity-progress');delete out.dataset.cancelled;let flow;body.querySelectorAll('[data-signin]').forEach(x=>x.disabled=true);
  try{
   out.textContent='Starting secure sign-in…';flow=await api('/identity/start','POST',{provider:b.dataset.signin});if(!out.isConnected)return;
   out.innerHTML=`<p>Finish signing in with ${esc(names[b.dataset.signin])}.</p><a class="btn" href="${esc(flow.url)}" target="_blank" rel="noopener noreferrer">Continue in browser</a> <button type="button" class="btn" id="cancel-signin">Cancel sign-in</button><p class="small-note">This request expires in ten minutes. Keep this screen open.</p>`;
   out.querySelector('#cancel-signin').onclick=safe(async()=>{out.dataset.cancelled='true';await api('/identity/cancel','POST',{flow_id:flow.flow_id});out.textContent='Sign-in cancelled.'});
   const deadline=Date.now()+flow.expires_in*1000;
   while(out.isConnected&&!out.dataset.cancelled&&Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,flow.interval*1000));if(!out.isConnected||out.dataset.cancelled)return;
    const r=await api('/identity/poll','POST',{flow_id:flow.flow_id});if(r.status==='complete'){if(out.isConnected)await renderAccounts(body);toast(r.message);return}
   }
   if(out.isConnected&&!out.dataset.cancelled)out.textContent='Sign-in expired. Start again.';
  }catch(error){if(out.isConnected)out.textContent=error.message}
  finally{if(flow)api('/identity/cancel','POST',{flow_id:flow.flow_id}).catch(()=>{});if(out.isConnected)body.querySelectorAll('[data-signin]').forEach(x=>x.disabled=connections.some(u=>u.provider===x.dataset.signin)||!identity.providers?.some(p=>p.id===x.dataset.signin&&p.configured))}
 }));
}

window.addEventListener('studio-state',function profileInfo(){
 window.removeEventListener('studio-state',profileInfo);
 api('/accounts').then(a=>{const user=a.identity?.user,label=document.getElementById('profile-label');if(!user||!label)return;label.innerHTML=esc(user.name)+'<small>Account & settings</small>';document.querySelector('.profile-symbol').textContent=user.name.slice(0,1).toUpperCase()}).catch(()=>{});
});
