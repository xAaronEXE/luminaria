/* Profile page: identity, signed-in devices, startup sign-in and local profile choices.
   Identity login is distinct from service connectors and local profile storage. */
const providerNames={google:'Google',github:'GitHub',discord:'Discord'};
const when=t=>{if(!t)return 'unknown';const d=Math.round((Date.now()/1000-t)/86400);return d<=0?'today':d===1?'yesterday':d+' days ago'};
const until=t=>{if(!t)return '';const d=Math.round((t-Date.now()/1000)/86400);return d<=0?'today':d===1?'tomorrow':'in '+d+' days'};
async function renderAccounts(body){
 const loading=document.createElement('div');loading.innerHTML='<h3 class="settings-page-title">Profile</h3><p class="note" role="status">Checking account status…</p>';body.replaceChildren(loading);
 const a=await api('/accounts');if(!loading.isConnected)return;const identity=a.identity||{},names=providerNames;
 const connections=identity.connections||(identity.signed_in?[identity.user]:[]),display=identity.account?.name||identity.user?.name||'';
 const local=a.profiles.filter(p=>p.provider==='local'),choice=p=>p.migration==='attached'&&p.account_id?'attach':p.migration==='separate'?'separate':'untouched';
 const choiceText={attach:'Attached to your account',separate:'Kept separate',untouched:'No choice yet'};
 body.innerHTML=`<h3 class="settings-page-title">Profile</h3><p class="settings-intro">Your identity, devices and local profiles. Settings for everything else are in the list beside this page.</p>
 ${identity.signed_in?`<div class="account-summary"><span class="profile-symbol">${esc(display.slice(0,1).toUpperCase())}</span><div><h3>${esc(display)}</h3><p>${connections.length} verified sign-in method${connections.length===1?'':'s'} · ${connections.map(c=>names[c.provider]).join(', ')}</p></div><button class="btn" id="identity-logout">Sign out on this PC</button></div>`:`<p class="note">${esc(identity.message||'Sign-in is unavailable.')}</p>`}
 <h4 class="section-heading">Sign-in methods</h4>${Object.entries(names).map(([id,name])=>{const ready=identity.providers?.some(p=>p.id===id&&p.configured),connected=connections.find(u=>u.provider===id);return `<div class="setting-row"><div><h3>${name}</h3><p>${connected?esc(connected.name)+' · Signed in':ready?'Sign in securely in your browser':'Publisher setup pending'}</p></div><button class="btn" data-signin="${id}" ${!ready||connected?'disabled':''}>${connected?'Connected':(identity.signed_in?'Connect ':'Sign in with ')+name}</button></div>`}).join('')}<div id="identity-progress" role="status"></div>
 <p class="small-note">Google, GitHub and Discord can be connected to this one account by signing in to each in your browser. Accounts are never merged by matching email addresses. Signing in does not grant access to email, repositories, Drive or cloud sync.</p>
 ${identity.signed_in?`<h4 class="section-heading">Signed-in devices</h4><div id="device-list"><p class="note" role="status">Loading devices…</p></div>`:''}
 ${identity.signed_in||a.require_sign_in?`<h4 class="section-heading">Opening Luminaria</h4><div class="setting-row"><div><h3>Require sign-in when opening Luminaria</h3><p>Shows the sign-in screen before your workspace until this PC has a valid session. Offline use is allowed for seven days after the last online check.</p></div><label class="switch"><input type="checkbox" id="require-sign-in" ${a.require_sign_in?'checked':''}> Required</label></div>`:''}
 <h4 class="section-heading">Local profiles</h4><p class="note">Profiles you made on this PC before signing in. Choose what each one should do. Nothing is merged or moved: chats, files and settings stay in their own profile whichever you pick.</p>
 <div id="profile-list">${a.profiles.map(x=>{const isLocal=x.provider==='local',c=choice(x);return `<div class="profile-row" data-profile-row="${esc(x.id)}"><div class="profile-row-head"><div><h3>${esc(x.name)}</h3><p>${x.id===a.active?'Open now':x.id===a.selected?'Opens after restart':'Saved on this PC'} · ${isLocal?esc(choiceText[c]):'Belongs to your '+esc(names[x.provider]||x.provider)+' sign-in'}</p></div><button class="btn" data-profile="${esc(x.id)}" ${x.id===a.selected?'disabled':''}>Open after restart</button></div>${isLocal?`<div class="segmented" role="radiogroup" aria-label="What should ${esc(x.name)} do?">${[['attach','Attach to account'],['separate','Keep separate'],['untouched','Leave untouched']].map(([v,l])=>`<label><input type="radio" name="migrate-${esc(x.id)}" value="${v}" data-migrate="${esc(x.id)}" ${c===v?'checked':''} ${v==='attach'&&!identity.signed_in?'disabled':''}><span>${l}</span></label>`).join('')}</div>`:''}</div>`}).join('')}</div>
 <p class="small-note"><strong>Attach</strong>: it opens only when you are signed in to this account. <strong>Keep separate</strong>: it stays a plain local profile and cannot open while sign-in is required. <strong>Leave untouched</strong>: nothing is recorded and it works as before.</p><p class="small-note" id="migrate-status" role="status" aria-live="polite"></p>`;
 const label=document.getElementById('profile-label');if(label)label.innerHTML=identity.signed_in?esc(display)+'<small>Profile & settings</small>':'Account & settings<small>Sign in</small>';
 const symbol=document.querySelector('.sidebar .profile-symbol');if(symbol&&identity.signed_in)symbol.textContent=display.slice(0,1).toUpperCase();
 if(identity.signed_in)renderDevices(body);
 body.querySelectorAll('[data-profile]').forEach(b=>b.onclick=safe(async()=>{const r=await api('/accounts/'+b.dataset.profile+'/select','POST',{});toast(r.message);await renderAccounts(body)}));
 body.querySelectorAll('[data-migrate]').forEach(r=>r.onchange=safe(async()=>{const out=body.querySelector('#migrate-status'),row=a.profiles.find(p=>p.id===r.dataset.migrate);
  if(r.value==='attach'&&!confirm(`Attach “${row.name}” to ${display}? It will only open while you are signed in to this account. Its chats and files are not moved or merged.`)){body.querySelector(`[data-migrate="${r.dataset.migrate}"][value="${choice(row)}"]`).checked=true;return}
  try{const res=await api('/accounts/'+r.dataset.migrate+'/migration','POST',{choice:r.value});out.textContent=res.message;await renderAccounts(body);body.querySelector('#migrate-status').textContent=res.message}
  catch(e){out.textContent=e.message;body.querySelector(`[data-migrate="${r.dataset.migrate}"][value="${choice(row)}"]`).checked=true}}));
 body.querySelector('#require-sign-in')?.addEventListener('change',safe(async e=>{const box=e.target;box.disabled=true;try{if(!box.checked&&!confirm('Turn off required sign-in? Anyone using this Windows account will be able to open Luminaria.')){box.checked=true;return}const r=await api('/identity/require','POST',{enabled:box.checked});toast(r.required?'Sign-in is now required when Luminaria opens.':'Sign-in is no longer required.')}catch(error){box.checked=!box.checked;throw error}finally{await renderAccounts(body)}}));
 body.querySelector('#identity-logout')?.addEventListener('click',safe(async()=>{if(!confirm('Sign out on this PC? Your chats and files stay here.'))return;await api('/identity/logout','POST',{});await renderAccounts(body)}));
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
async function renderDevices(body){
 const el=body.querySelector('#device-list');if(!el)return;
 let d;try{d=await api('/identity/devices')}catch(e){if(el.isConnected)el.innerHTML=`<p class="note" role="alert">${esc(e.message)}</p>`;return}
 if(!el.isConnected)return;
 if(!d.available){el.innerHTML=`<p class="note">${esc(d.message)}</p>`;return}
 const others=d.devices.filter(x=>!x.current).length;
 el.innerHTML=`<p class="small-note">A device stays signed in for ${d.idle_days} days after it was last used, and asks again after ${d.max_days} days at most. Without internet, Luminaria opens for up to ${d.offline_days} days after the last online check.</p>${d.devices.map(x=>`<div class="setting-row device-row"><div><h3>${esc(x.label)}${x.current?' <span class="badge good">This PC</span>':''}</h3><p>${esc(providerNames[x.provider]||'Sign-in')} · last active ${esc(when(x.last_seen))} · signed in ${esc(when(x.created))}${x.expires?' · expires '+esc(until(x.expires))+' if unused':''}</p></div>${x.current?'':`<button class="btn" data-revoke="${esc(x.id)}" data-label="${esc(x.label)}">Sign out</button>`}</div>`).join('')}${others?`<div class="form-actions"><button class="btn danger" id="revoke-others">Sign out all other devices (${others})</button></div>`:''}`;
 el.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=safe(async()=>{if(!confirm(`Sign out “${b.dataset.label}”? It will need to sign in again.`))return;b.disabled=true;await api('/identity/devices/'+b.dataset.revoke+'/revoke','POST',{});toast('Device signed out');await renderDevices(body)}));
 el.querySelector('#revoke-others')?.addEventListener('click',safe(async()=>{if(!confirm('Sign out every other device? This PC stays signed in.'))return;const r=await api('/identity/devices/revoke-others','POST',{});toast(r.revoked+' device'+(r.revoked===1?'':'s')+' signed out');await renderDevices(body)}));
}

window.addEventListener('studio-state',function profileInfo(){
 window.removeEventListener('studio-state',profileInfo);
 api('/accounts').then(a=>{const user=a.identity?.user?{...a.identity.user,name:a.identity.account?.name||a.identity.user.name}:null,label=document.getElementById('profile-label');if(!user||!label)return;label.innerHTML=esc(user.name)+'<small>Profile & settings</small>';document.querySelector('.profile-symbol').textContent=user.name.slice(0,1).toUpperCase()}).catch(()=>{});
});
