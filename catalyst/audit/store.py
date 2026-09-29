import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AuditStore:
    def __init__(self, path: str):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, event TEXT NOT NULL, actor TEXT NOT NULL, details TEXT NOT NULL)")
        self.db.commit()

    def log(self, event: str, actor: str = "catalyst", details: dict[str, Any] | None = None) -> int:
        cur = self.db.execute("INSERT INTO audit(ts,event,actor,details) VALUES(?,?,?,?)", (datetime.now(timezone.utc).isoformat(), event, actor, json.dumps(details or {}, ensure_ascii=False)))
        self.db.commit(); return int(cur.lastrowid)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        return [{"id": r["id"], "ts": r["ts"], "event": r["event"], "actor": r["actor"], "details": json.loads(r["details"])} for r in rows]

    def close(self) -> None:
        self.db.close()
