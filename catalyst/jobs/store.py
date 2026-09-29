import json, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

class JobStore:
    def __init__(self, path: str):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
            payload TEXT NOT NULL, result TEXT, error TEXT, created_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT, checkpoint TEXT,
            attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 2,
            next_retry_at TEXT)
        """)
        cols = {r[1] for r in self.db.execute('PRAGMA table_info(jobs)').fetchall()}
        if 'attempts' not in cols:
            self.db.execute("ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if 'max_attempts' not in cols:
            self.db.execute("ALTER TABLE jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 2")
        if 'next_retry_at' not in cols:
            self.db.execute("ALTER TABLE jobs ADD COLUMN next_retry_at TEXT")
        self.db.commit()
        # Jobs left running by a process crash are safely re-queued for recovery.
        self.db.execute("UPDATE jobs SET status='queued', started_at=NULL WHERE status='running'")
        self.db.commit()

    def create(self, kind: str, payload: dict, max_attempts: int = 2):
        jid = uuid4().hex; now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO jobs(id,kind,status,payload,created_at,attempts,max_attempts) VALUES(?,?,?,?,?,0,?)",
            (jid, kind, 'queued', json.dumps(payload, ensure_ascii=False), now, max(1, int(max_attempts)))
        )
        self.db.commit(); return jid

    def get(self, jid):
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(); return dict(row) if row else None

    def list(self, status=None):
        q = "SELECT * FROM jobs"; args = ()
        if status:
            q += " WHERE status=?"; args = (status,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY created_at DESC", args).fetchall()]

    def claim_next(self, worker_id: str):
        """Atomically claim one queued job so multiple workers/processes don't double-run it."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT id FROM jobs WHERE status='queued' AND (next_retry_at IS NULL OR next_retry_at<=?) ORDER BY created_at LIMIT 1",
                (now,)
            ).fetchone()
            if not row:
                self.db.commit(); return None
            jid = row[0]
            self.db.execute(
                "UPDATE jobs SET status='running',started_at=?,attempts=attempts+1 WHERE id=? AND status='queued'",
                (now, jid)
            )
            self.db.commit()
            job = self.get(jid)
            if job: job['worker_id'] = worker_id
            return job
        except Exception:
            self.db.rollback(); raise

    def start(self, jid):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute("UPDATE jobs SET status='running',started_at=? WHERE id=?", (now, jid)); self.db.commit()

    def checkpoint(self, jid, data):
        self.db.execute("UPDATE jobs SET checkpoint=? WHERE id=?", (json.dumps(data, ensure_ascii=False), jid)); self.db.commit()

    def finish(self, jid, status, result=None, error=None):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE jobs SET status=?,result=?,error=?,finished_at=?,next_retry_at=NULL WHERE id=?",
            (status, json.dumps(result, ensure_ascii=False) if result is not None else None, error, now, jid)
        ); self.db.commit()

    def fail_or_retry(self, jid, error, backoff_seconds=15):
        row = self.get(jid)
        if not row:
            return None
        now = datetime.now(timezone.utc)
        attempts = int(row.get('attempts') or 0)
        max_attempts = int(row.get('max_attempts') or 1)
        if attempts < max_attempts:
            delay = max(1, int(backoff_seconds)) * (2 ** max(0, attempts - 1))
            retry_at = (now + timedelta(seconds=min(delay, 3600))).isoformat()
            self.db.execute(
                "UPDATE jobs SET status='queued',error=?,finished_at=?,started_at=NULL,next_retry_at=? WHERE id=?",
                (error, now.isoformat(), retry_at, jid)
            )
            self.db.commit()
            return 'queued'
        self.finish(jid, 'failed', error=error)
        return 'failed'

    def resume_payload(self, jid):
        row = self.get(jid)
        if not row: return None
        payload = json.loads(row['payload']); checkpoint = json.loads(row['checkpoint']) if row['checkpoint'] else None
        return payload, checkpoint

    def cancel(self, jid):
        row=self.get(jid)
        if not row: return None
        if row['status'] in {'completed','failed','cancelled'}: return row
        self.db.execute("UPDATE jobs SET status='cancelled',finished_at=?,error=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),'cancelled by creator',jid));self.db.commit();return self.get(jid)

    def retry(self, jid):
        self.db.execute(
            "UPDATE jobs SET status='queued',error=NULL,finished_at=NULL,started_at=NULL,next_retry_at=NULL WHERE id=? AND status IN ('failed','completed')",
            (jid,)
        ); self.db.commit()

    def close(self): self.db.close()
