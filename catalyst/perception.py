from __future__ import annotations
import json, sqlite3, time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from .computer_use import BrowserObservation

class PerceptionStore:
    """Persists environment observations so perception can be correlated with later missions."""
    def __init__(self, path='catalyst_data/perception.db'):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,kind TEXT NOT NULL,source TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL,session_id TEXT)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(created_at)')
        self.db.commit()
    def add(self, kind, source, payload, session_id=None):
        oid=uuid4().hex; self.db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',(oid,kind,source,json.dumps(payload,ensure_ascii=False),time.time(),session_id)); self.db.commit(); return oid
    def recent(self, limit=50):
        rows=self.db.execute('SELECT * FROM observations ORDER BY created_at DESC LIMIT ?',(max(1,min(int(limit),500)),)).fetchall()
        return [dict(r)|{'payload':json.loads(r['payload'])} for r in rows]
    def close(self): self.db.close()

