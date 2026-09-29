import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
class ApprovalStore:
 def __init__(self,path='catalyst_data/approvals.db'):
  p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(p,check_same_thread=False,timeout=30);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA busy_timeout=30000');self.db.execute('CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,session_id TEXT,user_text TEXT NOT NULL,tool TEXT NOT NULL,arguments TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,resolved_at TEXT,decision TEXT,result TEXT,reason TEXT)');self.db.commit()
 def create(self,session_id,user_text,tool,arguments,reason=''):
  aid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();self.db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,session_id,user_text,tool,json.dumps(arguments,ensure_ascii=False),'pending',now,None,None,None,reason));self.db.commit();return aid
 def get(self,aid):
  r=self.db.execute('SELECT * FROM approvals WHERE id=?',(aid,)).fetchone();return dict(r) if r else None
 def list(self,status=None,limit=100):
  q='SELECT * FROM approvals';args=[]
  if status:q+=' WHERE status=?';args.append(status)
  q+=' ORDER BY created_at DESC LIMIT ?';args.append(limit);return [dict(r) for r in self.db.execute(q,args).fetchall()]
 def resolve(self,aid,approved,result=None,reason=''):
  status='approved' if approved else 'rejected';now=datetime.now(timezone.utc).isoformat();self.db.execute('UPDATE approvals SET status=?,resolved_at=?,decision=?,result=?,reason=? WHERE id=? AND status=?',(status,now,status,json.dumps(result,ensure_ascii=False) if result is not None else None,reason,aid,'pending'));self.db.commit();return self.get(aid)
 def close(self):self.db.close()
