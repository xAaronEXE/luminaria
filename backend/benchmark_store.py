"""Device-local benchmark history; legacy registry imports are idempotent."""
import hashlib,json,sqlite3,time
from contextlib import contextmanager
from .config import BASE_DATA

PATH=BASE_DATA/'benchmarks.sqlite3'

@contextmanager
def connect():
    db=sqlite3.connect(PATH,timeout=20)
    db.execute('CREATE TABLE IF NOT EXISTS benchmarks(id TEXT PRIMARY KEY,model TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS benchmark_model ON benchmarks(model,created)')
    db.execute('CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,model TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL)')
    try:
        with db:yield db
    finally:db.close()

def record(model,result,legacy=False):
    payload=json.dumps(result,sort_keys=True,ensure_ascii=False)
    identity=hashlib.sha256((model+'\0'+payload).encode()).hexdigest() if legacy else __import__('uuid').uuid4().hex
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO benchmarks VALUES(?,?,?,?)',(identity,model,payload,0 if legacy else time.time()))

def record_evaluation(model,result):
    with connect() as db:
        db.execute('INSERT INTO evaluations VALUES(?,?,?,?)',(__import__('uuid').uuid4().hex,model,json.dumps(result,ensure_ascii=False),time.time()))

def evaluations(model):
    with connect() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM evaluations WHERE model=? ORDER BY created DESC,rowid DESC',(model,))]

def history(model,legacy=()):
    # Preserve the legacy JSON exactly; migration never deletes the source records.
    with connect() as db:
        for index,result in enumerate(legacy):
            payload=json.dumps(result,sort_keys=True,ensure_ascii=False)
            identity=hashlib.sha256((model+'\0'+payload).encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO benchmarks VALUES(?,?,?,?)',(identity,model,payload,-index))
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM benchmarks WHERE model=? ORDER BY created DESC,rowid DESC',(model,))]
