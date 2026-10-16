/* Local WebGL neural lattice -> toroidal voice core. Motion represents UI events, not hidden thoughts. */
(()=>{
 const canvas=document.createElement('canvas');canvas.id='ambient-field';canvas.setAttribute('aria-hidden','true');document.body.prepend(canvas);
 const status=document.createElement('div');status.className='entity-caption';status.innerHTML='<span>Voice conversation</span><strong>Listening</strong><small>Your voice stays on this PC</small>';document.body.append(status);
 const button=document.createElement('button');button.id='ambient-motion';button.className='text-button';document.querySelector('.sidebar-bottom').prepend(button);
 const gl=canvas.getContext('webgl',{alpha:true,antialias:true,powerPreference:'low-power'}),reduce=matchMedia('(prefers-reduced-motion: reduce)');
 if(!gl){canvas.remove();button.remove();document.body.classList.add('entity-fallback');window.addEventListener('studio-voice-state',e=>status.querySelector('strong').textContent=e.detail);return}
 let voice=0,targetVoice=0,t=0,last=0,dirty=true,paused=false,px=0,py=0,region=-1,pulse=0,phase='idle';
 let microphone={rms:0,bass:0,mid:0,high:0},output={rms:0,bass:0,mid:0,high:0};
 const envelope={rms:0,bass:0,mid:0,high:0};
 function shader(type,code){const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
 try{
 const program=gl.createProgram();
 gl.attachShader(program,shader(gl.VERTEX_SHADER,`
 precision mediump float;
 attribute vec3 brain;attribute vec3 torus;attribute float cluster;
 uniform float time,morph,aspect,amplitude,bass,mid,high,reduced,entityScale;uniform vec2 pointer,dock,center;
 varying float depth;varying float zone;varying float travel;
 void main(){
 vec3 b=brain; b.x+=.025*sin(b.y*11.+b.z*7.);b.z+=.02*cos(b.x*17.);
 vec3 v=torus;float a=atan(v.z,v.x);
 v.xz*=1.+bass*.22*(1.-reduced);v.y*=1.+high*.7*(1.-reduced);
 v+=normalize(v)*sin(a*7.+time*2.5)*mid*.09*(1.-reduced);
 vec3 p=mix(b,v,morph);
 float rotation=time*.07*(1.-reduced)+pointer.x*.12*(1.-reduced);
 p.xz=mat2(cos(rotation),-sin(rotation),sin(rotation),cos(rotation))*p.xz;
 float tilt=.28+pointer.y*.08*(1.-reduced);p.yz=mat2(cos(tilt),-sin(tilt),sin(tilt),cos(tilt))*p.yz;
 p*=mix(.18,entityScale,morph);p.z+=4.6;
 vec2 offset=mix(dock,center,morph);
 gl_Position=vec4(p.x*2.15/aspect+offset.x*p.z,p.y*2.15+offset.y*p.z,0.,p.z);
 depth=clamp(1.-(p.z-2.)/5.,.15,1.);zone=cluster;travel=brain.y*3.+brain.x*2.;
 gl_PointSize=mix(1.7,2.6,morph)+amplitude*2.*(1.-reduced);
 }`));
 gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`
 precision mediump float;uniform vec3 tint;uniform float points,time,region,pulse,morph,amplitude;
 varying float depth;varying float zone;varying float travel;
 void main(){float shape=1.;if(points>.5){float d=length(gl_PointCoord-vec2(.5));if(d>.5)discard;shape=1.-smoothstep(.12,.5,d);}
 float zoneActive=1.-step(.4,abs(zone-region));float packet=pow(max(0.,sin(travel-time*4.)),18.)*zoneActive*pulse;
 float alpha=depth*mix(.32,.72,morph)*(points>.5?.86:.24)+packet*.6+amplitude*.08;
 gl_FragColor=vec4(tint,alpha*shape);
 }`));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
 // Deterministic anatomical lobes and neighboring synapses, each with a stable torus destination.
 const nodes=[],links=[],rings=42,steps=60;
 for(let j=0;j<rings;j++)for(let i=0;i<steps;i++){
  const u=i/steps*Math.PI*2,v=(j+.5)/rings*Math.PI,side=Math.cos(u)<0?-1:1;
  const fold=1+.085*Math.sin(u*11+Math.sin(v*5))*Math.sin(v*9);
  const cleft=.07+.17*Math.pow(Math.abs(Math.cos(u)),.5);
  const b=[side*cleft+Math.sin(v)*Math.cos(u)*.82*fold,Math.cos(v)*.88,Math.sin(v)*Math.sin(u)*1.06*fold];
  const a=i/steps*Math.PI*2,c=j/rings*Math.PI*2,r=.98+.26*Math.cos(c);
  const tor=[r*Math.cos(a),.26*Math.sin(c),r*Math.sin(a)];
  const zone=b[1]>.35?0:b[0]<0?1:b[2]>0?2:3;
  nodes.push([...b,...tor,zone]);
 }
 for(let j=0;j<rings;j++)for(let i=0;i<steps;i++){const at=j*steps+i;links.push(...nodes[at],...nodes[j*steps+(i+1)%steps]);if(j<rings-1&&i%3===0)links.push(...nodes[at],...nodes[at+steps]);}
 const buffer=data=>{const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);return b};
 const dots=buffer(nodes.flat()),lines=buffer(links),attrs=['brain','torus','cluster'].map(n=>gl.getAttribLocation(program,n));attrs.forEach(a=>gl.enableVertexAttribArray(a));
 const uniforms=Object.fromEntries(['time','morph','aspect','amplitude','bass','mid','high','reduced','pointer','tint','points','region','pulse','dock','center','entityScale'].map(n=>[n,gl.getUniformLocation(program,n)]));
 gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
 const label=()=>{button.textContent=paused?'Resume background motion':'Pause background motion';button.setAttribute('aria-pressed',String(paused))};
 button.onclick=safe(async()=>{await savePrefs({motion:!studioPrefs.motion})});
 window.addEventListener('studio-preferences',e=>{paused=reduce.matches||!e.detail.motion;dirty=true;label()});
 window.addEventListener('studio-audio',e=>{const d=e.detail;if(d&&typeof d==='object'){if(d.source==='output')output=d;else microphone=d}else{microphone={rms:Number(d)||0,bass:0,mid:0,high:0};output={rms:0,bass:0,mid:0,high:0}}dirty=true});
 window.addEventListener('studio-voice-state',e=>{phase=e.detail;targetVoice=Number(document.body.dataset.voice==='conversation'&&!document.body.classList.contains('voice-review'));status.querySelector('strong').textContent=phase;dirty=true});
 window.addEventListener('studio-state',()=>{const r=state.run,action=(state.actions||[]).at(-1);region=-1;pulse=0;if(r&&!r.finished){phase=r.phase||'Working';region=/think|reason/i.test(phase)?0:/compact/i.test(phase)?1:3;pulse=.7;if(action&&['running','ready','pending'].includes(action.status)){region=/memory|history|remember/.test(action.name)?1:2;pulse=1}}dirty=true});
 window.addEventListener('mint-token',()=>{region=3;pulse=1;dirty=true});
 window.addEventListener('pointermove',e=>{px=e.clientX/innerWidth-.5;py=.5-e.clientY/innerHeight});
 let stage;
 function layoutStage(){const main=document.querySelector('.main').getBoundingClientRect(),top=document.querySelector('.topbar').getBoundingClientRect().bottom,bottom=document.querySelector('.composer-area').getBoundingClientRect().top;stage={x:main.x,width:main.width,top,height:Math.max(120,bottom-top)};status.style.left=(stage.x+stage.width/2)+'px';status.style.top=(stage.top+stage.height*.76)+'px';status.style.maxWidth=Math.max(240,stage.width-48)+'px';document.body.classList.toggle('voice-compact',stage.height<300);dirty=true}
 new ResizeObserver(layoutStage).observe(document.querySelector('.main'));new ResizeObserver(layoutStage).observe(document.querySelector('.composer-area'));layoutStage();
 window.addEventListener('resize',layoutStage);reduce.addEventListener('change',()=>{paused=reduce.matches||!studioPrefs.motion;dirty=true;label()});
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();canvas.hidden=true;document.body.classList.add('entity-fallback')});
 function frame(now){requestAnimationFrame(frame);targetVoice=Number(document.body.dataset.voice==='conversation'&&!document.body.classList.contains('voice-review'));if(document.hidden)return;const interval=targetVoice?1000/60:1000/30;if(now-last<interval||paused&&!dirty&&Math.abs(voice-targetVoice)<.001)return;const dt=Math.min((now-last)/1000,.05);last=now;dirty=false;if(!paused)t+=dt;voice=paused?targetVoice:voice+(targetVoice-voice)*(1-Math.exp(-dt*6));pulse*=Math.exp(-dt*.25);
 const ratio=Math.min(devicePixelRatio||1,1.5),w=Math.min(2560,Math.round(innerWidth*ratio)),h=Math.round(w*innerHeight/innerWidth);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h)}
 const styles=getComputedStyle(document.documentElement),color=styles.getPropertyValue('--glow').trim()||'#D4CEB8',rgb=color.slice(1).match(/../g).map(x=>parseInt(x,16)/255);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.uniform3f(uniforms.tint,...rgb);
 const audio=envelope;for(const k of ['rms','bass','mid','high']){const target=Math.min(1,Math.max(microphone[k]||0,output[k]||0));envelope[k]=paused?target:envelope[k]+(target-envelope[k])*(1-Math.exp(-dt*(target>envelope[k]?18:7)))}
 for(const [k,v] of Object.entries({time:t,morph:voice,aspect:w/h,amplitude:audio.rms,bass:audio.bass,mid:audio.mid,high:audio.high,reduced:Number(paused),region,pulse}))gl.uniform1f(uniforms[k],v);
 gl.uniform2f(uniforms.pointer,px,py);
 gl.uniform2f(uniforms.dock,(stage.x+stage.width-90)/innerWidth*2-1,1-(stage.top+90)/innerHeight*2);
 gl.uniform2f(uniforms.center,(stage.x+stage.width/2)/innerWidth*2-1,1-(stage.top+stage.height*.40)/innerHeight*2);
 gl.uniform1f(uniforms.entityScale,Math.min(stage.width*.66,stage.height*.75)/(innerHeight*.58));
 for(const [buf,count,mode,point] of [[lines,links.length/7,gl.LINES,0],[dots,nodes.length,gl.POINTS,1]]){gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.vertexAttribPointer(attrs[0],3,gl.FLOAT,false,28,0);gl.vertexAttribPointer(attrs[1],3,gl.FLOAT,false,28,12);gl.vertexAttribPointer(attrs[2],1,gl.FLOAT,false,28,24);gl.uniform1f(uniforms.points,point);gl.drawArrays(mode,0,count)}
 }label();requestAnimationFrame(frame);
 }catch(error){console.error('Luminaria renderer unavailable',error);canvas.remove();button.remove();document.body.classList.add('entity-fallback');window.addEventListener('studio-voice-state',e=>status.querySelector('strong').textContent=e.detail)}
})();
