/* Opt-in tuning uses the existing settings shell and native controls. */
(()=>{
 const original=studioSettingsSection;
 studioSettingsSection=async function(section,body){
  if(section!=='Hardware & tuning')return original(section,body);
  body.innerHTML='<h3 class="settings-page-title">Hardware & tuning</h3><p role="status">Reading this PC’s hardware…</p>';
  const info=await api('/hardware');if(!body.isConnected)return;
  const value=v=>v==null?'Unavailable':esc(v);
  body.innerHTML=`<h3 class="settings-page-title">Hardware & tuning</h3><p class="settings-intro">What this PC has, and which settings run your models fastest. Close other GPU-heavy apps before measuring.</p><h4 class="section-heading">This PC</h4>
   <div class="setting-row"><div><h3>Processor</h3><p>${value(info.cpu)}</p></div><span>${value(info.physical_cores)} cores / ${value(info.logical_cores)} threads</span></div>
   <div class="setting-row"><div><h3>Memory</h3><p>Physical RAM installed</p></div><span>${formatBytes(info.ram_bytes)}</span></div>
   ${info.gpus.map(g=>`<div class="setting-row"><div><h3>${value(g.name)}</h3><p>Driver-reported GPU memory</p></div><span>${formatBytes(g.vram_bytes)}</span></div>`).join('')||'<p class="note">GPU information unavailable.</p>'}
   <details class="s-more"><summary>Runtime version</summary><pre>${value(info.runtime_version)}</pre></details>
   <h4 class="section-heading">Find the fastest settings</h4><form id="tuning-form"><label class="field">Installed model<select name="model" required>${info.models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select></label>
   ${!info.models.length?'<p class="note" role="status">No installed models are registered in this profile. Configure an existing model in Model library before benchmarking.</p>':''}${!info.runtime_available?'<p class="note" role="status">A local llama-server executable is not configured. Benchmarking is unavailable until an existing runtime is configured.</p>':''}
   <div class="tuning-modes" role="radiogroup" aria-label="What to measure"><label class="tuning-mode"><input type="radio" name="mode" value="smart" checked><span><strong>Smart</strong><small>Measures a few settings around what should fit this PC: GPU layers, expert placement for mixture-of-experts models, and CPU threads.</small></span></label><label class="tuning-mode"><input type="radio" name="mode" value="manual"><span><strong>Manual</strong><small>Choose exact thread counts and GPU layer counts to compare.</small></span></label></div><div class="form-grid" id="tuning-manual" hidden>${field('CPU thread counts (comma separated)','threads','4,8')}${field('GPU layers (0 = CPU, -1 = full)','gpu_layers','0,16,-1')}${field('Expert layers on CPU (mixture-of-experts only)','cpu_moe','0')}</div>
   
   <label class="switch"><input name="consent" type="checkbox" required> I want to run this local CPU/GPU benchmark.</label>
   <div class="form-actions"><button class="btn primary" type="submit" ${!info.models.length||!info.runtime_available?'disabled':''}>Start benchmark</button><button class="btn" type="button" id="tuning-stop">Stop benchmark</button><button class="btn" type="button" id="tuning-rollback">Roll back selection</button></div></form>
   <p id="tuning-status" role="status"></p><div id="tuning-results"></div><p class="small-note" id="tuning-browser"></p><details class="s-more"><summary>How measuring works</summary><p>Each setting runs three times at this model’s configured context. Luminaria records first-token time, prompt and generation speed when reported, RAM, GPU-memory snapshots and backend delay. Settings that fail to load are kept in the results. GPU snapshots cover the whole device.</p><p>Nothing applies automatically. Apply a measured profile, then restart Luminaria and its model manager. You can roll back to your previous selection.</p></details>`;
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
   $('#tuning-status').textContent=job.state+(job.progress?.threads?` · ${job.progress.threads} threads / ${job.progress.gpu_layers===-1?'all':job.progress.gpu_layers} GPU layers${job.progress.cpu_moe?' / '+job.progress.cpu_moe+' expert layers on CPU':''} · repetition ${job.progress.repetition}/3`:'')+(job.error?' · '+job.error:'');
   $('#tuning-form button[type=submit]').disabled=job.state==='Running'||!info.models.length||!info.runtime_available;
   $('#tuning-stop').disabled=job.state!=='Running';$('#tuning-rollback').disabled=!data.rollback_available||job.state==='Running';
   const variants=job.variants||[];
   $('#tuning-results').innerHTML=variants.length?`<table class="insight-table"><caption>Measured configurations</caption><thead><tr><th>Setting</th><th>First token</th><th>End-to-end tok/s</th><th>RAM peak</th><th>Outcome</th></tr></thead><tbody>${variants.map(v=>`<tr><th>${v.threads} threads · ${v.gpu_layers===-1?'all layers on GPU':v.gpu_layers===0?'CPU only':v.gpu_layers+' GPU layers'}${v.cpu_moe?' · '+v.cpu_moe+' expert layers on CPU':''}${v.ubatch&&v.ubatch!==128?' · batch '+v.ubatch:''}</th><td>${n(v.median_first_token_seconds)} s</td><td>${n(v.median_tps)}</td><td>${formatBytes(v.peak_runtime_rss_bytes)}</td><td>${v.error?esc(v.error):'Measured, 3 repetitions'}</td></tr>`).join('')}</tbody></table>${job.state==='Completed'&&job.best?`<button class="btn" id="tuning-apply">Apply best measured profile (${job.best.threads} threads / ${job.best.gpu_layers} layers)</button>`:''}<details><summary>Measurements and provenance</summary><pre>${esc(JSON.stringify(job,null,2))}</pre></details>`:'';
   const apply=$('#tuning-apply');if(apply)apply.onclick=safe(async()=>{apply.disabled=true;const r=await api('/tuning/apply','POST',{job:job.id});toast(r.message);await refresh()});
   $('#tuning-browser').textContent=`Browser scheduling delay, maximum while this panel was open: ${n(maximumDelay)} ms. Renderer samples observed: ${renderCount}; latest reported frame rate: ${n(lastRender?.fps)} fps. These are browser observations, not GPU completion or model speed.`;
   if(job.state==='Running')timer=setTimeout(()=>safe(refresh)(),1500);
  }
  $$('#tuning-form [name=mode]').forEach(r=>r.onchange=()=>{$('#tuning-manual').hidden=$('#tuning-form [name=mode]:checked').value!=='manual'});
  $('#tuning-form').onsubmit=safe(async event=>{event.preventDefault();const form=new FormData(event.target);const parse=key=>String(form.get(key)).split(',').map(x=>{if(!/^-?\d+$/.test(x.trim()))throw Error('Enter whole numbers separated by commas.');return Number(x.trim())});await api('/tuning/start','POST',form.get('mode')==='manual'?{model:form.get('model'),threads:parse('threads'),gpu_layers:parse('gpu_layers'),cpu_moe:parse('cpu_moe'),consent:form.get('consent')==='on'}:{model:form.get('model'),smart:true,consent:form.get('consent')==='on'});maximumDelay=null;renderCount=0;lastRender=null;await refresh()});
  $('#tuning-stop').onclick=safe(async()=>{await api('/tuning/stop','POST');await refresh()});
  $('#tuning-rollback').onclick=safe(async()=>{const r=await api('/tuning/apply','POST',{rollback:true});toast(r.message);await refresh()});
  await refresh();
 };
})();
