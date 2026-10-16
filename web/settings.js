/* Categorized settings backed by the local API. */
(()=>{
 const sections=['Models','Voice','Tools & permissions','Memory & context','Appearance','Accounts','Updates'];
 let library,selected,chosen;
 const original=openPanel;
 openPanel=async function(name){if(['settings','models'].includes(name))return settingsView(name==='models'?'Models':(window.studioSettingsCategory||'Models'));$('.sheet').classList.remove('settings-sheet');return original(name)};
 const row=(title,description,value)=>`<div class="setting-row"><div><h3>${title}</h3><p>${description}</p></div><span class="badge">${value}</span></div>`;
 async function settingsView(section){
  library=await api('/models');selected=selected||library.active;chosen=library.active;
  showPanel('Settings','Your app, configured your way.',`<div class="settings-layout"><nav class="settings-nav" aria-label="Settings categories">${sections.map(s=>`<button data-settings-section="${s}" aria-current="${s===section?'page':'false'}">${s}</button>`).join('')}<p>Settings are saved<br>on this PC.</p></nav><section id="settings-body" class="settings-body"></section></div>`);
  $('.sheet').classList.add('settings-sheet');$$('[data-settings-section]').forEach(b=>b.onclick=safe(()=>settingsView(b.dataset.settingsSection)));
  const body=$('#settings-body');
  if(section==='Models'){
   body.innerHTML=`<h3 class="settings-page-title">Models</h3><p class="settings-intro">Choose by capability, context, and measured performance.</p><input class="model-search" id="model-search" placeholder="Find a model or capability…" aria-label="Find a model"><div class="model-browser"><div id="model-options" aria-label="Model choices"></div><article id="model-detail"></article></div><details class="advanced-settings"><summary>Advanced model settings</summary><button class="btn" id="advanced-inference">Configure inference</button></details>`;
   function draw(){
    const q=$('#model-search').value.toLowerCase();$('#model-options').innerHTML=library.models.filter(m=>(m.name+' '+m.description+' '+m.strengths.join(' ')).toLowerCase().includes(q)).map(m=>`<button class="model-option ${m.id===selected?'selected':''}" data-model-detail="${esc(m.id)}"><span><strong>${esc(m.name)}</strong>${m.id===chosen?'<em>Active</em>':''}</span><small>${esc(m.strengths.slice(0,2).join(' · '))}</small><small>${Math.round(m.context/1024)}k context · ${m.benchmarks?.length?m.benchmarks[0].tps+' tok/s measured':'Not benchmarked'}</small></button>`).join('')||'<p class="note">No matching models.</p>';
    $$('[data-model-detail]').forEach(b=>b.onclick=()=>{selected=b.dataset.modelDetail;draw()});
    const m=library.models.find(m=>m.id===selected)||library.models[0];if(!m){$('#model-detail').innerHTML='<p class="note">No models registered. Configure your local model server to begin.</p>';return}const b=m.benchmarks?.[0];
    $('#model-detail').innerHTML=`<span class="badge">${m.vision?'Vision + text':'Text'}</span><h3>${esc(m.name)}</h3><p class="model-description">${esc(m.description)}</p><div class="model-tags">${m.strengths.map(s=>'<span class="badge">'+esc(s)+'</span>').join('')}</div><dl class="model-specs"><div><dt>Configured context</dt><dd>${m.context.toLocaleString()} tokens</dd></div><div><dt>Generation speed</dt><dd>${b?b.tps+' tok/s':'Not benchmarked'}</dd></div><div><dt>Quantization</dt><dd>${esc(m.quantization)}</dd></div><div><dt>Model file size</dt><dd>${formatBytes(m.bytes)}</dd></div></dl><p class="benchmark-caveat">${b?esc(b.test)+(b.measurement?' · '+esc(b.measurement):'')+'. Historical result on this PC; speed varies with context.':'File download verified. Speed and task quality have not been measured on this PC.'}</p><div class="model-actions"><button class="btn primary choose-model" id="choose-model" ${m.id===chosen?'disabled':''}>${m.id===chosen?'Active model':'Use this model'}</button><button class="btn" id="benchmark-model" aria-expanded="false" aria-controls="benchmark-preview">Benchmark</button></div><section id="benchmark-preview" class="benchmark-preview" hidden><h4>Benchmark this model</h4><p>Measure generation speed, time to first token, and output token count on this PC.</p><p class="small-note">This runs a fixed 256-token generation test. It may load this model and take several minutes. Speed varies with context; this is not a coding-quality score.</p><button class="btn primary" id="run-benchmark">Run benchmark</button><p id="benchmark-result" role="status"></p></section><p class="small-note">One loaded model at a time. Finish active tasks before switching.</p>${m.benchmarks?.length?'<details class="advanced-settings"><summary>All recorded benchmarks</summary>'+m.benchmarks.map(b=>`<p>${esc(b.test)} · <strong>${b.tps} tok/s</strong></p>`).join('')+'</details>':''}`;
    $('#benchmark-model').onclick=()=>{const area=$('#benchmark-preview');area.hidden=!area.hidden;$('#benchmark-model').setAttribute('aria-expanded',String(!area.hidden))};
    $('#choose-model').onclick=safe(async()=>{await api('/models/'+encodeURIComponent(m.id)+'/select','POST',{});chosen=m.id;await refresh();await settingsView('Models');toast('Model selected')});
    $('#run-benchmark').onclick=safe(async()=>{const btn=$('#run-benchmark'),result=$('#benchmark-result');btn.disabled=true;result.textContent='Benchmark running…';try{const r=await api('/models/'+encodeURIComponent(m.id)+'/benchmark','POST',{});result.textContent=r.tps+' tok/s · '+r.first_token_seconds+' s to first token · '+r.completion_tokens+' output tokens';library=await api('/models')}catch(e){result.textContent=e.message;throw e}finally{btn.disabled=false}});

   }
   $('#model-search').oninput=draw;draw();$('#advanced-inference').onclick=()=>studioSettingsSection('Inference',body);
  }else{
   await studioSettingsSection(section,body);
  }
 }
 const originalClose=closePanel;closePanel=function(){$('.sheet').classList.remove('settings-sheet');return originalClose()};
})();
