(()=>{
 const queues=new Map(),sending=new Set(),voiceTurns=new Set();let serial=0;
 const host=document.createElement('div');host.id='queued-messages';host.setAttribute('aria-label','Unsent messages');document.querySelector('.composer-area').prepend(host);
 function draw(){host.innerHTML=(queues.get(chat)||[]).map(m=>`<div class="queued-chip"><span>${m.error?'Not sent · '+esc(m.error):'Queued'} · ${esc(m.text.slice(0,100)||'Attachments')}</span>${m.error?`<button class="text-button" data-retry-queued="${m.id}">Retry</button>`:''}${!m.error&&!m.sending&&active()&&m.text&&!m.attachments?.length&&!m.plan_only&&!m.plan_run?`<button class="text-button" data-steer-queued="${m.id}" title="Luminaria reads it before its next step, without stopping the task">Send now</button>`:''}<button class="icon-btn" data-cancel-queued="${m.id}" ${m.sending?'disabled':''} aria-label="Cancel queued message">${icon('close')}</button></div>`).join('');host.querySelectorAll('[data-cancel-queued]').forEach(b=>b.onclick=()=>{const queue=queues.get(chat)||[],index=queue.findIndex(m=>m.id===+b.dataset.cancelQueued);if(index>=0&&!queue[index].sending)queue.splice(index,1);draw()});host.querySelectorAll('[data-steer-queued]').forEach(b=>b.onclick=async()=>{
  const chosen=chat,queue=queues.get(chosen)||[],message=queue.find(m=>m.id===+b.dataset.steerQueued);
  if(!message||message.sending||sending.has(chosen))return;
  message.sending=true;sending.add(chosen);draw();
  try{
   await api('/chats/'+chosen+'/steer','POST',{text:message.text});
   const index=queue.findIndex(m=>m.id===message.id);
   if(index>=0)queue.splice(index,1);
   toast('Sent. It will read this before its next step.');
  }catch(e){message.error=e.message;toast(e.message,true)}
  finally{delete message.sending;sending.delete(chosen);draw();drain(chosen)}
 });host.querySelectorAll('[data-retry-queued]').forEach(b=>b.onclick=()=>{const m=(queues.get(chat)||[]).find(m=>m.id===+b.dataset.retryQueued);if(m)delete m.error;drain()})}
 async function drain(chosen=chat){if(!chosen||voiceTurns.has(chosen)||(chosen===chat&&active())||sending.has(chosen))return;const queue=queues.get(chosen)||[],message=queue[0];if(!message||message.error)return;sending.add(chosen);let sent=false;try{if(chosen!==chat){const observed=await api('/state?chat='+encodeURIComponent(chosen));if(observed.run&&!observed.run.finished)return}message.sending=true;draw();await api('/chats/'+chosen+'/run','POST',{text:message.text,attachments:message.attachments,reasoning:message.reasoning,plan_only:Boolean(message.plan_only),plan_run:Boolean(message.plan_run),execution_mode:message.execution_mode});queue.shift();sent=true;if(chosen===chat)await refresh()}catch(e){message.error=e.message;if(chosen===chat)toast('Queued message was not sent. Retry or cancel it.',true)}finally{delete message.sending;sending.delete(chosen);draw();if(sent&&queue.length)setTimeout(()=>drain(chosen),0)}}

 window.luminariaQueue={enqueue(id,message){const queue=queues.get(id)||[];if(queue.length>=10)throw Error('At most ten unsent messages per chat');queue.push({...message,id:++serial});queues.set(id,queue);draw();drain()},sending:id=>sending.has(id)};
 window.addEventListener('studio-state',()=>{draw();drain()});
 window.addEventListener('studio-voice-turn',e=>{if(e.detail.pending)voiceTurns.add(e.detail.chat);else{voiceTurns.delete(e.detail.chat);drain(e.detail.chat)}});
 window.addEventListener('studio-work',e=>{if(['run.completed','run.failed','run.cancelled'].includes(e.detail?.type))drain(e.detail.chat)});
 window.addEventListener('beforeunload',e=>{if([...queues.values()].some(q=>q.length)){e.preventDefault();e.returnValue='Unsent queued messages remain.'}});
})();
