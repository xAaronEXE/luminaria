/* Explicit opt-in microphone, local recognition and synthesis, cancellable playback. */
(()=>{
 let mode='conversation',starting=false;
 let enabled=false,stream,context,node,source,sink,audio,micAnalyser,fetchController,epoch=0,lastAudioFrame=0;
 let frames=[],pre=[],talking=false,loud=0,quiet=0,length=0,transcribing=false;
 let voiceChat='',seen=new Set(),queue=[],speaking=false,interrupting=Promise.resolve();
 const voiceTurn=(pending,target=voiceChat)=>window.dispatchEvent(new CustomEvent('studio-voice-turn',{detail:{chat:target,pending}}));
 const voiceIcon='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4m4-8v12m4-15v18m4-15v12m4-8v4"/></svg>';
 const button=document.createElement('button');button.type='button';button.className='voice-toggle';button.id='voice-toggle';
 button.innerHTML=voiceIcon;button.setAttribute('aria-pressed','false');button.title='Start a local voice conversation';
 button.setAttribute('aria-label','Voice conversation');document.getElementById('send').before(button);
 const dictation=document.createElement('button');dictation.type='button';dictation.id='dictation';dictation.className='voice-toggle';dictation.setAttribute('aria-label','Dictate a message');dictation.title='Dictate a message';dictation.innerHTML='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0zM5 11v1a7 7 0 0 0 14 0v-1M12 19v3m-4 0h8"/></svg>';button.before(dictation);
 const bar=document.createElement('div');bar.className='voice-bar';bar.hidden=true;
 bar.innerHTML='<span class="voice-light"></span><span id="voice-status" role="status">Microphone off</span><button type="button" id="voice-interrupt">Interrupt</button><button type="button" id="voice-end">End voice</button>';
 document.querySelector('.composer-area').prepend(bar);
 const label=text=>{document.getElementById('voice-status').textContent=text;window.dispatchEvent(new CustomEvent('studio-voice-state',{detail:text}));};
 function audioFrame(analyser,source,rms){const bins=new Uint8Array(analyser.frequencyBinCount);analyser.getByteFrequencyData(bins);const hz=context.sampleRate/analyser.fftSize;const average=(lo,hi)=>{let sum=0,n=0;for(let i=Math.max(1,Math.floor(lo/hz));i<Math.min(bins.length,Math.ceil(hi/hz));i++){sum+=bins[i]/255;n++}return n?sum/n:0};const samples=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(samples);let power=0;for(const value of samples)power+=value*value;return {source,rms:rms??Math.min(1,Math.sqrt(power/samples.length)*8),bass:average(60,300),mid:average(300,2000),high:average(2000,7000)}}
 const clearSpeech=()=>{epoch++;queue=[];fetchController?.abort();if(audio){audio.pause();audio.src='';audio=null}speaking=false};
 function resetCapture(){frames=[];pre=[];talking=false;loud=quiet=length=0}
 function end(){voiceTurn(false);if(enabled&&mode==='conversation'&&chat===voiceChat&&active())stop().catch(e=>toast(e.message,true));enabled=false;delete document.body.dataset.voice;document.body.classList.remove('voice-review');label('Microphone off');window.dispatchEvent(new CustomEvent('studio-audio',{detail:0}));clearSpeech();stream?.getTracks().forEach(t=>t.stop());node?.disconnect();source?.disconnect();sink?.disconnect();context?.close();context=null;micAnalyser=null;resetCapture();bar.hidden=true;button.innerHTML=voiceIcon;button.setAttribute('aria-pressed','false');dictation.setAttribute('aria-pressed','false')}
 async function interrupt(){clearSpeech();if(enabled)label('Listening · reply interrupted');if(active()&&chat===voiceChat)await stop()}
 async function begin(nextMode='conversation'){
  if(starting)return;starting=true;button.disabled=dictation.disabled=true;
  try{await startCapture(nextMode)}finally{starting=false;button.disabled=dictation.disabled=false}
 }
 async function startCapture(nextMode){
  mode=nextMode;
  const readiness=await api('/voice/status');if(!readiness.ready){
   window.studioSettingsCategory='Voice';await openPanel('settings');window.studioSettingsCategory=null;toast('Install the local voice models in Voice settings first.');return;
  }
  stream=await navigator.mediaDevices.getUserMedia({audio:{...(studioPrefs.microphone?{deviceId:{exact:studioPrefs.microphone}}:{}),echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
  try{
   await ensureChat();await refresh();voiceChat=chat;seen=new Set((state.messages||[]).map(m=>m.id));
   context=new AudioContext({sampleRate:16000});await context.audioWorklet.addModule('/voice-capture.js');await context.resume();
   source=context.createMediaStreamSource(stream);node=new AudioWorkletNode(context,'voice-capture');sink=context.createGain();sink.gain.value=0;
   micAnalyser=context.createAnalyser();micAnalyser.fftSize=1024;source.connect(micAnalyser);source.connect(node);node.connect(sink);sink.connect(context.destination);node.port.onmessage=e=>capture(e.data);
   enabled=true;document.body.dataset.voice=mode;bar.hidden=false;button.innerHTML=voiceIcon;button.setAttribute('aria-pressed',String(mode==='conversation'));dictation.setAttribute('aria-pressed',String(mode==='dictation'));label('Listening · speak naturally');
   toast('Voice is local. Use headphones for the most reliable interruption.');
  }catch(e){end();throw e}
 }
 function capture(samples){
  if(!enabled||transcribing)return;
  const dt=samples.length/context.sampleRate;let power=0;for(const v of samples)power+=v*v;
  const level=Math.sqrt(power/samples.length);if(performance.now()-lastAudioFrame>30){lastAudioFrame=performance.now();window.dispatchEvent(new CustomEvent('studio-audio',{detail:audioFrame(micAnalyser,'microphone',Math.min(1,level*8))}));}const voiced=level>(studioPrefs.voice_threshold||.022);
  if(!talking){pre.push(samples);while(pre.length*dt>.32)pre.shift();loud=voiced?loud+dt:0;
   if(loud<.18)return;talking=true;frames=pre.slice();pre=[];length=frames.length*dt;
   if(mode==='conversation')voiceTurn(true);interrupting=(mode==='conversation'&&studioPrefs.interruptible?interrupt():Promise.resolve()).catch(e=>{toast(e.message,true)});label('Listening…');
  }else{frames.push(samples);length+=dt}
  quiet=voiced?0:quiet+dt;
  if(quiet>(studioPrefs.voice_silence||.85)||length>=30){const captured=frames;resetCapture();transcribe(captured).catch(e=>{toast(e.message,true);if(enabled)label('Listening · last turn failed')})}
 }
 function wav(chunks,rate){
  const n=chunks.reduce((s,c)=>s+c.length,0),joined=new Float32Array(n);let pos=0;for(const c of chunks){joined.set(c,pos);pos+=c.length}
  const count=Math.floor(n*16000/rate),buffer=new ArrayBuffer(44+count*2),d=new DataView(buffer);
  const str=(at,s)=>{for(let i=0;i<s.length;i++)d.setUint8(at+i,s.charCodeAt(i))};
  str(0,'RIFF');d.setUint32(4,36+count*2,true);str(8,'WAVE');str(12,'fmt ');d.setUint32(16,16,true);d.setUint16(20,1,true);d.setUint16(22,1,true);d.setUint32(24,16000,true);d.setUint32(28,32000,true);d.setUint16(32,2,true);d.setUint16(34,16,true);str(36,'data');d.setUint32(40,count*2,true);
  for(let i=0;i<count;i++)d.setInt16(44+i*2,Math.max(-1,Math.min(1,joined[Math.floor(i*rate/16000)]))*32767,true);
  return buffer;
 }
 async function transcribe(chunks){
  transcribing=true;window.dispatchEvent(new CustomEvent('studio-audio',{detail:{source:'microphone',rms:0,bass:0,mid:0,high:0}}));const current=epoch,target=voiceChat,rate=context.sampleRate;label('Transcribing locally…');
  try{
   await interrupting;
   const r=await fetch('/api/voice/transcribe',{method:'POST',headers:{'X-Studio-Token':token,'Content-Type':'audio/wav'},body:wav(chunks,rate)});
   const result=await r.json();if(!r.ok)throw Error(result.error||result.detail||'Speech recognition failed');
   if(!enabled||chat!==target||epoch!==current)return;
   if(!result.text){label('Listening · no speech recognized');return}
   if(mode==='dictation'){$('#prompt').value+=($('#prompt').value?' ':'')+result.text;$('#prompt').dispatchEvent(new Event('input'));end();$('#prompt').focus();return}
   // A voice turn uses exactly the normal agent route; it cannot grant approvals.
   await api('/chats/'+target+'/run','POST',{text:result.text,voice:true,reasoning:$('#reasoning').checked});await refresh();label('Thinking · you can interrupt');
  }finally{transcribing=false;voiceTurn(false,target)}
 }
 const spokenText=text=>text.replace(/```[\s\S]*?```/g,' Code is shown in the chat. ').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/https?:\/\/\S+/g,'link in the chat').replace(/[*#`_>|]/g,'').trim();
 async function playQueue(){
  if(speaking||!enabled||!queue.length)return;speaking=true;const current=epoch;
  try{while(queue.length&&enabled&&current===epoch){
   fetchController=new AbortController();label('Preparing speech locally…');
   const r=await fetch('/api/voice/speak',{method:'POST',headers:{'X-Studio-Token':token,'Content-Type':'application/json'},body:JSON.stringify({text:queue.shift(),voice_id:studioPrefs.voice_id||'lessac'}),signal:fetchController.signal});
   if(!r.ok)throw Error('Local speech synthesis failed');const blob=await r.blob();if(!enabled||current!==epoch)break;
   const url=URL.createObjectURL(blob),player=new Audio(url);player.playbackRate=studioPrefs.voice_rate||1;audio=player;
   const analyser=context.createAnalyser();analyser.fftSize=1024;const media=context.createMediaElementSource(player);media.connect(analyser);analyser.connect(context.destination);const bins=new Uint8Array(analyser.frequencyBinCount);const pulse=()=>{if(audio!==player||player.paused)return;analyser.getByteFrequencyData(bins);window.dispatchEvent(new CustomEvent('studio-audio',{detail:audioFrame(analyser,'output')}));requestAnimationFrame(pulse)};player.addEventListener('playing',()=>{if(current!==epoch)return;pulse();label('Speaking · talk to interrupt')});
   try{await new Promise((resolve,reject)=>{player.onended=resolve;player.onerror=()=>current!==epoch?resolve():reject(Error('Audio playback failed'));player.onpause=resolve;player.play().catch(reject)})}finally{media.disconnect();analyser.disconnect();window.dispatchEvent(new CustomEvent('studio-audio',{detail:{source:'output',rms:0,bass:0,mid:0,high:0}}));URL.revokeObjectURL(url)}
  }}catch(e){if(current===epoch&&e.name!=='AbortError')toast(e.message,true)}finally{if(current===epoch){speaking=false;audio=null;if(enabled)label('Listening · speak naturally')}}
 }
 window.addEventListener('studio-state',()=>{
  if(!enabled||mode==='dictation')return;if(state.run?.phase==='Error'){clearSpeech();label('Reply failed · see chat for details')}if(chat!==voiceChat){end();return}
  document.body.classList.toggle('voice-review',state.run?.phase==='Waiting for approval');if(state.run?.phase==='Waiting for approval'){label('Review the tool approval on screen');return}
  if(active()&&!speaking&&!talking&&!transcribing)label((state.run.phase||'Working')+' - you can interrupt');
  for(const m of state.messages||[]){
   if(seen.has(m.id))continue;seen.add(m.id);
   if(m.role!=='assistant'||m.tool_calls?.length||m.interrupted||!m.content)continue;
   const text=spokenText(typeof m.content==='string'?m.content:'');
   // Bounded chunks avoid a long synthesis request blocking interruption or the next reply.
   for(let i=0;i<text.length;i+=500){let part=text.slice(i,i+500);if(i+500<text.length){const cut=part.lastIndexOf(' ');if(cut>200){part=part.slice(0,cut);i-=500-cut}}if(part.trim())queue.push(part)}
  }
  playQueue();
 });
 button.onclick=safe(async()=>enabled?end():begin('conversation'));dictation.onclick=safe(async()=>enabled?end():begin('dictation'));document.getElementById('voice-end').onclick=end;
 document.getElementById('voice-interrupt').onclick=safe(interrupt);
 window.addEventListener('beforeunload',end);
})();

