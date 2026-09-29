from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


_SECRET = re.compile(r"(?i)(api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*\S+")


def _safe(value: str, limit: int = 6000) -> str:
    text = str(value or "").strip()
    text = _SECRET.sub("[REDACTED SECRET]", text)
    return text[:limit]


class LearningLedger:
    """Durable, evidence-gated learning for Catalyst's generalist behavior.

    Catalyst does not silently retrain a model or rewrite its constitution. It
    records verified outcomes and reusable lessons, then retrieves them as
    advisory context for future planning. This makes improvement observable,
    reversible, and compatible with any model provider.
    """

    def __init__(self, path="catalyst_data/learning.db"):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS learning_events(
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, query TEXT NOT NULL,
            domain TEXT NOT NULL, status TEXT NOT NULL, verified INTEGER NOT NULL,
            tools TEXT NOT NULL, outcome TEXT NOT NULL, lesson TEXT NOT NULL,
            confidence REAL NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_learning_domain ON learning_events(domain,created_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_learning_verified ON learning_events(verified,created_at)")
        self.db.commit()

    @staticmethod
    def _domain(query: str, tools: list[str] | None = None) -> str:
        text = (query or "").lower()
        if any(x in text for x in ("code", "repo", "bug", "test", "implement", "software")): return "engineering"
        if any(x in text for x in ("research", "source", "latest", "investigate")): return "research"
        if any(x in text for x in ("file", "folder", "browser", "website", "click")): return "computer_use"
        if any(x in text for x in ("voice", "audio", "speak", "listen")): return "voice"
        if any(x in text for x in ("image", "video", "story", "media")): return "creative"
        if tools:
            return str(tools[0]).split(".")[0][:48] or "general"
        return "general"

    def record_outcome(self, query: str, outcome: str, *, verified=False,
                       tools=None, status="completed", lesson=None,
                       metadata=None, confidence=None) -> str | None:
        tools = [str(x) for x in (tools or [])]
        # Only outcomes with verification or observable tool interaction enter
        # the learning ledger. Unverified prose is not treated as experience.
        if not verified and not tools:
            return None
        query = _safe(query, 3000)
        outcome = _safe(outcome, 6000)
        if not query or not outcome:
            return None
        domain = self._domain(query, tools)
        if lesson is None:
            lesson = (f"For {domain} tasks, preserve the evidence boundary and reuse the observed approach: "
                      f"{outcome[:700]}")
        now = datetime.now(timezone.utc).isoformat()
        eid = uuid4().hex
        score = float(confidence if confidence is not None else (.92 if verified else .62))
        self.db.execute("INSERT INTO learning_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            eid, now, query, domain, status, 1 if verified else 0,
            json.dumps(tools), outcome, _safe(lesson, 2500), max(0, min(1, score)),
            json.dumps(metadata or {}, ensure_ascii=False)))
        self.db.commit()
        return eid

    def search(self, query: str, limit=8) -> list[dict]:
        terms = [x.lower() for x in re.findall(r"[\w.-]{2,}", query or "")][:16]
        rows = self.db.execute("SELECT * FROM learning_events WHERE verified=1 ORDER BY created_at DESC LIMIT 2000").fetchall()
        scored = []
        for row in rows:
            haystack = f"{row['query']} {row['domain']} {row['lesson']} {row['outcome']}".lower()
            hits = sum(term in haystack for term in terms)
            if terms and not hits:
                continue
            score = (hits / len(terms) if terms else 0.1) * .65 + float(row['confidence']) * .25 + .1
            scored.append((score, row))
        scored.sort(key=lambda item: (item[0], item[1]['created_at']), reverse=True)
        return [self._row(row) for _, row in scored[:max(1, min(int(limit), 50))]]

    def context(self, query: str, limit=6) -> str:
        rows = self.search(query, limit)
        return "\n".join(f"- LEARNED [{row['domain']}]: {row['lesson']}" for row in rows)

    def stats(self) -> dict:
        total = int(self.db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0])
        verified = int(self.db.execute("SELECT COUNT(*) FROM learning_events WHERE verified=1").fetchone()[0])
        domains = self.db.execute("SELECT domain,COUNT(*) FROM learning_events GROUP BY domain ORDER BY COUNT(*) DESC").fetchall()
        return {"total": total, "verified": verified, "verified_rate": round(verified / total, 3) if total else 0.0,
                "by_domain": {row[0]: int(row[1]) for row in domains}}

    def self_evaluation(self) -> dict:
        stats = self.stats()
        weak = [domain for domain, count in stats["by_domain"].items() if count < 2]
        return {"status": "evidence-gated", "stats": stats,
                "underrepresented_domains": weak,
                "next_step": "Collect more verified outcomes in underrepresented domains." if weak else "Continue testing cross-domain transfer.",
                "model_retraining": False}

    @staticmethod
    def _row(row):
        value = dict(row)
        value["verified"] = bool(value["verified"])
        value["tools"] = json.loads(value["tools"] or "[]")
        value["metadata"] = json.loads(value["metadata"] or "{}")
        return value

    def close(self):
        self.db.close()
