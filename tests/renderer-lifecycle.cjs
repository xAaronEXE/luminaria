// Execute the actual renderer with controlled DOM/WebGL boundaries. No pixels or GPU are simulated as evidence.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/core.js'),'utf8');
function fixture({available=true,reduced=false}={}){
 const events=new Map(),frames=[],draws=[],uniforms=[];
 const el=()=>({style:{},listeners:{},setAttribute(){},prepend(){},append(){},remove(){this.removed=true},addEventListener(name,callback){this.listeners[name]=callback},querySelector(){return this.child??=el()},getBoundingClientRect(){return {x:200,width:900,bottom:100,top:700}}});
 const gl=new Proxy({getShaderParameter:()=>true,getProgramParameter:()=>true,getAttribLocation:()=>0,getUniformLocation:(_,name)=>name,drawArrays:(...args)=>draws.push(args),uniform1f:(...args)=>uniforms.push(args)},{get:(object,key)=>key in object?object[key]:()=>({})});
 const canvas=el();canvas.getContext=()=>available?gl:null;canvas.width=300;canvas.height=150;
 const elements=[],classes=new Set(),media={matches:reduced,addEventListener(name,fn){this.change=fn}};
 const body={prepend(){},append(){},dataset:{},classList:{add:x=>classes.add(x),contains:x=>classes.has(x),toggle(){}}};
 const context={console,Uint8Array,Float32Array,Math,Number,Object,document:{body,hidden:false,documentElement:{},createElement(type){const node=type==='canvas'?canvas:el();elements.push(node);return node},querySelector:()=>el()},window:{addEventListener(name,fn){events.set(name,[...(events.get(name)||[]),fn])},dispatchEvent(e){for(const fn of events.get(e.type)||[])fn(e)}},matchMedia:()=>media,ResizeObserver:class{observe(){}disconnect(){}},CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail}},performance:{now:()=>0},requestAnimationFrame:fn=>frames.push(fn),getComputedStyle:()=>({getPropertyValue:()=>'#EAE6D9'}),devicePixelRatio:1,innerWidth:1200,innerHeight:900,studioPrefs:{motion:true},state:{},safe:fn=>fn,savePrefs:async()=>{}};
 vm.runInNewContext(source,context,{filename:'core.js'});
 return {context,canvas,classes,frames,draws,uniforms,media,elements,tick(time){const next=frames.shift();if(next)next(time)},send(type,detail){context.window.dispatchEvent({type,detail})}};
}
{
 const f=fixture({available:false});assert(f.classes.has('entity-fallback'));assert.equal(f.frames.length,0);assert.equal(f.context.window.luminariaRenderStats.mode,'fallback');
 f.send('studio-voice-state','Speaking');assert.equal(f.elements[1].child.textContent,'Speaking');
}
{
 const f=fixture();f.tick(100);assert(f.draws.length>0);const baseline=f.draws.length;let prevented=false;
 f.canvas.listeners.webglcontextlost({preventDefault(){prevented=true}});assert(prevented);assert(f.canvas.removed);
 f.tick(200);assert.equal(f.frames.length,0);assert.equal(f.draws.length,baseline);assert.equal(f.context.window.luminariaRenderStats.mode,'fallback');
}
{
 const f=fixture({reduced:true});assert.equal(f.context.window.luminariaRenderStats.reducedMotion,true);assert.equal(f.context.window.luminariaRenderStats.paused,true);
 f.tick(100);const baseline=f.draws.length;f.tick(200);assert.equal(f.draws.length,baseline);assert(f.uniforms.some(([name,value])=>name==='reduced'&&value===1));
 f.media.matches=false;f.media.change();f.tick(300);assert(f.draws.length>baseline);
 f.send('studio-preferences',{motion:false});assert.equal(f.context.window.luminariaRenderStats.paused,true);assert.equal(f.context.window.luminariaRenderStats.fps,0);
}
console.log('Renderer lifecycle passed: unavailable WebGL, context-loss loop termination, initial reduced motion, preference updates. DOM/WebGL boundaries are stubbed; native rendering remains a separate check.');
