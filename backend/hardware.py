"""Local hardware inventory and opt-in measurements. Never tunes the system implicitly."""
import asyncio,hashlib,json,os,platform,secrets,socket,statistics,subprocess,time
from pathlib import Path
import httpx,psutil
from .config import CONFIG
from .models import registry,save
from .store import now,uid

FLAGS=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0

def command(argv,timeout=8):
    try:
        result=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,creationflags=FLAGS)
        return (result.stdout.strip() or result.stderr.strip()) if result.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None

def gpu_memory():
    output=command(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader,nounits'])
    rows=[]
    for line in (output or '').splitlines():
        fields=line.rsplit(',',2)
        try:rows.append({'name':fields[0].strip(),'vram_bytes':int(fields[1].strip())*1024**2,'used_bytes':int(fields[2].strip())*1024**2})
        except (ValueError,IndexError):continue
    return rows

def information():
    cpu=platform.processor() or None
    if os.name=='nt':
        cpu=command(['powershell.exe','-NoProfile','-NonInteractive','-Command','(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name) -join "; "']) or cpu
    exe=Path(CONFIG.get('llama_executable',''))
    version=command([str(exe),'--version']) if exe.is_file() else None
    if version:version=version[:1000]
    gpus=gpu_memory()
    if not gpus and os.name=='nt':
        names=command(['powershell.exe','-NoProfile','-NonInteractive','-Command','Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'])
        gpus=[{'name':line,'vram_bytes':None,'used_bytes':None} for line in (names or '').splitlines()]
    result={'cpu':cpu,'physical_cores':psutil.cpu_count(logical=False),'logical_cores':psutil.cpu_count(),
            'ram_bytes':psutil.virtual_memory().total,'gpus':gpus,'runtime_version':version,
            'runtime_available':exe.is_file(),'measured_at':now(),
            'limitations':'GPU memory unavailable unless the installed driver exposes a supported query. No values are estimated.'}
    identity={k:result[k] for k in ('cpu','physical_cores','logical_cores','ram_bytes')}
    identity['gpus']=[{k:g[k] for k in ('name','vram_bytes')} for g in gpus]
    result['hardware_id']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return result

def provenance(model,hardware):
    file=Path(model['model_file']);stat=file.stat();exe=Path(CONFIG.get('llama_executable',''))
    if not exe.is_file():raise ValueError('Configure an existing llama-server executable first.')
    # The large weight file is identified by path/size/mtime; do not hash gigabytes during a UI request.
    result={'model':model['id'],'model_file':str(file.resolve()),'model_bytes':stat.st_size,'model_mtime_ns':stat.st_mtime_ns,
            'runtime_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'runtime_version':hardware['runtime_version'],
            'hardware_id':hardware['hardware_id'],'context':model['context'],'batch':512,'ubatch':128,'kv':'q8_0'}
    result['key']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result

def choices(body):
    threads=body.get('threads',[4,8]);layers=body.get('gpu_layers',[0,16,-1])
    if not isinstance(threads,list) or not 1<=len(threads)<=4 or any(type(n)!=int or not 1<=n<=min(256,psutil.cpu_count() or 1) for n in threads):raise ValueError('Choose one to four valid CPU thread counts.')
    if not isinstance(layers,list) or not 1<=len(layers)<=3 or any(type(n)!=int or not -1<=n<=256 for n in layers):raise ValueError('Choose one to three GPU layer counts; -1 requests full offload, 0 CPU-only.')
    return list(dict.fromkeys(threads)),list(dict.fromkeys(layers))

async def terminate(proc):
    if proc.returncode is None:
        if os.name=='nt':
            killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(proc.pid),'/T','/F',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=FLAGS)
            await killer.wait()
        else:proc.terminate()
        await proc.wait()

