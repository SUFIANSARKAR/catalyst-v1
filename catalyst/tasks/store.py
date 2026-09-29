import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class TaskStore:
    def __init__(self, path: str):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL, agent TEXT NOT NULL, priority INTEGER NOT NULL, parent_id TEXT, depends_on TEXT NOT NULL, result TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, priority DESC, created)")
        self.db.commit()

    def create(self, title: str, description: str = "", agent: str = "general", priority: int = 50, parent_id: str | None = None, depends_on: list[str] | None = None) -> str:
        tid = uuid4().hex; now = datetime.now(timezone.utc).isoformat()
        self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)", (tid, title[:240], description, "queued", agent, max(0,min(100,priority)), parent_id, json.dumps(depends_on or []), "", now, now)); self.db.commit(); return tid

    def update(self, task_id: str, status: str | None = None, result: str | None = None) -> None:
        row=self.db.execute("SELECT status,result FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not row: raise KeyError(task_id)
        now=datetime.now(timezone.utc).isoformat(); self.db.execute("UPDATE tasks SET status=?,result=?,updated=? WHERE id=?", (status or row["status"], result if result is not None else row["result"], now, task_id)); self.db.commit()

    def get(self, task_id: str):
        r=self.db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone(); return self._row(r) if r else None

    def list(self, status: str | None = None, limit: int = 100):
        q="SELECT * FROM tasks"; args=[]
        if status: q += " WHERE status=?"; args.append(status)
        q += " ORDER BY priority DESC, created ASC LIMIT ?"; args.append(max(1,min(limit,500)))
        return [self._row(r) for r in self.db.execute(q,args).fetchall()]

    def claim(self, agent: str | None = None):
        for task in self.list("queued", 50):
            deps=task["depends_on"]
            if any((self.get(x) or {}).get("status") != "completed" for x in deps): continue
            self.update(task["id"], "running"); task["status"]="running"; task["agent"] = agent or task["agent"]; return task
        return None

    @staticmethod
    def _row(r):
        return {"id":r["id"],"title":r["title"],"description":r["description"],"status":r["status"],"agent":r["agent"],"priority":r["priority"],"parent_id":r["parent_id"],"depends_on":json.loads(r["depends_on"]),"result":r["result"],"created":r["created"],"updated":r["updated"]}

    def close(self): self.db.close()
