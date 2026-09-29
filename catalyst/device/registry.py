import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class DeviceRegistry:
    """Durable registry for Catalyst clients/shells with per-device credentials."""

    def __init__(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS devices("
            "id TEXT PRIMARY KEY,name TEXT NOT NULL,platform TEXT NOT NULL,version TEXT,"
            "capabilities TEXT NOT NULL,last_seen TEXT NOT NULL,metadata TEXT NOT NULL,token_hash TEXT)"
        )
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(devices)").fetchall()}
        if "token_hash" not in cols:
            self.db.execute("ALTER TABLE devices ADD COLUMN token_hash TEXT")
        self.db.commit()

    def register(self, name, platform, version="", capabilities=None, metadata=None, device_id=None):
        did = device_id or uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        caps = sorted(set(str(x) for x in (capabilities or [])))
        self.db.execute(
            "INSERT INTO devices(id,name,platform,version,capabilities,last_seen,metadata,token_hash) "
            "VALUES(?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,"
            "version=excluded.version,capabilities=excluded.capabilities,last_seen=excluded.last_seen,"
            "metadata=excluded.metadata",
            (did, name[:120], platform[:40], version[:40], json.dumps(caps), now, json.dumps(metadata or {})),
        )
        self.db.commit()
        return did

    def issue_token(self, device_id) -> str:
        if not self.get(device_id):
            raise ValueError("Unknown device")
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.db.execute("UPDATE devices SET token_hash=? WHERE id=?", (digest, device_id))
        self.db.commit()
        return token

    def authenticate(self, device_id, token) -> bool:
        row = self.db.execute("SELECT token_hash FROM devices WHERE id=?", (device_id,)).fetchone()
        if not row or not row["token_hash"] or not token:
            return False
        digest = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        return secrets.compare_digest(str(row["token_hash"]), digest)

    def heartbeat(self, device_id, metadata=None):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute("UPDATE devices SET last_seen=?,metadata=? WHERE id=?", (now, json.dumps(metadata or {}), device_id))
        self.db.commit()
        return self.get(device_id)

    def get(self, device_id):
        r = self.db.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        return self._row(r) if r else None

    def list(self):
        return [self._row(r) for r in self.db.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()]

    def _row(self, r):
        d = dict(r)
        d.pop("token_hash", None)
        d["capabilities"] = json.loads(d["capabilities"])
        d["metadata"] = json.loads(d["metadata"])
        return d

    def close(self):
        self.db.close()
