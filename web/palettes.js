/* Appearance: light, dark or follow system, with every color customizable. Black and white by default. */
async function renderPaletteSettings(body,p){
 const A=window.luminariaAppearance;let draft=A.fromPreferences(p),timer=0,saving=Promise.resolve();
 const modeName={light:'Light',dark:'Dark',system:'Follow system'};
 const swatch=m=>{const t=A.tokens({...draft,mode:m==='system'?A.current.mode:m}).tokens;return `<span class="mode-sample" aria-hidden="true" style="--s-bg:${t.bg};--s-panel:${t.panel};--s-line:${t.line};--s-text:${t.text};--s-muted:${t.muted};--s-accent:${t.accent}"><i></i><span><b></b><b></b><em></em></span></span>`};
 const colorRow=(key,label,value,overridden)=>`<div class="color-row"><label for="c-${key}">${label}</label><span class="color-value"><input type="color" id="c-${key}" data-color="${key}" value="${value.toLowerCase()}"><code>${value.toUpperCase()}</code></span><button type="button" class="text-button" data-reset-color="${key}" ${overridden?'':'hidden'}>Reset</button></div>`;
 function render(){
  const r=A.tokens(draft),mode=r.mode,own=draft.modes[mode],t=r.tokens,other=mode==='dark'?'light':'dark';
  body.innerHTML=`<h3 class="settings-page-title">Appearance</h3><p class="settings-intro">Black on white in light mode, white on black in dark mode. Change any color; changes apply as you make them.</p>
  <section aria-labelledby="mode-heading"><h4 class="appearance-heading" id="mode-heading">Mode</h4><div class="mode-choices" role="group" aria-labelledby="mode-heading">${['light','dark'].map(m=>`<button type="button" class="mode-choice" data-mode="${m}" aria-pressed="${draft.mode===m}">${swatch(m)}<strong>${modeName[m]}</strong><small>${m==='system'?'Matches Windows · now '+modeName[A.current.mode].toLowerCase():m==='light'?'Black text on white':'White text on black'}</small></button>`).join('')}</div></section>
  <section aria-labelledby="accent-heading"><h4 class="appearance-heading" id="accent-heading">Accent</h4><p class="note">Used for primary buttons, selection, focus rings and progress. With no accent, these use the text color.</p>
   <div class="color-row"><label><input type="checkbox" id="accent-on" ${draft.accent?'checked':''}> Accent color in both modes</label><span class="color-value"><input type="color" id="accent-shared" value="${(draft.accent||t.text).toLowerCase()}" ${draft.accent?'':'disabled'} aria-label="Shared accent color"><code>${draft.accent||'None'}</code></span></div>
   <div class="color-row"><label><input type="checkbox" id="accent-mode-on" ${own.accent?'checked':''}> Different accent in ${modeName[mode].toLowerCase()} mode</label><span class="color-value"><input type="color" id="accent-mode" value="${(own.accent||t.accent).toLowerCase()}" ${own.accent?'':'disabled'} aria-label="${modeName[mode]} mode accent color"><code>${own.accent||'Uses shared'}</code></span></div></section>
  <details class="advanced-settings appearance-advanced" ${body.dataset.advanced==='open'?'open':''}><summary>All ${modeName[mode].toLowerCase()} mode colors</summary><p class="note">These apply to ${modeName[mode].toLowerCase()} mode only. Switch to ${modeName[other].toLowerCase()} mode to edit its colors separately.</p>${A.EDITABLE.map(([group,items])=>`<fieldset><legend>${group}</legend>${items.map(([k,l])=>colorRow(k,l,t[k],k in own.colors)).join('')}</fieldset>`).join('')}</details>
  <div id="contrast-warnings" role="status" aria-live="polite"></div>
  <div class="form-actions appearance-actions"><button type="button" class="btn" id="reset-mode">Reset ${modeName[mode].toLowerCase()} mode</button><button type="button" class="btn danger" id="reset-all">Reset all appearance</button><span class="save-status" id="appearance-status" role="status"></span></div>
  <h4 class="appearance-heading">Motion and display</h4><form>${checkField('Reactive AI entity','motion',p.motion,'Neural workspace while working; an audio-reactive entity during conversation. System reduced-motion settings take priority.'+(matchMedia('(prefers-reduced-motion: reduce)').matches?' Windows is currently set to reduce motion, so the background stays still.':''))}${checkField('Chat performance strip','metrics',p.metrics,'Keep real context, speed and compaction information beside the composer.')}<button class="btn primary" type="submit">Save motion and display</button></form>`;
  bind();showWarnings(t);diagnostics()
 }
 function status(text,error){const s=body.querySelector('#appearance-status');if(s){s.textContent=text;s.classList.toggle('error-text',!!error)}}
 function showWarnings(t){const out=body.querySelector('#contrast-warnings'),list=A.warnings(t);out.innerHTML=list.length?`<div class="contrast-warning"><strong>Low contrast</strong><ul>${list.map(w=>`<li>${esc(w.what)}: ${w.ratio}:1, needs ${w.min}:1</li>`).join('')}</ul></div>`:''}
 function change(persistNow){
  const r=A.apply(draft);showWarnings(r.tokens);status('Saving…');clearTimeout(timer);
  const value=JSON.parse(JSON.stringify(draft));
  // Start persistence immediately: a desktop close can discard a debounce timer.
  saving=saving.then(async()=>{try{await api('/preferences','POST',{appearance:value});studioPrefs.appearance=value;studioPrefs.theme_mode=value.mode;status('Saved')}catch(e){status('Not saved: '+e.message+'. Change any color to retry.',true)}})
 }
 function bind(){
  const $b=s=>body.querySelector(s),own=()=>draft.modes[A.tokens(draft).mode];
  body.querySelector('.appearance-advanced').ontoggle=e=>body.dataset.advanced=e.target.open?'open':'';
  body.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{draft.mode=b.dataset.mode;change(true);render();status('Saving…')});
  $b('#accent-on').onchange=e=>{draft.accent=e.target.checked?$b('#accent-shared').value.toUpperCase():'';change();render();status('Saving…')};
  $b('#accent-shared').oninput=e=>{draft.accent=e.target.value.toUpperCase();e.target.nextElementSibling.textContent=draft.accent;change()};
  $b('#accent-mode-on').onchange=e=>{if(e.target.checked)own().accent=$b('#accent-mode').value.toUpperCase();else delete own().accent;change();render();status('Saving…')};
  $b('#accent-mode').oninput=e=>{own().accent=e.target.value.toUpperCase();e.target.nextElementSibling.textContent=own().accent;change()};
  body.querySelectorAll('[data-color]').forEach(i=>i.oninput=()=>{own().colors[i.dataset.color]=i.value.toUpperCase();i.nextElementSibling.textContent=i.value.toUpperCase();body.querySelector(`[data-reset-color="${i.dataset.color}"]`).hidden=false;change()});
  body.querySelectorAll('[data-reset-color]').forEach(b=>b.onclick=()=>{delete own().colors[b.dataset.resetColor];change();render();status('Saving…')});
  $b('#reset-mode').onclick=()=>{const m=A.tokens(draft).mode;draft.modes[m]={colors:{}};change(true);render();status('Saving…')};
  $b('#reset-all').onclick=()=>{if(!confirm('Reset every appearance setting? Both modes return to black and white, accents are removed and the mode returns to light.'))return;draft=A.normalize(JSON.parse(JSON.stringify(A.DEFAULT)));change(true);render();status('Saving…')};
  body.querySelector('form').onsubmit=safe(async e=>{e.preventDefault();await savePrefs({motion:body.querySelector('#motion').checked,metrics:body.querySelector('#metrics').checked})});
 }
 function diagnostics(){
  const d=document.createElement('details');d.className='advanced-settings';d.innerHTML='<summary>Animation diagnostics</summary><p class="note" id="render-diagnostics">Measuring rendered frames…</p><p class="small-note">Measures canvas draw submissions, not GPU completion time or model speed. Quality adapts to keep frames steady. Pausing or system reduced motion suppresses spatial animation.</p>';body.append(d);
  const update=e=>{const out=document.getElementById('render-diagnostics');if(!out){window.removeEventListener('studio-render-stats',update);return}const s=e.detail;out.textContent=s.mode==='fallback'?s.reason:s.paused?'Spatial animation paused'+(s.reducedMotion?' by your system preference.':'.'):`${s.fps} rendered frames/s · ${s.width} × ${s.height} · quality ${s.quality??'—'} · ${s.nodes??0} task nodes`};
  window.addEventListener('studio-render-stats',update);if(window.luminariaRenderStats)update({detail:window.luminariaRenderStats})
 }
 render();
}
