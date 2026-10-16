/* Perspective filament field: local WebGL, no textures or remote assets. */
(()=>{
 const canvas=document.createElement('canvas');canvas.id='ambient-field';canvas.setAttribute('aria-hidden','true');document.body.prepend(canvas);
 document.querySelector('.core-stage')?.remove();
 const button=document.createElement('button');button.id='ambient-motion';button.className='text-button';document.querySelector('.sidebar-bottom').prepend(button);
 const gl=canvas.getContext('webgl',{alpha:false,antialias:false,powerPreference:'low-power'});if(!gl){canvas.remove();button.remove();return}
 const reduce=matchMedia('(prefers-reduced-motion: reduce)');let paused=reduce.matches||localStorage.getItem('studio-motion')==='off',energy=0,voice=0,audioLevel=0,activity=0,px=0,py=0,last=0,clock=0,dirty=true;
 function shader(type,text){const s=gl.createShader(type);gl.shaderSource(s,text);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
 const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,`
 attribute vec3 position;uniform float time,aspect,energy,voice,activity;uniform vec2 pointer;varying float depth;varying float hue;
 void main(){
 vec3 p=position;
 float longitude=atan(position.z,position.x),latitude=position.y;
 float side=sign(position.x);
 vec3 brain=vec3(side*(.13+abs(position.x)*.68),position.y*.95,position.z*.68);
 brain.y+=.12*sin(longitude*9.)*cos(latitude*8.);
 float ring=2.1+.5*cos(latitude*2.4+time*.3);
 vec3 torus=vec3(ring*cos(longitude),.55*sin(latitude*2.4+time*.3),ring*sin(longitude));
 p=mix(brain,torus,voice);
 float a=time*.045+pointer.x*.13;
 p*=1.+energy*.12;
 p.y+=sin(longitude*5.+time*2.)*energy*.12;
 p.xz=mat2(cos(a),-sin(a),sin(a),cos(a))*p.xz;
 p.y+=pointer.y*.16;p.z+=mix(7.,5.6,voice);
 depth=clamp(1.-p.z/13.,.06,.85);
 hue=position.y;
 gl_Position=vec4(p.x*1.65/aspect,p.y*1.65,0.,p.z);
 gl_PointSize=(1.4+energy*2.)*max(1.,4./p.z);
 }`));
 gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`precision mediump float;varying float depth;varying float hue;uniform float points,time,activity;uniform vec3 tint;void main(){if(points>.5&&length(gl_PointCoord-vec2(.5))>.5)discard;float pulse=pow(max(0.,sin(hue*9.-time*3.)),14.)*activity;vec3 color=mix(tint,vec3(1.),pulse*.55);gl_FragColor=vec4(color,depth*(points>.5?.66:.18));}`));gl.linkProgram(program);gl.useProgram(program);
 const vertices=[],lines=[];for(let band=0;band<14;band++)for(let i=0;i<190;i++){const t=i/189*Math.PI*4.4,phase=band*.09,radius=2.4+band*.09,p=[Math.cos(t+phase)*radius,Math.sin(t*.55+phase)*1.8+(band-7)*.055,Math.sin(t+phase)*radius];vertices.push(...p);if(i)lines.push(...vertices.slice(vertices.length-6,vertices.length-3),...p)}
 const bind=data=>{const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);return b};const dots=bind(vertices),threads=bind(lines),position=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(position);const u=Object.fromEntries(['time','aspect','energy','pointer','points','voice','activity','tint'].map(n=>[n,gl.getUniformLocation(program,n)]));gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
 function label(){button.textContent=paused?'Resume background motion':'Pause background motion';button.setAttribute('aria-pressed',String(paused))}label();button.onclick=()=>{paused=!paused;localStorage.setItem('studio-motion',paused?'off':'on');dirty=true;label()};
 window.addEventListener('studio-audio',e=>{audioLevel=Math.min(1,e.detail||0)});window.addEventListener('studio-preferences',e=>{paused=reduce.matches||!e.detail.motion;dirty=true;label()});window.addEventListener('studio-state',()=>{activity=state.run&&!state.run.finished?1:0;dirty=true});
 window.addEventListener('pointermove',e=>{px=e.clientX/innerWidth-.5;py=.5-e.clientY/innerHeight});window.addEventListener('resize',()=>dirty=true);window.addEventListener('mint-token',()=>energy=.65);window.addEventListener('mint-type',()=>energy=1);reduce.addEventListener('change',e=>{paused=e.matches;dirty=true;label()});canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();canvas.hidden=true;button.hidden=true});
 function frame(now){requestAnimationFrame(frame);if(document.hidden||(paused&&!dirty)||now-last<50)return;if(!paused)clock+=Math.min((now-last)/1000,.1);last=now;dirty=false;energy=Math.max(energy*.94,audioLevel);voice+=(Number(document.body.dataset.voice==='conversation')-voice)*.08;const ratio=Math.min(devicePixelRatio||1,2),scale=Math.min(1,3840/(innerWidth*ratio),2160/(innerHeight*ratio)),w=Math.round(innerWidth*ratio*scale),h=Math.round(innerHeight*ratio*scale);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h)}const color=h=>h.slice(1).match(/../g).map(v=>parseInt(v,16)/255),bg=color(studioPrefs.background||'#141A17'),accent=color(studioPrefs.accent||'#B7FF2E');gl.clearColor(...bg,1);gl.uniform3f(u.tint,...accent);gl.uniform1f(u.voice,voice);gl.uniform1f(u.activity,activity);gl.clear(gl.COLOR_BUFFER_BIT);gl.uniform1f(u.time,clock);gl.uniform1f(u.aspect,w/h);gl.uniform1f(u.energy,paused?0:energy);gl.uniform2f(u.pointer,px,py);for(const [buffer,count,mode,points]of [[threads,lines.length/3,gl.LINES,0],[dots,vertices.length/3,gl.POINTS,1]]){gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.vertexAttribPointer(position,3,gl.FLOAT,false,0,0);gl.uniform1f(u.points,points);gl.drawArrays(mode,0,count)}}requestAnimationFrame(frame);
})();
