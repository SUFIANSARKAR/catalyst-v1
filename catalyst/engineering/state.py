from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class EngineeringStateStore:
    """Durable mission/run evidence for long coding tasks and resumability."""
    def __init__(self, path: str="catalyst_data/engineering_runs.db"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, objective TEXT, status TEXT, phase TEXT, payload TEXT, created_at REAL, updated_at REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, kind TEXT, payload TEXT, created_at REAL)")

    def create(self, objective:str, payload:dict[str,Any]|None=None)->str:
        rid=uuid.uuid4().hex
        now=time.time()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?)",(rid,objective,"planned","recon",json.dumps(payload or {}),now,now))
        return rid

    def update(self, run_id:str, **fields:Any)->None:
        fields={k:v for k,v in fields.items() if k in {"status","phase","payload"}}
        if not fields: return
        fields["updated_at"]=time.time()
        cols=", ".join(f"{k}=?" for k in fields)
        vals=[json.dumps(v) if k=="payload" and not isinstance(v,str) else v for k,v in fields.items()]
        vals.append(run_id)
        with sqlite3.connect(self.path) as db: db.execute(f"UPDATE runs SET {cols} WHERE id=?",vals)

    def event(self, run_id:str, kind:str, payload:dict[str,Any])->None:
        with sqlite3.connect(self.path) as db: db.execute("INSERT INTO events(run_id,kind,payload,created_at) VALUES(?,?,?,?)",(run_id,kind,json.dumps(payload,ensure_ascii=False)[:100000],time.time()))

    def get(self, run_id:str)->dict[str,Any]|None:
        with sqlite3.connect(self.path) as db:
            row=db.execute("SELECT id,objective,status,phase,payload,created_at,updated_at FROM runs WHERE id=?",(run_id,)).fetchone()
            if not row: return None
            events=db.execute("SELECT kind,payload,created_at FROM events WHERE run_id=? ORDER BY id DESC LIMIT 200",(run_id,)).fetchall()
        return {"id":row[0],"objective":row[1],"status":row[2],"phase":row[3],"payload":json.loads(row[4] or "{}"),"created_at":row[5],"updated_at":row[6],"events":[{"kind":e[0],"payload":json.loads(e[1]),"created_at":e[2]} for e in reversed(events)]}
