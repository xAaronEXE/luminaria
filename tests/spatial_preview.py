"""Isolated browser preview with mocked APIs; never connects to installed app."""
import copy,json,time,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from backend.preferences import DEFAULTS
ROOT=Path(__file__).resolve().parents[1]
lock=threading.Lock();events=[];prefs=copy.deepcopy(DEFAULTS);run_id='preview-run';finished=False

def record(kind,node=None,**fields):
 with lock:
  seq=len(events)+1
  events.append(dict(id='fixture-'+str(seq),seq=seq,chat='preview',run=run_id,type=kind,at=time.time(),**({'node':node} if node else {}),**fields))
record('run.started',status='running',label='Browser preview task')
record('plan.created','plan1',region='planning',source='model-provided',steps=[dict(id='inspect',title='Inspect fixture file',status='done',depends_on=[]),dict(id='verify',title='Run fixture check',status='active',depends_on=['inspect'])],label='Plan from the model')
record('generation.started','gen0',status='running',label='Model response',region='generation')
record('generation.completed','gen0',status='done',region='generation',evidence={'message':2})
record('tool.completed','read-fixture',tool='read_file',status='done',label='Read fixture file',parent='gen0',region='files',step='inspect',evidence={'action':'read-fixture'})
record('tool.failed','failed-fixture',tool='run_code',status='failed',label='Fixture check failed',parent='gen0',region='verification',step='verify',evidence={'action':'failed-fixture'})
record('tool.started','check-fixture',tool='run_code',status='running',label='Verify fixture revision',parent='gen0',follows_failure='failed-fixture',region='verification',step='verify',evidence={'action':'check-fixture'})

def state(chat):
 return dict(chat=chat,chats=[dict(id='preview',title='Spatial workflow preview')],messages=[dict(id=1,role='user',content='Browser preview with mocked APIs: inspect and verify a fixture.',created=time.time()),dict(id=2,role='assistant',content='This is fixture data, not a real model run.',reasoning='Model-provided fixture reasoning for UI inspection.',created=time.time())] if chat else [],actions=[dict(id=id,name=name,args={'fixture':True},tier='auto',status=status,result={'text':text},created=time.time()) for id,name,status,text in [('read-fixture','read_file','done','Fixture contents'),('failed-fixture','run_code','failed','Fixture failure'),('check-fixture','run_code','done' if any(e['type']=='tool.completed' and e.get('node')=='check-fixture' for e in events) else 'running','Fixture check output')]] if chat else [],run=dict(id=run_id,phase='Complete' if finished else 'Running tools',finished=finished,live='',reasoning_text='',metrics={}) if chat else None,summaries=[],summary=None,context={},workspace=str(ROOT/'data'/'preview-files'),model='Preview fixture',context_limit=32768,memories=[],tool_count=0,active_runs=[],connectors={},schedules=[])

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'web'),**kwargs)
 def log_message(self,*args):pass
 def reply(self,data,status=200):
  payload=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  parsed=urlsplit(self.path);path=parsed.path
  if path=='/api/events':
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.end_headers();i=0
   try:
    self.wfile.write(b'data: {"type":"ready"}\n\n');self.wfile.flush()
    for _ in range(1800):
     with lock:batch=list(events[i:]);i=len(events)
     for event in batch:self.wfile.write(('data: '+json.dumps({'type':'work','event':event})+'\n\n').encode())
     if batch:self.wfile.write(b'data: {"type":"changed"}\n\n')
     self.wfile.flush();time.sleep(.2)
   except (BrokenPipeError,ConnectionResetError):pass
   return
  if path=='/api/bootstrap':return self.reply(dict(token='preview-only',version='0.2.8',name='Luminaria'))
  if path=='/api/gate':return self.reply(dict(unlocked=True,locked=False))
  if path=='/api/state':return self.reply(state(parse_qs(parsed.query).get('chat',[''])[0]))
  if path=='/api/preferences':return self.reply(prefs)
  if path.endswith('/work'):return self.reply(dict(chat='preview',events=events,active_run=None if finished else run_id))
  if path=='/api/model/status':return self.reply(dict(connected=False,loaded=False))
  if path=='/api/files':return self.reply([])
  if path.startswith('/api/'):return self.reply({})
  if path=='/no-webgl.js':
   payload=b"const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /^webgl/.test(type)?null:original.call(this,type,...args)};";self.send_response(200);self.send_header('Content-Type','application/javascript');self.end_headers();self.wfile.write(payload);return
  if path=='/':
   html=(ROOT/'web'/'index.html').read_text(encoding='utf-8').replace('<body>','<body><div style="position:fixed;top:0;left:270px;z-index:100;font-size:11px;background:var(--panel);color:var(--text);padding:3px 10px">BROWSER PREVIEW · MOCKED APIs · no model execution</div>')
   if 'no-webgl' in parsed.query:html=html.replace('<script src="/appearance.js">','<script src="/no-webgl.js"></script><script src="/appearance.js">')
   payload=html.encode();self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
  super().do_GET()
 def do_POST(self):
  global finished,run_id
  body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
  if self.path=='/api/preferences':prefs.update(body);return self.reply(prefs)
  if self.path=='/api/preview/advance':
   record('tool.completed','check-fixture',tool='run_code',status='done',region='verification',label='Fixture check completed',evidence={'action':'check-fixture'});record('run.completed',status='done',label='Fixture completed');finished=True
  elif self.path.endswith('/run'):
   run_id='preview-run-'+str(len(events));finished=False;record('run.started',status='running',label='Queued fixture message');record('generation.started','gen0',status='running',label='Fixture generation',region='generation')
  elif self.path.endswith('/stop'):record('run.cancelled',status='cancelled',label='Fixture cancelled');finished=True
  self.reply(dict(ok=True))

if __name__=='__main__':
 print('Browser preview with mocked APIs: http://127.0.0.1:3215',flush=True)
 ThreadingHTTPServer(('127.0.0.1',3215),Handler).serve_forever()
