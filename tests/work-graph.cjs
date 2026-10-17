const assert=require('node:assert/strict'),{reduce}=require('../web/work-graph.js');
const event=(id,seq,type,fields={})=>({id,seq,type,run:'r1',chat:'c',at:seq,...fields});
const events=[event('start',1,'run.started',{status:'running'}),event('gen',2,'generation.started',{node:'gen0',status:'running'}),event('requested',3,'tool.requested',{node:'a',tool:'read_file',parent:'gen0',region:'files',status:'requested',evidence:{action:'a'}}),event('wait',4,'approval.requested',{node:'a',status:'waiting'}),event('done',5,'tool.completed',{node:'a',status:'done',evidence:{action:'a'}})];
let scene=reduce([events[4],...events,events[3]]);
assert.equal(scene.nodes.length,3);assert.equal(scene.all.get('r1:a').status,'done');assert.equal(scene.edges.length,1);assert.equal(scene.all.get('r1:a').events.length,3);
scene=reduce(events.slice(0,4));assert.equal(scene.focus,'r1:a');assert.equal(scene.all.get(scene.focus).status,'waiting');
scene=reduce([...events.slice(0,4),event('cancel',6,'run.cancelled',{status:'cancelled'})]);assert.equal(scene.all.get('r1:a').status,'interrupted');assert.equal(scene.all.get('r1:gen0').status,'interrupted');
const plan=(id,seq,dependencies)=>event(id,seq,'plan.revised',{node:'plan'+seq,source:'model-provided',steps:[{id:'first',title:'Inspect',status:'done',depends_on:[]},{id:'second',title:'Edit',status:'active',depends_on:dependencies}]});
scene=reduce([plan('p1',1,['first']),plan('p2',2,[])]);assert.equal(scene.edges.filter(e=>e.kind==='dependency').length,0);assert.equal(scene.all.get('r1:step:second').source,'model-provided');
scene=reduce([...events,event('failed',6,'tool.failed',{node:'a',status:'failed'}),event('retry',7,'tool.started',{node:'b',tool:'read_file',status:'running',follows_failure:'a'})]);assert(scene.edges.some(e=>e.from==='r1:a'&&e.to==='r1:b'&&e.kind==='failure-followup'));
const other=event('other',1,'run.started',{run:'r2',at:20,status:'running'});scene=reduce([...events,other]);assert.equal(scene.nodes.filter(n=>n.kind==='cluster').length,1);assert(scene.all.has('r1:a'));scene=reduce([...events,other],new Set(['r1']));assert(scene.nodes.some(n=>n.id==='r1:a'));
scene=reduce(Array.from({length:300},(_,i)=>event('n'+i,i,'tool.completed',{node:'n'+i,tool:'read_file',status:'done'})));assert.equal(scene.nodes.length,200);assert.equal(scene.omitted,101);
assert.equal(reduce([]).nodes.length,0);
console.log('Work graph passed: replay deduplication, ordering, approval focus, cancellation, revised dependencies, failure relationships, collapsed runs, bounded nodes, empty history.');

const vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 const listeners=new Map(),frames=[],requests=[],published=[];
 const context={Map,Set,Math,Date,document:{},state:{chat:''},requestAnimationFrame:fn=>frames.push(fn),CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail}},api:path=>new Promise(resolve=>requests.push({path,resolve})),window:{addEventListener(type,fn){listeners.set(type,fn)},dispatchEvent(e){if(e.type==='studio-scene')published.push(e.detail);listeners.get(e.type)?.(e)}}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/work-graph.js'),'utf8'),context);
 const tick=()=>{while(frames.length)frames.shift()()};
 context.state.chat='old';listeners.get('studio-state')();context.state.chat='new';listeners.get('studio-state')();
 requests[1].resolve({events:[{...events[0],chat:'new'}]});await Promise.resolve();await Promise.resolve();tick();
 requests[0].resolve({events:[{...events[1],chat:'old'}]});await Promise.resolve();await Promise.resolve();tick();
 assert.equal(published.at(-1).chat,'new');assert.equal(published.at(-1).nodes.length,1);
 listeners.get('studio-work')({detail:{...events[2],chat:'old'}});tick();assert.equal(published.at(-1).nodes.length,1);
 console.log('Work recovery passed: late responses and other-chat events cannot overwrite current chat.');
})().catch(e=>{console.error(e);process.exitCode=1});
