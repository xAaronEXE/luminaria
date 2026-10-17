(()=>{
 const launch=document.createElement('button');launch.id='task-overview';launch.className='btn';launch.innerHTML=icon('brain')+'<span>Task overview</span>';launch.setAttribute('aria-expanded','false');document.querySelector('.top-actions').prepend(launch);
 const surface=document.createElement('section');surface.id='spatial-workspace';surface.hidden=true;surface.setAttribute('aria-label','Task overview');surface.innerHTML=`<div class="spatial-controls"><button class="btn" id="spatial-return">${icon('arrow-right')}Return to conversation</button><label><input type="checkbox" id="spatial-follow" checked> Follow current activity</label><button class="btn" id="spatial-focus">Focus selection</button><button class="btn" id="spatial-outline-toggle" aria-pressed="false">Activity outline</button><button class="btn" id="spatial-retry">Refresh history</button></div><div id="spatial-region-labels" aria-hidden="true"></div><div id="spatial-canvas-target" tabindex="0" role="group" aria-label="Neural workspace. Arrow keys select recorded steps, Enter inspects, Escape returns."></div><div class="spatial-summary" id="spatial-summary" role="status"></div><div class="spatial-outline" id="spatial-outline" hidden></div><aside id="spatial-detail" aria-label="Selected activity" hidden></aside>`;document.body.append(surface);
 function layout(){const main=document.querySelector('.main').getBoundingClientRect(),top=document.querySelector('.topbar').getBoundingClientRect().bottom,bottom=document.querySelector('.composer-area').getBoundingClientRect().top;surface.style.left=Math.max(0,main.x)+'px';surface.style.width=main.width+'px';surface.style.top=top+'px';surface.style.bottom=Math.max(0,innerHeight-bottom)+'px'}
 const layoutObserver=new ResizeObserver(layout);layoutObserver.observe(document.querySelector('.main'));layoutObserver.observe(document.querySelector('.composer-area'));window.addEventListener('resize',layout);layout();
 let scene={nodes:[],edges:[],all:new Map()},selection=null,request=0,previousFocus=null,outline=false;
 const $s=id=>surface.querySelector('#'+id);
 const control=detail=>window.dispatchEvent(new CustomEvent('studio-spatial-control',{detail}));
 function open(){previousFocus=document.activeElement;surface.hidden=false;document.body.classList.add('task-overview');launch.setAttribute('aria-expanded','true');window.luminariaWork.recover();$s('spatial-canvas-target').focus();draw()}
 function close(){surface.hidden=true;document.body.classList.remove('task-overview');launch.setAttribute('aria-expanded','false');request++;(previousFocus?.isConnected?previousFocus:launch).focus()}
 launch.onclick=open;$s('spatial-return').onclick=close;
 $s('spatial-follow').onchange=e=>control({type:'follow',value:e.target.checked});
 $s('spatial-focus').onclick=()=>{if(selection){$s('spatial-follow').checked=false;control({type:'focus',id:selection})}};
 $s('spatial-retry').onclick=()=>window.luminariaWork.recover();
 $s('spatial-outline-toggle').onclick=()=>{outline=!outline;draw()};
 function draw(){
  const fallback=window.luminariaRenderStats?.mode==='fallback';$s('spatial-outline').hidden=!(outline||fallback);$s('spatial-outline-toggle').setAttribute('aria-pressed',String(outline||fallback));
  $s('spatial-summary').textContent=scene.error||`${scene.nodes.length} recorded nodes${scene.omitted?' · '+scene.omitted+' older nodes outside this view':''}. ${fallback?'3D unavailable. Use the activity outline.':'Select a node or use arrow keys to inspect.'}`;
  $s('spatial-outline').innerHTML=scene.nodes.length?`<ul>${scene.nodes.map(n=>`<li><button data-node="${esc(n.id)}" aria-pressed="${n.id===selection}"><strong>${esc(n.label)}</strong><span>${esc(n.status)} · ${esc(n.region)}${n.source?' · model-provided':''}</span></button></li>`).join('')}</ul>`:'<p>No recorded work in this chat yet. Start a task to create an execution trace.</p>';
  surface.querySelectorAll('[data-node]').forEach(b=>b.onclick=()=>inspect(b.dataset.node));
 }
 function showActivity(action){if(!action)return;tab='activity';if(typeof activityScope!=='undefined')activityScope='chat';document.body.classList.remove('inspector-collapsed');document.body.classList.add('inspector-open');$$('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab==='activity')));renderInspector();const row=$$('#inspector-content [data-action]').find(n=>n.dataset.action===action);if(row){row.classList.add('spatial-selected');row.scrollIntoView({block:'nearest',behavior:'auto'})}}
 async function inspect(id){
  const node=scene.all.get(id);if(!node)return;if(!scene.nodes.some(n=>n.id===id))window.luminariaWork.expand(node.run);selection=id;const ticket=++request;window.luminariaWork.select(id);draw();
  const detail=$s('spatial-detail');detail.hidden=false;detail.innerHTML=`<div class="spatial-detail-heading"><h3>${esc(node.label)}</h3><button class="icon-btn" id="close-spatial-detail" aria-label="Close activity details">${icon('close')}</button></div><p>${esc(node.status)} · ${esc(node.region)}${node.source?' · model-provided':''}</p><div id="spatial-evidence"></div>`;$s('close-spatial-detail').onclick=()=>{detail.hidden=true;request++};
  const out=$s('spatial-evidence');
  if(node.kind==='cluster'){out.innerHTML=`<p>${node.count} recorded nodes in this earlier run.</p><button class="btn" id="expand-spatial-run">Expand this run</button>`;$s('expand-spatial-run').onclick=()=>window.luminariaWork.expand(node.run);return}
  if(node.kind==='step'){out.innerHTML='<p>This step and its status were supplied by the model. Executed tool nodes carry separate evidence.</p>'}
  try{
   const data=await api('/state?chat='+encodeURIComponent(scene.chat));if(ticket!==request||scene.chat!==data.chat)return;
   if(node.evidence?.action){
    const a=data.actions.find(a=>a.id===node.evidence.action);if(a){out.innerHTML+=`<h4>Tool · ${esc(a.name)}</h4><p>${esc(a.status)} · approval tier ${esc(a.tier)}</p><h4>Arguments</h4><pre>${esc(JSON.stringify(a.args,null,2))}</pre><h4>Output</h4><pre>${esc(a.result?.text||'No result recorded yet.')}</pre><div class="form-actions"><button class="btn" id="spatial-show-activity">Show in Activity</button>${a.result?'<button class="btn" id="spatial-download-output">Download full output</button>':''}</div>`;$s('spatial-show-activity').onclick=()=>{showActivity(a.id);close()};if($s('spatial-download-output'))$s('spatial-download-output').onclick=safe(()=>download('/actions/'+encodeURIComponent(a.id)+'/output',a.id+'.json'))}
   }
   const message=data.messages.find(m=>m.id===node.evidence?.message);
   if(message){out.innerHTML+=`<h4>Recorded model response</h4><pre>${esc(typeof message.content==='string'?message.content:JSON.stringify(message.content))}</pre>${message.reasoning?`<h4>Reasoning · model-provided</h4><pre>${esc(message.reasoning)}</pre>`:''}`}
   if(node.reasoning&&!message&&data.run?.id===node.run&&data.run.reasoning_text)out.innerHTML+=`<h4>Reasoning · model-provided</h4><pre>${esc(data.run.reasoning_text)}</pre>`;
   if(node.evidence?.summary){const summary=await api('/state?chat='+encodeURIComponent(scene.chat));if(ticket!==request)return;if(summary.summary?.id===node.evidence.summary)out.innerHTML+=`<h4>Compaction summary</h4><pre>${esc(summary.summary.content)}</pre>`;else out.innerHTML+='<p>Historical compaction reference retained; summary text is not available through this view.</p>'}
   if(node.error)out.innerHTML+=`<h4>Error</h4><pre>${esc(node.error)}</pre>`;
   if(!out.textContent.trim())out.textContent='This node records a lifecycle event. No additional output is attached.';
  }catch(e){if(ticket===request)out.textContent='Could not load evidence: '+e.message}
 }
 $s('spatial-canvas-target').onpointermove=e=>{const id=window.luminariaSpatial?.hit(e.clientX,e.clientY),n=scene.all.get(id);e.currentTarget.title=n?n.label+' � '+n.status:''};
 $s('spatial-canvas-target').onclick=e=>{const id=window.luminariaSpatial?.hit(e.clientX,e.clientY);if(id)inspect(id)};
 surface.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();return}if(e.target!==$s('spatial-canvas-target'))return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const list=scene.nodes,i=list.findIndex(n=>n.id===selection),direction=['ArrowLeft','ArrowUp'].includes(e.key)?-1:1;if(list.length){selection=list[(i+direction+list.length)%list.length].id;window.luminariaWork.select(selection);draw();$s('spatial-summary').textContent=list.find(n=>n.id===selection).label+' · '+list.find(n=>n.id===selection).status}}if(e.key==='Enter'&&selection){e.preventDefault();inspect(selection)}});
 document.addEventListener('click',e=>{const b=e.target.closest('[data-show-work]');if(!b)return;const node=[...scene.all.values()].find(n=>n.evidence?.action===b.dataset.showWork);if(node){open();inspect(node.id)}else{toast('Loading recorded work…');window.luminariaWork.recover()}});
 window.addEventListener('studio-scene',e=>{const changed=scene.chat!==e.detail.chat;scene=e.detail;if(changed){selection=null;$s('spatial-detail').hidden=true;request++}draw()});
 window.addEventListener('studio-spatial-fallback',draw);
 const regions=setInterval(()=>{if(surface.hidden||document.hidden)return;const box=surface.getBoundingClientRect();$s('spatial-region-labels').innerHTML=(window.luminariaSpatial?.regions()||[]).filter(p=>p.x>box.left+20&&p.x<box.right-70&&p.y>box.top+75&&p.y<box.bottom-45).map(p=>`<span style="left:${p.x-box.left}px;top:${p.y-box.top-25}px">${esc(p.label)}</span>`).join('')},200);window.addEventListener('pagehide',()=>clearInterval(regions));
})();
