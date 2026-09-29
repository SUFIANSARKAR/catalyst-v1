import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class ProvenanceStore:
    def __init__(self,path:str):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p,check_same_thread=False); self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, kind TEXT, source TEXT, claim TEXT, metadata TEXT, created_at TEXT)"); self.db.commit()
    def add(self,kind,source,claim,metadata=None):
        eid=uuid4().hex; now=datetime.now(timezone.utc).isoformat(); self.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?)",(eid,kind,source,claim,json.dumps(metadata or {}),now)); self.db.commit(); return eid
    def list(self,kind=None,limit=200):
        q="SELECT * FROM evidence"; args=[]
        if kind: q+=" WHERE kind=?"; args.append(kind)
        q+=" ORDER BY created_at DESC LIMIT ?"; args.append(limit)
        return [dict(r) for r in self.db.execute(q,args).fetchall()]
    def close(self): self.db.close()
