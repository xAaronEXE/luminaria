/* Library presentation: preserve API authorization and existing setup handlers. */
(()=>{
 const oldOpen=openPanel;
 openPanel=async function(name){
  if(name==='memory')return memoryLibrary();
  const result=await oldOpen(name);decorate();return result;
 };
 async function memoryLibrary(){
  showPanel('Memory','Keep useful facts and preferences close at hand.',`<div class="library-toolbar"><input id="memory-search" class="filter-input" type="search" placeholder="Search saved memories…" aria-label="Search saved memories"><button class="btn primary" id="new-memory">Add memory</button></div><p class="small-note">Saved on this PC for use across tasks. Review what is remembered and remove anything you no longer need.</p><form id="memory-form" class="memory-editor" hidden><h3>Add a memory</h3>${field('Give it a short title','title','','text',true)}<label class="field">What should Luminaria remember?<textarea name="content" required placeholder="A preference, project decision or useful fact…"></textarea></label><div class="form-actions"><button class="btn" type="button" id="cancel-memory">Cancel</button><button class="btn primary" type="submit">Save memory</button></div><p role="status" id="memory-status"></p></form><div id="memory-list"></div>`);
  const form=$('#memory-form');$('#new-memory').onclick=()=>{form.hidden=false;form.elements.title.focus()};$('#cancel-memory').onclick=()=>{form.hidden=true;form.reset()};
  const draw=()=>{const q=$('#memory-search').value.toLowerCase(),items=(state.memories||[]).filter(m=>(m.title+' '+m.content).toLowerCase().includes(q));$('#memory-list').innerHTML=items.length?`<p class="library-count">${items.length} saved memories</p>`+items.map(m=>`<article class="memory-item"><h3>${esc(m.title)}</h3><p>${esc(m.content)}</p><footer><span>${esc(m.source)} · ${new Date(m.updated*1000).toLocaleDateString()}</span><button class="text-button" data-memory-delete="${esc(String(m.id))}">Delete</button></footer></article>`).join(''):`<div class="library-empty"><h3>${q?'No matching memories':'A place for the details that matter'}</h3><p>${q?'Try another title or phrase.':'Add your first memory above, or ask Luminaria to remember a detail during a conversation.'}</p></div>`;
   $$('[data-memory-delete]').forEach(b=>b.onclick=safe(async()=>{if(!confirm('Delete this memory? Its original conversation stays saved.'))return;await api('/memories/'+encodeURIComponent(b.dataset.memoryDelete),'DELETE');await refresh();draw()}));
  };$('#memory-search').oninput=draw;draw();
  form.onsubmit=safe(async e=>{e.preventDefault();const b=form.querySelector('[type=submit]');b.disabled=true;try{await api('/memories','POST',Object.fromEntries(new FormData(form)));await refresh();form.reset();form.hidden=true;draw();toast('Memory saved')}catch(error){$('#memory-status').textContent=error.message}finally{b.disabled=false}});
 }
 function decorate(){
  const panel=$('#panel-content');if(!panel)return;
  const title=$('#panel-title')?.textContent||'';
  $('.sheet').classList.toggle('library-sheet',['Memory','Tools','Integrations','Skills library'].includes(title));
  panel.querySelectorAll('.skill-row:not([data-library-polished])').forEach(row=>{
   row.dataset.libraryPolished='true';const desc=row.querySelector('.skill-description');if(desc){const full=desc.textContent;desc.title=full;desc.textContent=full.split(/\.\s/)[0].replace(/\.$/,'')+'.'}
   const action=row.querySelector('[data-use-skill]');if(action){action.classList.remove('text-button');action.classList.add('btn');action.textContent='Use skill'}
  });
  const skillForm=panel.querySelector('#skill-form');if(skillForm&&!skillForm.closest('details')){const heading=skillForm.previousElementSibling?.previousElementSibling,note=skillForm.previousElementSibling;const details=document.createElement('details');details.className='advanced-settings';details.innerHTML='<summary>Import your own skill</summary>';skillForm.before(details);if(heading?.matches('h3'))heading.remove();if(note?.matches('p'))details.append(note);details.append(skillForm)}
  panel.querySelectorAll('.catalog-row:not([data-library-polished])').forEach(row=>{row.dataset.libraryPolished='true';const summary=row.querySelector('summary'),text=summary.querySelector('strong');if(text)text.textContent=text.textContent.replace(/\b\w/g,c=>c.toUpperCase());const purpose=summary.querySelector('.tool-purpose');if(purpose){purpose.title=purpose.textContent;purpose.textContent=purpose.textContent.split(/\.\s/)[0]+'.'}const pre=row.querySelector('pre');if(pre){const details=document.createElement('details');details.className='tool-technical';details.innerHTML='<summary>Technical input schema</summary>';pre.before(details);details.append(pre)}const heading=row.querySelector('h4');if(heading)heading.textContent='How this tool works';});
  panel.querySelectorAll('.integration-card:not([data-guided])').forEach(card=>{
   card.dataset.guided='true';const body=card.querySelector('.integration-body'),guide=body?.querySelector('.connection-guide'),form=body?.querySelector('form');if(!body||!guide||!form)return;
   const steps=[...guide.children],redirect=body.querySelector('.field:not(form .field)');
   const toolbar=document.createElement('div');toolbar.className='connection-steps';toolbar.innerHTML='<span role="status"></span><div><button type="button" class="btn" data-connection-back>Back</button><button type="button" class="btn primary" data-connection-next>Continue</button></div>';body.append(toolbar);
   let step=0;const prepared=!form.querySelector('[name=client_id],[name=token]');
   function draw(){steps.forEach((li,i)=>li.hidden=i!==step);form.hidden=step!==1;if(redirect)redirect.hidden=step!==0;toolbar.querySelector('span').textContent=['1 · Prepare access','2 · Connect securely','3 · Verify connection'][step];toolbar.querySelector('[data-connection-back]').hidden=step===0;toolbar.querySelector('[data-connection-next]').hidden=step>=1;}
   toolbar.querySelector('[data-connection-next]').onclick=()=>{step=1;draw();form.querySelector('input:not([readonly]),button')?.focus()};toolbar.querySelector('[data-connection-back]').onclick=()=>{step=0;draw()};
   if(prepared)step=1;draw();
   const first=steps[0];if(first){const note=document.createElement('p');note.className='small-note';note.textContent=prepared?'You can continue directly in your browser.':'This service requires a token or an OAuth app configured by you or your administrator. Luminaria cannot skip this provider requirement. Prepare it once; saved credentials can be reused.';first.prepend(note)}
  });
  const mcp=panel.querySelector('#mcp-form');if(mcp&&!mcp.closest('details')){const d=document.createElement('details');d.className='advanced-settings';d.innerHTML='<summary>Advanced · Add a custom MCP connector</summary>';const note=mcp.previousElementSibling,heading=note?.previousElementSibling;mcp.before(d);if(heading?.matches('h3'))heading.remove();if(note?.matches('p'))d.append(note);d.append(mcp)}
 }
 let decorationFrame=0;new MutationObserver(()=>{if(decorationFrame)return;decorationFrame=requestAnimationFrame(()=>{decorationFrame=0;decorate()})}).observe($('#panel-content'),{childList:true,subtree:true});
})();
