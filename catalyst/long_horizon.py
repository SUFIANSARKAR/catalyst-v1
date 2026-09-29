from __future__ import annotations
import json, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class LongHorizonEvaluator:
    """Persisted scenario evaluator with per-step timing, retries, and recovery metadata."""
    def __init__(self,path='catalyst_data/evals/long_horizon.db'):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(p,check_same_thread=False,timeout=30);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,scenario TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,result TEXT,checkpoint TEXT)');self.db.commit()
    def run(self,scenario,executor,stop_on_failure=True,max_steps=24):
        steps=list((scenario or {}).get('steps',[]))[:max(1,min(int(max_steps),100))];rid=uuid4().hex;started=datetime.now(timezone.utc).isoformat();results=[];status='passed';checkpoint={'seq':0,'status':'running'}
        self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',(rid,str((scenario or {}).get('name','scenario')),'running',started,None,None,json.dumps(checkpoint)));self.db.commit()
        for i,step in enumerate(steps,1):
            if any(r.get('id')==step.get('id',f'step-{i}') and r['status']=='passed' for r in results):continue
            t=time.perf_counter();expected=step.get('expect');attempts=max(1,min(int(step.get('max_attempts',1)),5));last=None;ok=False
            for attempt in range(1,attempts+1):
                try:value=executor(step,i,results);ok=self._matches(value,expected);last={'seq':i,'id':step.get('id',f'step-{i}'),'status':'passed' if ok else 'failed','attempt':attempt,'duration_ms':round((time.perf_counter()-t)*1000,3),'result':value,'expected':expected,'recovered':attempt>1}
                except Exception as exc:last={'seq':i,'id':step.get('id',f'step-{i}'),'status':'failed','attempt':attempt,'duration_ms':round((time.perf_counter()-t)*1000,3),'error':str(exc),'expected':expected};ok=False
                if ok:break
            results.append(last);checkpoint={'seq':i,'status':'passed' if ok else 'failed','attempt':last['attempt']};self.db.execute('UPDATE runs SET checkpoint=? WHERE id=?',(json.dumps(checkpoint),rid));self.db.commit()
            if not ok:
                status='failed'
                if stop_on_failure:break
        finished=datetime.now(timezone.utc).isoformat();report={'run_id':rid,'scenario':(scenario or {}).get('name','scenario'),'status':status,'steps':results,'passed':sum(r['status']=='passed' for r in results),'failed':sum(r['status']=='failed' for r in results),'completed':len(results)==len(steps),'checkpoint':checkpoint};self.db.execute('UPDATE runs SET status=?,finished_at=?,result=?,checkpoint=? WHERE id=?',(status,finished,json.dumps(report,ensure_ascii=False),json.dumps(checkpoint),rid));self.db.commit();return report
    @staticmethod
    def _matches(value,expected):
        if expected is None:return True
        if isinstance(expected,dict) and isinstance(value,dict):return all(value.get(k)==v for k,v in expected.items())
        return value==expected
    def recent(self,limit=20):
        rows=self.db.execute('SELECT * FROM runs ORDER BY started_at DESC LIMIT ?',(max(1,min(int(limit),100)),)).fetchall();out=[]
        for r in rows:
            x=dict(r);x['result']=json.loads(x['result']) if x['result'] else None;x['checkpoint']=json.loads(x['checkpoint']) if x['checkpoint'] else None;out.append(x)
        return out
    def close(self):self.db.close()
