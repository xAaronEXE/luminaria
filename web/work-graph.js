/* Execution evidence is reduced independently of the renderer. */
(()=>{
 const regions=['planning','memory','retrieval','files','tools','generation','verification'];
 function reduce(events,expanded=new Set(),limit=200){
  const unique=new Map();for(const e of events)if(e?.id&&e.run)unique.set(e.id,e);
  const runs=new Map();for(const e of unique.values()){if(!runs.has(e.run))runs.set(e.run,[]);runs.get(e.run).push(e)}
  const ordered=[...runs].map(([id,list])=>({id,events:list.sort((a,b)=>a.seq-b.seq),at:Math.min(...list.map(e=>e.at||0))})).sort((a,b)=>a.at-b.at||a.id.localeCompare(b.id));
  const nodes=[],edges=[],all=new Map();let focus=null;
  for(const [index,run] of ordered.entries()){
   const root=run.id+':run',local=new Map(),links=[];let terminal=false;
   const put=(id,fields)=>{const old=local.get(id)||{id,run:run.id,region:'generation',label:'Observed activity',status:'observed',events:[]};const n={...old,...fields};local.set(id,n);return n};
   put(root,{kind:'run',label:'Task run',events:[],status:'observed'});
   for(const e of run.events){
    if(e.type.startsWith('run.')){
     const n=put(root,{label:e.label||'Task run',status:e.status||'running',error:e.error,evidence:e.evidence,seq:e.seq});n.events.push(e);
     terminal=['run.completed','run.failed','run.cancelled','run.interrupted'].includes(e.type);
     if(e.type==='run.resumed')terminal=false;
     continue;
    }
    if(e.type.startsWith('plan.')){
     for(let i=links.length-1;i>=0;i--)if(links[i].kind==='dependency')links.splice(i,1);
     for(const step of e.steps||[]){
      const id=run.id+':step:'+step.id;
      put(id,{kind:'step',label:step.title,status:step.status,region:'planning',source:'model-provided',evidence:e.evidence,step:step.id,seq:e.seq,events:[e]});
      for(const dependency of step.depends_on||[])links.push({from:run.id+':step:'+dependency,to:id,kind:'dependency'});
     }
    }
    if(!e.node)continue;
    const id=run.id+':'+e.node,n=put(id,{kind:e.tool?'tool':e.type.split('.')[0],region:regions.includes(e.region)?e.region:(e.type.startsWith('reasoning.')?'generation':local.get(id)?.region||'generation'),seq:e.seq});
    n.events.push(e);for(const key of ['label','status','evidence','error','tool','approval_tier','source','metrics'])if(e[key]!==undefined)n[key]=e[key];
    if(e.type==='reasoning.started')n.reasoning=true;
    if(e.parent)links.push({from:run.id+':'+e.parent,to:id,kind:'execution'});
    if(e.follows_failure)links.push({from:run.id+':'+e.follows_failure,to:id,kind:'failure-followup'});
    if(e.step)links.push({from:run.id+':step:'+e.step,to:id,kind:'step'});
   }
   if(terminal)for(const n of local.values())if(n.kind!=='run'&&['running','waiting','requested','allowed'].includes(n.status))n.status='interrupted';
   for(const n of local.values())all.set(n.id,n);
   const latest=index===ordered.length-1;
   if(!latest&&!expanded.has(run.id))nodes.push({...local.get(root),kind:'cluster',label:'Earlier run · '+local.size+' recorded nodes',count:local.size});
   else{
    const list=[...local.values()].sort((a,b)=>(a.seq||0)-(b.seq||0));
    nodes.push(...list);edges.push(...links);
    if(latest){const candidates=list.filter(n=>['running','waiting','requested'].includes(n.status)&&n.kind!=='run');focus=(candidates.find(n=>n.status==='waiting')||candidates.at(-1)||list.at(-1))?.id}
   }
  }
  const visible=nodes.slice(-limit),ids=new Set(visible.map(n=>n.id)),dedup=new Map();
  for(const edge of edges)if(ids.has(edge.from)&&ids.has(edge.to)&&edge.from!==edge.to)dedup.set(edge.from+'|'+edge.to+'|'+edge.kind,edge);
  return {nodes:visible,edges:[...dedup.values()],focus:ids.has(focus)?focus:visible.at(-1)?.id||null,omitted:nodes.length-visible.length,runs:ordered.length,all};
 }
 if(typeof module!=='undefined')module.exports={reduce};
 if(typeof window==='undefined'||typeof document==='undefined')return;
 let current='',generation=0,events=new Map(),expanded=new Set(),scheduled=false,selected=null,snapshot=reduce([]),error='';
 function publish(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;snapshot={...reduce([...events.values()],expanded),chat:current,selected,error};window.luminariaScene=snapshot;window.dispatchEvent(new CustomEvent('studio-scene',{detail:snapshot}))})}
 function ingest(event){if(event?.chat!==current||!event.id||events.has(event.id))return;events.set(event.id,event);if(events.size>6000){const oldest=[...events.values()].sort((a,b)=>(a.at-b.at)||(a.seq-b.seq));for(const e of oldest.slice(0,events.size-6000))events.delete(e.id)}publish()}
 async function recover(){const chosen=current,ticket=++generation;if(!chosen){publish();return}try{const response=await api('/chats/'+encodeURIComponent(chosen)+'/work?runs=12');if(ticket!==generation||chosen!==current)return;error='';for(const e of response.events||[])ingest(e);publish()}catch(e){if(ticket===generation){error='Work history could not be loaded. Retry task overview to reconnect.';publish()}}}
 window.luminariaWork={recover,select(id){selected=id;publish();window.dispatchEvent(new CustomEvent('studio-node-selected',{detail:snapshot.all.get(id)||null}))},expand(run){expanded.add(run);publish()},snapshot:()=>snapshot};
 window.addEventListener('studio-work',e=>ingest(e.detail));
 window.addEventListener('studio-work-reconnect',recover);
 window.addEventListener('studio-state',()=>{const next=state.chat||'';if(next!==current){current=next;generation++;events=new Map();expanded=new Set();selected=null;error='';publish();recover()}});
 publish();
})();
