/* Library presentation: preserve API authorization and existing setup handlers. */
(()=>{
 const oldOpen=openPanel;
 openPanel=async function(name){
  if(name==='memory')return memoryLibrary();
  const result=await oldOpen(name);decorate();return result;
 };
 let memoryGuard=null;
 async function memoryLibrary(){
  // Memory is two Markdown files, like CLAUDE.md: MEMORY.md about the user, LUMINARIA.md about the working folder.
  showPanel('Memory','What Luminaria remembers, in plain Markdown you can edit.',`<div class="memory-bar"><div class="segmented" role="tablist" aria-label="Memory file"><button type="button" role="tab" data-mem-tab="me" aria-selected="true">My memory</button><button type="button" role="tab" data-mem-tab="project" aria-selected="false">This project</button></div><div class="segmented" role="group" aria-label="View"><button type="button" data-mem-view="edit" aria-pressed="true">Edit</button><button type="button" data-mem-view="preview" aria-pressed="false">Preview</button></div></div>
   <p class="small-note" id="memory-about"></p>
   <div id="memory-body"><textarea id="memory-text" class="memory-text" spellcheck="true" aria-label="Memory file"></textarea><div id="memory-preview" class="memory-preview markdown" hidden></div></div>
   <div class="s-actions"><span class="save-state" id="memory-state" role="status"></span><button type="button" class="btn" id="memory-revert">Undo changes</button><button type="button" class="btn primary" id="memory-save">Save</button></div>`);
  const text=$('#memory-text'),preview=$('#memory-preview'),about=$('#memory-about'),stateEl=$('#memory-state');
  let tab='me',view='edit',data=await api('/memory'),saved={me:data.content,project:data.project.content||''},draft={...saved};
  const PROJECT_TEMPLATE='# Project notes\n\nWhat Luminaria should know about this folder. Like CLAUDE.md in a code repository.\n\n## What this is\n\n## How to work here\n\n## Decisions\n';
  const dirty=()=>draft.me!==saved.me||draft.project!==saved.project;
  const draw=()=>{
   $$('[data-mem-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.memTab===tab)));
   $$('[data-mem-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.memView===view)));
   const missing=tab==='project'&&!data.project.exists&&!draft.project;
   about.innerHTML=tab==='me'
    ?`Used in every task. Saved on this PC in <code>${esc(data.path)}</code>. Ask Luminaria to “remember” something and it adds a line under Notes.`
    :(data.project.path?`Loaded only when you work in this folder: <code>${esc(data.project.path)}</code>.`:'Choose a working folder in Settings to keep project notes.')+(missing?' This folder has no project notes yet.':'');
   text.value=draft[tab];text.placeholder=tab==='project'?'Click “Start project notes” or type here…':'';
   text.hidden=view!=='edit';preview.hidden=view!=='preview';
   if(view==='preview')preview.innerHTML=draft[tab].trim()?markdown(draft[tab]):'<p class="note">Nothing here yet.</p>';
   $('#memory-save').textContent=missing?'Start project notes':'Save';
   $('#memory-revert').hidden=draft[tab]===saved[tab];
   stateEl.textContent=draft[tab]!==saved[tab]?'Unsaved changes':'';
  };
  text.oninput=()=>{draft[tab]=text.value;draw()};
  $$('[data-mem-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.memTab;draw();if(view==='edit')text.focus()});
  $$('[data-mem-view]').forEach(b=>b.onclick=()=>{view=b.dataset.memView;draw()});
  $('#memory-revert').onclick=()=>{draft[tab]=saved[tab];draw()};
  $('#memory-save').onclick=safe(async()=>{
   if(tab==='project'&&!data.project.exists&&!draft.project){draft.project=PROJECT_TEMPLATE;view='edit';draw();text.focus();return}
   const b=$('#memory-save');b.disabled=true;
   try{
    if(tab==='me')await api('/memory','PUT',{content:draft.me});else await api('/memory/project','PUT',{content:draft.project});
    data=await api('/memory');saved={me:data.content,project:data.project.content||''};draft={...draft,[tab]:saved[tab]};
    draw();toast(tab==='me'?'Memory saved':'Project notes saved');await refresh();
   }catch(error){stateEl.textContent=error.message}finally{b.disabled=false}
  });
  text.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();$('#memory-save').click()}});
  // Don't lose edits when the panel is closed.
  const closer=$('#close-panel');
  if(closer){
   if(memoryGuard)closer.removeEventListener('click',memoryGuard,true);
   memoryGuard=e=>{if(text.isConnected&&dirty()&&!confirm('Close without saving your memory changes?')){e.preventDefault();e.stopImmediatePropagation()}};
   closer.addEventListener('click',memoryGuard,true);
  }
  draw();
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
