/* Insights: measured usage on this PC, optional daily-total sync, export and delete.
   Every figure comes from recorded events; anything not measured is labelled, never estimated. */
(()=>{
 const num=n=>n==null?'—':Number(n).toLocaleString();
 const compact=n=>n==null?'—':n>=1e9?(n/1e9).toFixed(1)+'B':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e4?Math.round(n/1e3)+'k':Number(n).toLocaleString();
 const span=s=>{s=Math.round(s||0);if(s<60)return s+' s';const m=Math.floor(s/60);if(m<60)return m+' min'+(s%60?' '+s%60+' s':'');const h=Math.floor(m/60);return h+' h'+(m%60?' '+m%60+' min':'')};
 const day=d=>d?new Date(d+'T12:00:00').toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}):'—';
 const stamp=t=>t?new Date(t*1000).toLocaleString(undefined,{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}):'never';
 const stat=(label,value,detail)=>`<div class="insight-stat"><dt>${label}</dt><dd><strong>${value}</strong>${detail?`<small>${detail}</small>`:''}</dd></div>`;
 const spec=(label,value,detail)=>`<div><dt>${label}</dt><dd>${value}${detail?`<small>${detail}</small>`:''}</dd></div>`;
 function chart(history){
  const max=Math.max(1,...history.map(h=>h.tokens_in+h.tokens_out));
  const bars=history.map(h=>{const total=h.tokens_in+h.tokens_out,label=`${day(h.day)}: ${h.covered?num(total)+' tokens':'not recorded'}`;
   return `<li class="${h.covered?'':'uncovered'}" title="${esc(label)}"><span class="bar-in" style="height:${(h.tokens_in/max*100).toFixed(1)}%"></span><span class="bar-out" style="height:${(h.tokens_out/max*100).toFixed(1)}%"></span><span class="sr-only">${esc(label)}</span></li>`}).join('');
  return `<figure class="insight-chart"><figcaption><span>Tokens per day · last ${history.length} days</span><span class="chart-legend"><i class="bar-in"></i>Read <i class="bar-out"></i>Generated${history.some(h=>!h.covered)?' <i class="uncovered"></i>Before recording started':''}</span></figcaption><ol aria-label="Tokens per day">${bars}</ol><div class="chart-axis"><span>${day(history[0].day)}</span><span>Today</span></div></figure>`;
 }
 function tallyRows(items,empty){
  if(!items?.length)return `<p class="small-note">${empty}</p>`;
  return `<table class="insight-table"><thead><tr><th scope="col">Name</th><th scope="col">Succeeded</th><th scope="col">Failed</th><th scope="col">Declined</th></tr></thead><tbody>${items.map(t=>`<tr><th scope="row">${esc(t.name.replace('__',' · '))}</th><td>${num(t.ok)}</td><td class="${t.failed?'warn-note':''}">${num(t.failed)}</td><td>${num(t.denied)}</td></tr>`).join('')}</tbody></table>`;
 }
 async function render(body){
  body.innerHTML='<h3 class="settings-page-title">Insights</h3><p class="note" role="status">Reading recorded activity…</p>';
  const s=await api('/insights');if(!body.isConnected)return;
  const sync=s.sync||{},acct=s.account,life=s.lifetime;
  const coverage=s.coverage_start?`Measured on this PC since ${esc(stamp(s.coverage_start))}. Earlier activity was not recorded and is not estimated.`:'Nothing recorded yet. Insights start with your next task.';
  let html=`<h3 class="settings-page-title">Insights</h3><p class="settings-intro">${coverage} Counts and timings only: no chat text, files, addresses or tool output are recorded.</p>`;
  if(life){
   const streak=s.streak||{},busy=s.busiest_day,fast=s.fastest;
   html+=`<dl class="insight-stats">
    ${stat('Total tokens',compact(life.total),`${compact(life.tokens_in)} read · ${compact(life.tokens_out)} generated${life.cached!=null?` · ${compact(life.cached)} reused from cache`:''}`)}
    ${stat('Current streak',streak.current+' day'+(streak.current===1?'':'s'),`Longest ${streak.longest} day${streak.longest===1?'':'s'}`)}
    ${stat('Busiest day',busy?compact(busy.tokens)+' tokens':'—',busy?`${esc(day(busy.day))} · ${busy.generations} response${busy.generations===1?'':'s'}`:'Not measured yet')}
    ${stat('Fastest measured speed',fast?fast.tps+' tok/s':'—',fast?`${esc(fast.model||'Unknown model')} · ${esc(day(fast.day))}`:'Not measured yet')}
   </dl>${chart(s.history)}
   <h4 class="section-heading">Defined measures</h4><dl class="model-specs insight-specs">
    ${spec('Largest task',s.largest_task?num(s.largest_task.tokens)+' tokens':'—',s.largest_task?`${esc(day(s.largest_task.day))} · ${s.largest_task.generations} model response${s.largest_task.generations===1?'':'s'}. Tokens read and generated across one task run.`:'No finished task yet')}
    ${spec('Longest task',s.longest_task?span(s.longest_task.active)+' active':'—',s.longest_task?`${esc(day(s.longest_task.day))} · ${span(s.longest_task.wait)} waiting for your approval · ${span(s.longest_task.paused)} paused. Active time excludes both.`:'No finished task yet')}
    ${spec('Streak rule','A day counts when at least one model response completed',`Days end at midnight in ${esc(s.timezone_label)}${streak.last_active?` · last active ${esc(day(streak.last_active))}`:''}`)}
    ${spec('Busiest day rule','Most tokens read and generated in one calendar day','Different from the largest single task and from the fastest response.')}
    ${spec('Fastest speed rule','Highest generation speed of a single response','Only responses with at least 32 generated tokens count; shorter ones are too noisy.')}
    ${spec('Reasoning',`${num(s.reasoning.generations)} of ${num(s.reasoning.of)} responses`,`Reasoning was turned on for ${num(s.reasoning.tasks)} task${s.reasoning.tasks===1?'':'s'}. Luminaria offers reasoning on or off, so no levels are recorded. Hidden reasoning is not estimated.`)}
    ${spec('Skills',`${num(s.skills.invoked)} used`,`Browsed by the assistant ${num(s.skills.browsed_by_assistant)} · opened by you ${num(s.skills.viewed)} · turned on ${num(s.skills.enabled)} · turned off ${num(s.skills.disabled)}${s.skills.top.length?'. Most used: '+s.skills.top.map(t=>esc(t.name)+' ('+t.count+')').join(', '):''}`)}
   </dl>
   <h4 class="section-heading">Tools</h4>${tallyRows(s.tools,'No tool use recorded yet.')}
   ${s.integrations?.length?`<h4 class="section-heading">Integrations</h4>${tallyRows(s.integrations,'')}`:''}
   <h4 class="section-heading">Models</h4>${s.models.length?`<table class="insight-table"><thead><tr><th scope="col">Model</th><th scope="col">Responses</th><th scope="col">Generated</th><th scope="col">Median speed</th></tr></thead><tbody>${s.models.map(m=>`<tr><th scope="row">${esc(m.model)}</th><td>${num(m.generations)}</td><td>${num(m.tokens_out)}</td><td>${m.median_tps!=null?m.median_tps+' tok/s':'Not measured'}</td></tr>`).join('')}</tbody></table>`:'<p class="small-note">No model responses recorded yet.</p>'}`;
  }
  if(s.speed_history?.length)html+=`<details class="advanced-settings"><summary>Measured model speed over time</summary><p class="small-note">Daily medians of responses with at least 32 generated tokens. End-to-end measurements include prompt processing and are not controlled benchmark comparisons.</p><table class="insight-table"><thead><tr><th scope="col">Day</th><th scope="col">Model</th><th scope="col">Median tok/s</th><th scope="col">Samples</th></tr></thead><tbody>${s.speed_history.map(r=>`<tr><th scope="row">${esc(day(r.day))}</th><td>${esc(r.model||'Unknown')}</td><td>${num(r.median_tps)}</td><td>${num(r.samples)}</td></tr>`).join('')}</tbody></table></details>`;
  if(s.missing?.length)html+=`<h4 class="section-heading">Not measured</h4><ul class="insight-missing">${s.missing.map(m=>`<li>${esc(m)}</li>`).join('')}</ul>`;
  html+=`<h4 class="section-heading">Time zone</h4><form class="insight-zone" id="insight-zone"><label class="field">Days and streaks follow<input name="timezone" value="${esc(s.timezone_requested)}" placeholder="This PC (${esc(s.timezone_label)})" autocomplete="off" spellcheck="false"></label><button class="btn" type="submit">Save</button></form><p class="small-note" id="zone-status" role="status">${s.timezone_valid?'Leave empty to use this PC’s time zone, or enter a name such as Europe/Amsterdam. Use the same zone on each PC so synced days line up.':'The saved time zone is not known on this PC, so this PC’s zone is used.'}</p>
  <h4 class="section-heading">Sync across devices</h4>
  <div class="setting-row"><div><h3>Sync daily totals to your account</h3><p>Off unless you turn it on. Sends one line per day with these counts: tokens read, generated and reused, responses, tasks, active and waiting seconds, tool successes and failures, reasoning responses and skills used. Model names, tool names, chat text and files stay on this PC.</p></div><label class="switch"><input type="checkbox" id="insight-sync" ${sync.enabled?'checked':''}> On</label></div>
  <div id="sync-detail">${sync.enabled?`<p class="small-note">Last synced ${esc(stamp(sync.last_sync))}.${sync.last_error?` <span class="warn-note">${esc(sync.last_error)}</span>`:''} Uploading again replaces this PC’s totals for each day, so nothing is counted twice. The service keeps synced days for two years.</p><div class="form-actions"><button class="btn" id="sync-now">Sync now</button></div>`:''}
  ${acct?`<dl class="model-specs insight-specs"><div><dt>All synced devices</dt><dd>${num(acct.total)} tokens<small>${acct.devices} device${acct.devices===1?'':'s'} · ${acct.active_days} active day${acct.active_days===1?'':'s'} since ${esc(day(acct.first_day))} · ${span(acct.active_seconds)} active · longest streak ${acct.streak.longest} day${acct.streak.longest===1?'':'s'}</small></dd></div></dl>`:''}</div>
  <h4 class="section-heading">Your data</h4><div class="form-actions"><button class="btn" id="insight-export">Export as JSON</button><button class="btn quiet-danger" id="delete-local">Delete on this PC</button><button class="btn quiet-danger" id="delete-synced" ${sync.enabled||acct?'':'disabled'}>Delete synced totals</button></div><p class="small-note" id="data-status" role="status" aria-live="polite">Insights are kept until you delete them. Permanently deleting a chat does not remove its counts, since they contain no chat content.</p>`;
  body.innerHTML=html;
  const status=body.querySelector('#data-status');
  body.querySelector('#insight-zone').onsubmit=safe(async e=>{e.preventDefault();const out=body.querySelector('#zone-status');try{await api('/insights/timezone','POST',{timezone:new FormData(e.target).get('timezone')});toast('Time zone saved');await render(body)}catch(error){out.textContent=error.message}});
  const after=async message=>{if(!body.isConnected)return;await render(body);if(message&&body.isConnected){const out=body.querySelector('#data-status');out.textContent=message;out.classList.add('warn-note')}};
  body.querySelector('#insight-sync').onchange=safe(async e=>{const box=e.target;box.disabled=true;let problem='';
   try{if(box.checked&&!confirm('Turn on insights sync? Daily totals from this PC are sent to your Luminaria account. Nothing else leaves this PC.')){box.checked=false;box.disabled=false;return}
    await api('/insights/sync-setting','POST',{enabled:box.checked});toast(box.checked?'Insights sync is on.':'Insights sync is off. Already synced totals stay until you delete them.')}
   catch(error){problem=error.message}
   await after(problem)});
  body.querySelector('#sync-now')?.addEventListener('click',safe(async e=>{e.target.disabled=true;let problem='';try{const r=await api('/insights/sync','POST',{});toast(`Synced ${r.sent} day${r.sent===1?'':'s'}`)}catch(error){problem=error.message}await after(problem)}));
  body.querySelector('#insight-export').onclick=safe(async()=>{const r=await fetch('/api/insights/export',{headers:{'X-Studio-Token':token}});if(!r.ok)throw Error('Export failed ('+r.status+')');const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download='luminaria-insights.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)});
  const remove=(scope,question,done)=>safe(async()=>{if(!confirm(question))return;try{const r=await api('/insights/delete','POST',{scope});toast(done(r));await after('')}catch(error){status.textContent=error.message;status.classList.add('warn-note')}});
  body.querySelector('#delete-local').onclick=remove('local','Delete all insights recorded on this PC? Chats are not affected. This cannot be undone.',r=>`Deleted ${r.local} recorded event${r.local===1?'':'s'}`);
  body.querySelector('#delete-synced').onclick=remove('synced','Delete the synced daily totals for your whole account, from every device? Sync is turned off. Insights on this PC stay.',r=>`Deleted ${r.synced} synced day${r.synced===1?'':'s'}`);
 }
 window.renderInsights=render;
})();
