"""Durable source history and versioned working summaries. No transcript truncation."""
import json
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

def uid(): return uuid.uuid4().hex
def now(): return time.time()

class Store:
    def __init__(self, path):
        self.data_directory = Path(path).resolve().parent
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,title TEXT,created REAL,updated REAL,archived INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat TEXT REFERENCES chats(id),payload TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS message_chat ON messages(chat,id);
        CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY,chat TEXT,through_id INTEGER,content TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,title TEXT,content TEXT,source TEXT,updated REAL);
        CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,chat TEXT,name TEXT,args TEXT,tier TEXT,status TEXT,result TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,title TEXT,prompt TEXT,interval INTEGER,next_run REAL,enabled INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,chat TEXT,payload TEXT,status TEXT,updated REAL);
        CREATE TABLE IF NOT EXISTS retrieval_events(id TEXT PRIMARY KEY,run TEXT,tool TEXT,status TEXT,category TEXT,source TEXT,duration_ms INTEGER,attempts INTEGER,cached INTEGER,created REAL);
        ''')
        # Which plan step an action belongs to; older databases get the column added.
        if 'step' not in [r[1] for r in self.db.execute('PRAGMA table_info(actions)')]: self.db.execute('ALTER TABLE actions ADD COLUMN step TEXT')
        # A process restart must never resume previously approved side effects.
        self.db.execute("UPDATE actions SET status='interrupted' WHERE status='running'")
        self.db.commit()

    def rows(self, sql, args=()): return [dict(x) for x in self.db.execute(sql, args).fetchall()]
    def execute(self, sql, args=()):
        cur=self.db.execute(sql,args); self.db.commit(); return cur.lastrowid
    def create_chat(self, title='New task'):
        id=uid(); self.execute('INSERT INTO chats VALUES(?,?,?,?,0)',(id,title,now(),now())); return id
    def chats(self): return self.rows('SELECT * FROM chats WHERE archived=0 ORDER BY updated DESC')
    def add(self, chat, payload):
        id=self.execute('INSERT INTO messages(chat,payload,created) VALUES(?,?,?)',(chat,json.dumps(payload,ensure_ascii=False),now()))
        self.execute('UPDATE chats SET updated=? WHERE id=?',(now(),chat)); return id
    def save_run(self,run):
        safe={k:(list(v) if isinstance(v,set) else v) for k,v in run.items()}
        self.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)',(run['id'],run['chat'],json.dumps(safe),run['phase'],now()))
        folder=self.data_directory/'runs'/run['id']
        folder.mkdir(parents=True,exist_ok=True); (folder/'artifacts').mkdir(exist_ok=True)
        with (folder/'conversation.jsonl').open('w',encoding='utf-8') as f:
            for msg in self.messages(run['chat']): f.write(json.dumps(msg,ensure_ascii=False)+'\n')
    def purge_chat(self,chat):
        """Erase a trashed chat's history and run records. Returns run ids for checkpoint cleanup."""
        found=self.rows('SELECT archived FROM chats WHERE id=?',(chat,))
        if not found: raise ValueError('Chat not found')
        if found[0]['archived']!=2: raise ValueError('Move the chat to trash before deleting it permanently')
        runs=[r['id'] for r in self.rows('SELECT id FROM runs WHERE chat=?',(chat,))]
        with self.db:
            for table in ('messages','summaries','actions','runs'): self.db.execute(f'DELETE FROM {table} WHERE chat=?',(chat,))
            if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='run_events'").fetchone(): self.db.execute('DELETE FROM run_events WHERE chat=?',(chat,))
            self.db.execute('DELETE FROM settings WHERE key IN (?,?,?,?,?)',('context:'+chat,'plan:'+chat,'brief:'+chat,'integration-context:'+chat,'execution-mode:'+chat))
            self.db.execute('DELETE FROM chats WHERE id=?',(chat,))
        root=(self.data_directory/'runs').resolve()
        for run in runs:
            folder=(root/run).resolve()
            if folder.parent==root and folder.is_dir(): shutil.rmtree(folder,ignore_errors=True)
        return runs
    def trashed(self): return [r['id'] for r in self.rows('SELECT id FROM chats WHERE archived=2')]
    def messages(self, chat, after=0):
        return [dict(id=r['id'],created=r['created'],**json.loads(r['payload'])) for r in self.rows('SELECT * FROM messages WHERE chat=? AND id>? ORDER BY id',(chat,after))]
    def summary(self, chat):
        r=self.rows('SELECT * FROM summaries WHERE chat=? ORDER BY id DESC LIMIT 1',(chat,)); return r[0] if r else None
    def save_summary(self, chat, through, text):
        if not text.strip(): raise ValueError('Empty summary; original context retained')
        return self.execute('INSERT INTO summaries(chat,through_id,content,created) VALUES(?,?,?,?)',(chat,through,text,now()))
    def memory(self): return self.rows('SELECT * FROM memories ORDER BY updated DESC')
    def save_memory(self,title,content,source='user',id=None):
        id=id or uid(); self.execute('INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?)',(id,title,content,source,now())); return id
    def setting(self,key,default=None):
        r=self.rows('SELECT value FROM settings WHERE key=?',(key,))
        if not r: return default
        value=json.loads(r[0]['value'])
        if key.startswith('plan:'):
            from .plan_runner import upgrade_saved_checks
            return upgrade_saved_checks(value)
        return value
    def set_setting(self,key,value): self.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    def actions(self,chat):
        return [dict(r,args=json.loads(r['args']),result=json.loads(r['result']) if r['result'] else None) for r in self.rows('SELECT * FROM actions WHERE chat=? ORDER BY created',(chat,))]
    def reconcile_action(self, chat, action, outcome):
        from .plan_runner import unknown_outcome

        rows=self.rows('SELECT name,status,result FROM actions WHERE chat=? AND id=?',(chat,action))
        if not unknown_outcome(rows):
            raise ValueError('This action no longer has an unknown outcome.')
        if outcome not in ('applied','no_effect'):
            raise ValueError('Choose whether the interrupted action took effect.')
        status='done' if outcome=='applied' else 'retryable'
        text='You confirmed that this action took effect.' if outcome=='applied' else 'You confirmed that this action had no effect.'
        evidence=json.loads(rows[0]['result']) if rows[0]['result'] else {}
        evidence={**evidence,'text':text,'replayed':True,'reconciled':outcome,'reconciled_at':now()}
        self.execute('UPDATE actions SET status=?,result=? WHERE chat=? AND id=?',
                     (status,json.dumps(evidence),chat,action))

    def action_history(self,status='',query='',limit=200):
        sql='SELECT a.id,a.chat,a.name,a.args,a.tier,a.status,a.result,a.created,c.title,c.archived FROM actions a JOIN chats c ON c.id=a.chat WHERE 1=1'
        params=[]
        if status=='problems':sql+=" AND a.status IN ('error','denied','interrupted')"
        elif status:sql+=' AND a.status=?';params.append(status)
        if query:
            sql+=" AND (a.name LIKE ? ESCAPE '\\' OR a.args LIKE ? ESCAPE '\\' OR c.title LIKE ? ESCAPE '\\')"
            like='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%';params+=[like]*3
        sql+=' ORDER BY a.created DESC LIMIT ?';params.append(max(1,min(int(limit),500)))
        rows=[]
        for r in self.rows(sql,tuple(params)):
            result=json.loads(r['result']) if r['result'] else None
            text=result.get('text') if isinstance(result,dict) and isinstance(result.get('text'),str) else (json.dumps(result)[:2000] if result is not None else '')
            rows.append({'id':r['id'],'chat':r['chat'],'chat_title':r['title'],'chat_place':{1:'archived',2:'trash'}.get(r['archived'],'active'),
                         'name':r['name'],'args':json.loads(r['args']),'tier':r['tier'],'status':r['status'],'created':r['created'],'output':text[:600],'truncated':len(text)>600})
        return rows
    def recover_tool_pairs(self,chat_id=None):
        for chat in self.rows('SELECT id FROM chats WHERE id=?',(chat_id,)) if chat_id else self.rows('SELECT id FROM chats'):
            msgs=self.messages(chat['id']); answered={m.get('tool_call_id') for m in msgs if m['role']=='tool'}
            for msg in msgs:
                for call in msg.get('tool_calls',[]):
                    if call['id'] not in answered:
                        self.add(chat['id'],{'role':'tool','tool_call_id':call['id'],'content':'Process interrupted. Action outcome unknown; inspect files/state before retrying. Do not assume it executed.'})
