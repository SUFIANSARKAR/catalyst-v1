import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

ACTIVE={'queued','planned','running','paused'}
TERMINAL={'completed','failed','cancelled'}

class MissionStore:
    def __init__(self,path='catalyst_data/missions.db'):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p,check_same_thread=False,timeout=30);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,objective TEXT NOT NULL,status TEXT NOT NULL,plan TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,result TEXT,error TEXT,checkpoint TEXT,session_id TEXT,priority INTEGER NOT NULL DEFAULT 50)')
        self.db.execute("CREATE TABLE IF NOT EXISTS mission_steps(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,seq INTEGER NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,result TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(mission_id,seq))")
        self.db.commit()
    def create(self,objective,session_id=None,priority=50):
        mid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();self.db.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(mid,objective,'planned',None,now,now,None,None,None,session_id,max(0,min(100,priority))));self.db.commit();return mid
    def get(self,mid):
        r=self.db.execute('SELECT * FROM missions WHERE id=?',(mid,)).fetchone();return dict(r) if r else None
    def list(self,status=None,limit=100):
        q='SELECT * FROM missions';args=[]
        if status:q+=' WHERE status=?';args.append(status)
        q+=' ORDER BY priority DESC,updated_at DESC LIMIT ?';args.append(max(1,min(int(limit),500)));return [dict(r) for r in self.db.execute(q,args).fetchall()]
    def update(self,mid,status,plan=None,result=None,error=None,checkpoint=None):
        self.db.execute('UPDATE missions SET status=?,plan=COALESCE(?,plan),result=COALESCE(?,result),error=?,checkpoint=COALESCE(?,checkpoint),updated_at=? WHERE id=?',(status,json.dumps(plan,ensure_ascii=False) if plan is not None else None,json.dumps(result,ensure_ascii=False) if result is not None else None,error,json.dumps(checkpoint,ensure_ascii=False) if checkpoint is not None else None,datetime.now(timezone.utc).isoformat(),mid));self.db.commit()
    def add_step(self,mid,seq,name,kind,payload):
        sid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();self.db.execute('INSERT OR REPLACE INTO mission_steps VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,mid,seq,name,kind,'queued',json.dumps(payload,ensure_ascii=False),None,None,now,now));self.db.commit();return sid
    def steps(self,mid):
        rows=self.db.execute('SELECT * FROM mission_steps WHERE mission_id=? ORDER BY seq',(mid,)).fetchall();out=[]
        for r in rows:
            x=dict(r);x['payload']=json.loads(x['payload']);x['result']=json.loads(x['result']) if x['result'] else None;out.append(x)
        return out
    def update_step(self,sid,status,result=None,error=None):
        self.db.execute('UPDATE mission_steps SET status=?,result=COALESCE(?,result),error=?,updated_at=? WHERE id=?',(status,json.dumps(result,ensure_ascii=False) if result is not None else None,error,datetime.now(timezone.utc).isoformat(),sid));self.db.commit()

    def update_step_payload(self,sid,payload):
        self.db.execute('UPDATE mission_steps SET payload=?,updated_at=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),sid));self.db.commit()
    def next_step(self,mid):
        steps=self.steps(mid); done={x['seq'] for x in steps if x['status'] in {'completed','skipped'}}
        for x in steps:
            if x['status'] in {'completed','skipped','running'}: continue
            deps=x.get('payload',{}).get('depends_on',[]) or []
            depseq=[]
            for dep in deps:
                try: depseq.append(int(str(dep).lstrip('s')))
                except Exception: pass
            if all(d in done for d in depseq): return x
        return None
    def pause(self,mid): self.update(mid,'paused',checkpoint={'phase':'paused'}); return self.get(mid)
    def cancel(self,mid,reason='cancelled by creator'):
        self.update(mid,'cancelled',error=reason,checkpoint={'phase':'cancelled'}); return self.get(mid)
    def resume(self,mid): self.update(mid,'queued',error=None,checkpoint={'phase':'resumed'}); return self.get(mid)

    def ready_steps(self,mid):
        steps=self.steps(mid); done={x['seq'] for x in steps if x['status'] in {'completed','skipped'}}; out=[]
        for step in steps:
            if step['status'] in {'completed','skipped','running'}: continue
            deps=step.get('payload',{}).get('depends_on',[]) or []
            depseq=[]
            for dep in deps:
                try: depseq.append(int(str(dep).lstrip('s')) )
                except Exception: pass
            if all(d in done for d in depseq): out.append(step)
        return out

    def record_attempt(self,mid,step,attempt,error=None):
        return self.update(mid,'running',checkpoint={'phase':'step_attempt','step':step.get('seq'),'step_id':step.get('id'),'attempt':attempt,'error':error})

    def close(self):self.db.close()
