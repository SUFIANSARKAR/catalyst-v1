import json, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

class AutomationStore:
    def __init__(self, path:str):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(p,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute("CREATE TABLE IF NOT EXISTS automations(id TEXT PRIMARY KEY,name TEXT NOT NULL,objective TEXT NOT NULL,interval_minutes INTEGER NOT NULL,enabled INTEGER NOT NULL,next_run TEXT NOT NULL,last_run TEXT,claim_until TEXT)")
        cols={r[1] for r in self.db.execute('PRAGMA table_info(automations)').fetchall()}
        if 'claim_until' not in cols:self.db.execute("ALTER TABLE automations ADD COLUMN claim_until TEXT")
        self.db.commit()
    def create(self,name,objective,interval_minutes=60):
        aid=uuid4().hex; now=datetime.now(timezone.utc); self.db.execute('INSERT INTO automations VALUES(?,?,?,?,?,?,?,?)',(aid,name[:120],objective,max(1,int(interval_minutes)),1,(now+timedelta(minutes=interval_minutes)).isoformat(),None,None)); self.db.commit(); return aid
    def list(self): return [dict(r) for r in self.db.execute('SELECT * FROM automations ORDER BY name').fetchall()]
    def claim_due(self,limit=4):
        now=datetime.now(timezone.utc); now_s=now.isoformat(); claim=(now+timedelta(seconds=120)).isoformat(); out=[]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows=self.db.execute("SELECT * FROM automations WHERE enabled=1 AND next_run<=? AND (claim_until IS NULL OR claim_until<=?) ORDER BY next_run LIMIT ?",(now_s,now_s,limit)).fetchall()
            for r in rows:
                self.db.execute('UPDATE automations SET claim_until=? WHERE id=?',(claim,r['id']))
                out.append(dict(r))
            self.db.commit(); return out
        except Exception:
            self.db.rollback(); raise
    def mark_dispatched(self,aid,interval):
        now=datetime.now(timezone.utc); self.db.execute('UPDATE automations SET last_run=?,next_run=?,claim_until=NULL WHERE id=?',(now.isoformat(),(now+timedelta(minutes=max(1,int(interval)))).isoformat(),aid)); self.db.commit()
    def release_claim(self,aid): self.db.execute('UPDATE automations SET claim_until=NULL WHERE id=?',(aid,)); self.db.commit()
    def peek_due(self,limit=20):
        now=datetime.now(timezone.utc).isoformat()
        rows=self.db.execute("SELECT * FROM automations WHERE enabled=1 AND next_run<=? ORDER BY next_run LIMIT ?",(now,max(1,min(int(limit),500)))).fetchall()
        return [dict(r) for r in rows]
    def due(self): return self.claim_due(1000)
    def mark_run(self,aid,interval): self.mark_dispatched(aid,interval)
    def set_enabled(self,aid,enabled): self.db.execute('UPDATE automations SET enabled=?,claim_until=NULL WHERE id=?',(1 if enabled else 0,aid)); self.db.commit()
    def close(self): self.db.close()