async def measure_variant(model,threads,layers,progress):
    # A temporary loopback server isolates settings without changing the user's model registry or manager.
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    token=secrets.token_urlsafe(24);url=f'http://127.0.0.1:{port}'
    argv=[CONFIG['llama_executable'],'-m',model['model_file'],'--host','127.0.0.1','--port',str(port),
          '-c',str(model['context']),'-np','1','-t',str(threads),'-ngl',str(layers),'-fit','off',
          '-b','512','-ub','128','-ctk','q8_0','-ctv','q8_0','-fa','on','--jinja','--api-key',token]
    if layers==0:argv+=['--no-kv-offload']
    proc=await asyncio.create_subprocess_exec(*argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=FLAGS)
    stop=asyncio.Event();samples=[];jitter=[]
    async def monitor():
        while not stop.is_set():
            start=time.monotonic();await asyncio.sleep(.1);jitter.append(max(0,time.monotonic()-start-.1))
            try:samples.append(psutil.Process(proc.pid).memory_info().rss)
            except psutil.Error:pass
    watcher=asyncio.create_task(monitor())
    try:
        gpus_before=await asyncio.to_thread(gpu_memory)
        results=[]
        async with httpx.AsyncClient(timeout=httpx.Timeout(300,connect=5),trust_env=False,headers={'Authorization':'Bearer '+token}) as client:
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                if proc.returncode is not None:raise ValueError('Temporary runtime exited; this configuration may not fit or be supported.')
                try:
                    response=await client.get(url+'/health',timeout=2)
                    if response.status_code==200:break
                except httpx.HTTPError:pass
                await asyncio.sleep(.5)
            else:raise ValueError('Runtime did not become ready within two minutes.')
            for repetition in range(3):
                progress.update(repetition=repetition+1)
                payload={'model':model['id'],'messages':[{'role':'user','content':'Explain hash tables, collisions, resizing, and practical tradeoffs in several detailed paragraphs.'}],
                         'max_tokens':256,'temperature':0,'stream':True,'stream_options':{'include_usage':True},'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
                started=time.monotonic();first=None;usage={};timing={}
                async with client.stream('POST',url+'/v1/chat/completions',json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith('data: ') or line=='data: [DONE]':continue
                        data=json.loads(line[6:]);usage=data.get('usage') or usage;timing=data.get('timings') or timing
                        if first is None and any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in data.get('choices',[])):first=time.monotonic()
                elapsed=time.monotonic()-started;count=usage.get('completion_tokens')
                if first is None or not isinstance(count,int) or count<=0:raise ValueError('Runtime did not supply usable token counts; no speed was invented.')
                results.append({'first_token_seconds':first-started,'end_to_end_tps':count/elapsed,'output_tokens':count,
                                'prompt_tps':timing.get('prompt_per_second'),'decode_tps':timing.get('predicted_per_second'),'elapsed':elapsed})
        gpus_after=await asyncio.to_thread(gpu_memory)
        return {'threads':threads,'gpu_layers':layers,'repetitions':results,'median_tps':statistics.median(r['end_to_end_tps'] for r in results),
                'median_first_token_seconds':statistics.median(r['first_token_seconds'] for r in results),'peak_runtime_rss_bytes':max(samples,default=None),
                'gpu_before':gpus_before,'gpu_after':gpus_after,'gpu_memory_scope':'Driver snapshots for the whole GPU, not per-process peak VRAM.',
                'maximum_event_loop_delay_seconds':max(jitter,default=None),'responsiveness_scope':'Backend event-loop scheduling; browser/render performance is separate.'}
    finally:
        stop.set()
        try:await watcher
        finally:await terminate(proc)

class Tuning:
    def __init__(self,store):self.store=store;self.task=None;self.job=None;self.cancel_requested=False
    def public(self):return self.job or {'state':'Idle'}
    def start(self,model,body,hardware):
        if self.task and not self.task.done():raise ValueError('A tuning benchmark is already running.')
        threads,layers=choices(body);identity=provenance(model,hardware)
        self.cancel_requested=False
        self.job={'id':uid(),'state':'Running','model':model['id'],'started':now(),'variants':[],'progress':{},'provenance':identity}
        self.task=asyncio.create_task(self.run(model,threads,layers));return self.public()
    async def run(self,model,threads,layers):
        try:
            for t in threads:
                for g in layers:
                    self.job['progress']={'threads':t,'gpu_layers':g,'repetition':0}
                    try:result=await measure_variant(model,t,g,self.job['progress'])
                    except (ValueError,httpx.HTTPError,OSError) as error:result={'threads':t,'gpu_layers':g,'error':str(error)[:300]}
                    self.job['variants'].append(result)
            successful=[r for r in self.job['variants'] if r.get('median_tps')]
            self.job['state']='Completed' if successful else 'Failed'
            self.job['best']=max(successful,key=lambda r:r['median_tps'],default=None)
        except asyncio.CancelledError:self.job['state']='Cancelled'
        except Exception as error:self.job.update(state='Failed',error=str(error)[:300])
        finally:
            self.job['finished']=now();history=self.store.setting('tuning_history',[])
            self.store.set_setting('tuning_history',(history+[self.job])[-30:])
    async def cancel(self):
        if self.task and not self.task.done():
            if not self.cancel_requested:self.cancel_requested=True;self.task.cancel()
            try:await asyncio.shield(self.task)
            except asyncio.CancelledError:
                if not self.task.cancelled():raise
                self.job.update(state='Cancelled',finished=now())
                history=[j for j in self.store.setting('tuning_history',[]) if j['id']!=self.job['id']]
                self.store.set_setting('tuning_history',(history+[self.job])[-30:])
        return self.public()

def apply_profile(store,job_id,hardware,rollback=False):
    models=registry()
    if rollback:
        previous=store.setting('tuning_rollback',None)
        if not previous:raise ValueError('No previous tuning selection is saved.')
        model=next((m for m in models if m['id']==previous['model']),None)
        if not model:raise ValueError('The previous model is no longer registered.')
        current=model.get('tuning');model['tuning']=previous['tuning']
    else:
        job=next((j for j in store.setting('tuning_history',[]) if j['id']==job_id),None)
        if not job or job['state']!='Completed' or not job.get('best'):raise ValueError('Choose a completed measured tuning run.')
        model=next((m for m in models if m['id']==job['model']),None)
        if not model or provenance(model,hardware)['key']!=job['provenance']['key']:raise ValueError('Model, runtime, context, or hardware changed; benchmark again before applying.')
        current=model.get('tuning');model['tuning']={k:job['best'][k] for k in ('threads','gpu_layers')}
        model['tuning'].update(provenance=job['provenance'],measurement=job_id)
    store.set_setting('tuning_rollback',{'model':model['id'],'tuning':current});save(models)
    return {'status':'ok','model':model['id'],'tuning':model['tuning'],'restart_required':True,'message':'Selection saved. Restart Luminaria and its owned model manager to apply it. No running settings were changed.'}
