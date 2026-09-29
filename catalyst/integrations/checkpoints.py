from __future__ import annotations
import copy, json, sqlite3, time
from pathlib import Path
from uuid import uuid4
from typing import Any

class StateCheckpointStore:
    """Catalyst-native durable snapshots/deltas inspired by checkpoint primitives."""
    def __init__(self, path='catalyst_data/state_checkpoints.db'):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,parent_id TEXT,state TEXT NOT NULL,delta TEXT NOT NULL,created_at REAL NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_cp_thread_seq ON checkpoints(thread_id,seq)')
        self.db.commit()

    @staticmethod
    def _delta(before: dict[str,Any], after: dict[str,Any]) -> dict[str,Any]:
        changed={}; removed=[]
        for k,v in after.items():
            if before.get(k) != v: changed[k]=copy.deepcopy(v)
        for k in before:
            if k not in after: removed.append(k)
        return {'set':changed,'remove':removed}

    def put(self, thread_id: str, state: dict[str,Any]) -> dict[str,Any]:
        row=self.db.execute('SELECT id,seq,state FROM checkpoints WHERE thread_id=? ORDER BY seq DESC LIMIT 1',(thread_id,)).fetchone()
        before=json.loads(row['state']) if row else {}
        seq=(int(row['seq'])+1) if row else 0
        cid=uuid4().hex; delta=self._delta(before,state)
        self.db.execute('INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?)',(cid,thread_id,seq,row['id'] if row else None,json.dumps(state,ensure_ascii=False),json.dumps(delta,ensure_ascii=False),time.time()))
        self.db.commit(); return {'id':cid,'thread_id':thread_id,'seq':seq,'parent_id':row['id'] if row else None,'delta':delta}

    def get(self, thread_id: str, seq: int | None = None) -> dict[str,Any] | None:
        q='SELECT * FROM checkpoints WHERE thread_id=?'; args=[thread_id]
        if seq is not None: q+=' AND seq<=?'; args.append(int(seq))
        q+=' ORDER BY seq DESC LIMIT 1'; row=self.db.execute(q,args).fetchone()
        return dict(row) if row else None

    def restore(self, thread_id: str, seq: int) -> dict[str,Any]:
        row=self.get(thread_id,seq)
        if not row: raise KeyError(f'checkpoint not found: {thread_id}:{seq}')
        return json.loads(row['state'])
