/* Opt-in tuning uses the existing settings shell and native controls. */
(()=>{
 const original=studioSettingsSection;
 studioSettingsSection=async function(section,body){
  if(section!=='Hardware & tuning')return original(section,body);
  body.innerHTML='<h3 class="settings-page-title">Hardware & tuning</h3><p role="status">Reading this PC’s hardware…</p>';
  const info=await api('/hardware');if(!body.isConnected)return;
  const value=v=>v==null?'Unavailable':esc(v);
  body.innerHTML=`<h3 class="settings-page-title">Hardware & tuning</h3><p class="note">Measure this PC before changing anything. Benchmarks use existing models and temporary local runtimes. Close other GPU-heavy work and unload models for a cleaner comparison.</p>
   <div class="setting-row"><div><h3>Processor</h3><p>${value(info.cpu)}</p></div><span>${value(info.physical_cores)} cores / ${value(info.logical_cores)} threads</span></div>
   <div class="setting-row"><div><h3>Memory</h3><p>Physical RAM installed</p></div><span>${formatBytes(info.ram_bytes)}</span></div>
   ${info.gpus.map(g=>`<div class="setting-row"><div><h3>${value(g.name)}</h3><p>Driver-reported GPU memory</p></div><span>${formatBytes(g.vram_bytes)}</span></div>`).join('')||'<p class="note">GPU information unavailable.</p>'}
   <details><summary>Runtime version</summary><pre>${value(info.runtime_version)}</pre></details>
   <h4 class="section-heading">Compare inference settings</h4><form id="tuning-form"><label class="field">Installed model<select name="model" required>${info.models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select></label>
   ${!info.models.length?'<p class="note" role="status">No installed models are registered in this profile. Configure an existing model in Model library before benchmarking.</p>':''}${!info.runtime_available?'<p class="note" role="status">A local llama-server executable is not configured. Benchmarking is unavailable until an existing runtime is configured.</p>':''}
   <div class="form-grid">${field('CPU thread counts (comma separated)','threads','4,8')}${field('GPU layers (0 = CPU, -1 = full)','gpu_layers','0,16,-1')}</div>
   <p class="small-note">Three repetitions per configuration at this model’s configured context. Records first-token time, prompt/decode speed when reported, RAM, GPU-memory snapshots, and backend delay. Runtime load failures are retained. GPU snapshots cover the whole device.</p>
   <label class="switch"><input name="consent" type="checkbox" required> I want to run this local CPU/GPU benchmark.</label>
   <div class="form-actions"><button class="btn primary" type="submit" ${!info.models.length||!info.runtime_available?'disabled':''}>Start benchmark</button><button class="btn" type="button" id="tuning-stop">Stop benchmark</button><button class="btn" type="button" id="tuning-rollback">Roll back selection</button></div></form>
   <p id="tuning-status" role="status"></p><div id="tuning-results"></div><p class="small-note" id="tuning-browser"></p><p class="small-note">Nothing applies automatically. Apply a measured profile explicitly, then restart Luminaria and its owned model manager. Existing selections can be rolled back. Browser/render measurements are separate from model speed.</p>`;
  let timer,last=performance.now(),maximumDelay=null,renderCount=0,lastRender=null,disposed=false;
  const render=e=>{if(body.isConnected&&e.detail){renderCount++;lastRender=e.detail}};
  window.addEventListener('studio-render-stats',render);
  const clock=setInterval(()=>{const at=performance.now();maximumDelay=Math.max(maximumDelay||0,at-last-100);last=at;if(!body.isConnected)dispose()},100);
  function dispose(){if(disposed)return;disposed=true;clearTimeout(timer);clearInterval(clock);window.removeEventListener('studio-render-stats',render)}
  const n=v=>typeof v==='number'?v.toFixed(2):'Unavailable';
  async function refresh(){
   if(!body.isConnected){dispose();return}
   const data=await api('/tuning');if(!body.isConnected){dispose();return}
   const job=data.job.state==='Idle'?data.history.at(-1)||data.job:data.job;
   $('#tuning-status').textContent=job.state+(job.progress?.threads?` · ${job.progress.threads} threads / ${job.progress.gpu_layers} GPU layers · repetition ${job.progress.repetition}/3`:'')+(job.error?' · '+job.error:'');
   $('#tuning-form button[type=submit]').disabled=job.state==='Running'||!info.models.length||!info.runtime_available;
   $('#tuning-stop').disabled=job.state!=='Running';$('#tuning-rollback').disabled=!data.rollback_available||job.state==='Running';
   const variants=job.variants||[];
   $('#tuning-results').innerHTML=variants.length?`<table class="insight-table"><caption>Measured configurations</caption><thead><tr><th>Threads / GPU layers</th><th>First token</th><th>End-to-end tok/s</th><th>RAM peak</th><th>Outcome</th></tr></thead><tbody>${variants.map(v=>`<tr><th>${v.threads} / ${v.gpu_layers}</th><td>${n(v.median_first_token_seconds)} s</td><td>${n(v.median_tps)}</td><td>${formatBytes(v.peak_runtime_rss_bytes)}</td><td>${v.error?esc(v.error):'Measured, 3 repetitions'}</td></tr>`).join('')}</tbody></table>${job.state==='Completed'&&job.best?`<button class="btn" id="tuning-apply">Apply best measured profile (${job.best.threads} threads / ${job.best.gpu_layers} layers)</button>`:''}<details><summary>Measurements and provenance</summary><pre>${esc(JSON.stringify(job,null,2))}</pre></details>`:'';
   const apply=$('#tuning-apply');if(apply)apply.onclick=safe(async()=>{apply.disabled=true;const r=await api('/tuning/apply','POST',{job:job.id});toast(r.message);await refresh()});
   $('#tuning-browser').textContent=`Browser scheduling delay, maximum while this panel was open: ${n(maximumDelay)} ms. Renderer samples observed: ${renderCount}; latest reported frame rate: ${n(lastRender?.fps)} fps. These are browser observations, not GPU completion or model speed.`;
   if(job.state==='Running')timer=setTimeout(()=>safe(refresh)(),1500);
  }
  $('#tuning-form').onsubmit=safe(async event=>{event.preventDefault();const form=new FormData(event.target);const parse=key=>String(form.get(key)).split(',').map(x=>{if(!/^-?\d+$/.test(x.trim()))throw Error('Enter whole numbers separated by commas.');return Number(x.trim())});await api('/tuning/start','POST',{model:form.get('model'),threads:parse('threads'),gpu_layers:parse('gpu_layers'),consent:form.get('consent')==='on'});maximumDelay=null;renderCount=0;lastRender=null;await refresh()});
  $('#tuning-stop').onclick=safe(async()=>{await api('/tuning/stop','POST');await refresh()});
  $('#tuning-rollback').onclick=safe(async()=>{const r=await api('/tuning/apply','POST',{rollback:true});toast(r.message);await refresh()});
  await refresh();
 };
})();
