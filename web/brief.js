/* Working brief: a short, editable list the assistant sees on every turn of this chat. */
(()=>{
 const order=['goals','permissions','constraints','decisions','pending','references'];
 const hints={goals:'What this chat is for.',permissions:'What you allow. Only you can add these.',constraints:'Limits to respect.',decisions:'Choices already made.',pending:'Work still to do.',references:'Files, links and where things are kept.'};
 const button=document.createElement('button');button.type='button';button.className='text-button';button.id='open-brief';button.title='The working brief is sent to the assistant on every turn and is never summarized away.';
 button.innerHTML='<span data-icon="list-tree"></span><span id="brief-label">Brief</span>';
 const place=()=>{const compact=$('#compact');if(compact&&!button.isConnected){compact.before(button);fillIcons(button)}};
 window.addEventListener('studio-state',()=>{place();const b=state.brief;$('#brief-label').textContent=b?.entries?`Brief (${b.pinned}${b.pinned!==b.entries?'/'+b.entries:''})`:'Brief';button.disabled=!chat});
 button.onclick=safe(()=>openBrief());
 async function openBrief(focus){
  if(!chat)return toast('Start a chat first.');
  const {brief,sections,max_text}=await api('/chats/'+chat+'/brief');
  const entries=brief.entries,by=s=>entries.filter(e=>e.section===s);
  showPanel('Working brief',`Sent to the assistant on every turn of this chat${brief.version?` · version ${brief.version}`:''}`,`<div class="brief-view">
   <p class="note">Pinned entries go into the assistant’s instructions unchanged, so they survive compaction. They take priority over older messages and the summary. Editing an entry replaces it; the old wording is kept below as history and is no longer sent. Don’t store passwords or keys here, only where they are kept.</p>
   ${order.map(s=>`<section class="brief-section" aria-labelledby="brief-${s}"><header><h4 id="brief-${s}">${esc(sections[s])}</h4><small>${esc(hints[s])}</small></header>
    ${by(s).map(e=>`<div class="brief-entry ${e.pinned?'':'unpinned'}" data-entry="${esc(e.id)}"><p>${esc(e.text)}</p><div class="brief-meta"><span>${e.source==='assistant'?'Proposed by the assistant':'Written by you'}${e.pinned?'':' · not sent'}</span><span class="brief-actions"><button class="text-button" data-edit="${esc(e.id)}">Edit</button><button class="text-button" data-pin="${esc(e.id)}" data-pinned="${e.pinned}">${e.pinned?'Unpin':'Pin'}</button><button class="text-button" data-remove="${esc(e.id)}">Remove</button></span></div></div>`).join('')||'<p class="small-note">Nothing yet.</p>'}
    <form class="brief-add" data-section="${s}"><label class="sr-only" for="brief-new-${s}">Add to ${esc(sections[s])}</label><input id="brief-new-${s}" name="text" maxlength="${max_text}" placeholder="Add to ${esc(sections[s].toLowerCase())}" autocomplete="off"><button class="btn" type="submit">Add</button></form></section>`).join('')}
   <p class="small-note" id="brief-status" role="status" aria-live="polite"></p>
   ${brief.superseded.length?`<details class="advanced-settings"><summary>Replaced and removed entries (${brief.superseded.length})</summary><ul class="brief-history">${brief.superseded.slice().reverse().map(e=>`<li><s>${esc(e.text)}</s><small>${esc(sections[e.section]||e.section)} · ${e.removed?'removed':'replaced'} by ${e.superseded_by==='assistant'?'the assistant':'you'} · ${esc(new Date(e.superseded_at*1000).toLocaleString())}</small></li>`).join('')}</ul></details>`:''}
  </div>`);
  const root=$('#panel-content'),status=root.querySelector('#brief-status');
  const change=async(payload,done)=>{try{await api('/chats/'+chat+'/brief','POST',payload);await openBrief(payload.section||null);if(done)toast(done)}catch(error){status.textContent=error.message;status.classList.add('warn-note')}};
  root.querySelectorAll('.brief-add').forEach(f=>f.onsubmit=safe(async e=>{e.preventDefault();const text=f.elements.text.value.trim();if(!text)return;await change({op:'add',section:f.dataset.section,text})}));
  root.querySelectorAll('[data-pin]').forEach(b=>b.onclick=safe(()=>change({op:'pin',id:b.dataset.pin,pinned:b.dataset.pinned!=='true'})));
  root.querySelectorAll('[data-remove]').forEach(b=>b.onclick=safe(async()=>{if(!confirm('Remove this entry from the working brief? The assistant stops seeing it from the next turn.'))return;await change({op:'remove',id:b.dataset.remove},'Entry removed')}));
  root.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{const row=root.querySelector(`[data-entry="${CSS.escape(b.dataset.edit)}"]`),entry=entries.find(e=>e.id===b.dataset.edit);
   row.innerHTML=`<form class="brief-add brief-edit"><label class="sr-only" for="edit-${esc(entry.id)}">Edit entry</label><input id="edit-${esc(entry.id)}" name="text" maxlength="${max_text}" value="${esc(entry.text)}"><button class="btn primary" type="submit">Save</button><button class="btn" type="button" data-cancel>Cancel</button></form>`;
   const form=row.querySelector('form'),input=form.elements.text;input.focus();input.setSelectionRange(input.value.length,input.value.length);
   form.querySelector('[data-cancel]').onclick=()=>openBrief();
   form.onsubmit=safe(async e=>{e.preventDefault();await change({op:'edit',id:entry.id,text:input.value.trim()},'Entry replaced')})});
  if(focus)root.querySelector('#brief-new-'+focus)?.focus();
 }
 window.openBrief=openBrief;
})();
