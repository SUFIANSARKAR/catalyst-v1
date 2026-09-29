from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*\S+"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,}\b"),
]


def _safe(text: str) -> str:
    value = str(text or "").strip()
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[REDACTED SECRET]", value)
    return value[:12000]


class CatalystMind:
    """Persistent cognitive state layered over Catalyst's existing memory.

    Memory is append-only by default. Explicit forgetting is required to remove a
    cognitive item. This store keeps durable facts, preferences, decisions,
    commitments, goals and cross-session episode summaries separate from the
    short-lived conversation transcript.
    """
    KINDS = {"fact", "preference", "decision", "commitment", "goal", "episode"}

    def __init__(self, path="catalyst_data/mind.db", memory=None):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS cognitive_memory(
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            kind TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT .7, importance REAL NOT NULL DEFAULT .7,
            pinned INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL DEFAULT '{}'
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_kind ON cognitive_memory(kind,updated_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_pinned ON cognitive_memory(pinned,updated_at)")
        self.db.commit()
        self.memory = memory

    def ensure_core_identity(self) -> list[str]:
        """Install durable identity anchors for every Catalyst deployment.

        These anchors live in the same cognitive database as user-approved
        memories, so Catalyst's identity and mission survive model, frontend,
        and process changes. ``remember`` is idempotent because the IDs are
        derived from the content.
        """
        anchors = [
            ("fact", "Catalyst is a female artificial intelligence with a warm, intelligent, composed, and conversational identity.", "system:identity"),
            ("goal", "Catalyst's long-term mission is to become a Catalyst-level personal AI: understand context, remember what matters, plan safely, act through governed tools, verify outcomes, and communicate naturally.", "system:catalyst-mission"),
        ]
        ids = []
        for kind, text, source in anchors:
            mid = self.remember(kind, text, source=source, confidence=1.0,
                                importance=1.0, pinned=True,
                                metadata={"system_anchor": True, "permanent": True})
            if mid:
                ids.append(mid)
        return ids

    @staticmethod
    def _id(kind: str, text: str) -> str:
        return hashlib.sha256((kind + "\0" + text.strip().lower()).encode()).hexdigest()

    def remember(self, kind: str, text: str, *, source="conversation", confidence=.75,
                 importance=.75, pinned=False, metadata=None) -> str | None:
        if kind not in self.KINDS:
            raise ValueError(f"invalid cognitive memory kind: {kind}")
        text = _safe(text)
        if not text or text == "[REDACTED SECRET]":
            return None
        now = datetime.now(timezone.utc).isoformat()
        mid = self._id(kind, text)
        row = self.db.execute("SELECT id FROM cognitive_memory WHERE id=?", (mid,)).fetchone()
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        if row:
            self.db.execute("""UPDATE cognitive_memory SET updated_at=?, confidence=MAX(confidence,?),
                importance=MAX(importance,?), pinned=MAX(pinned,?), metadata=? WHERE id=?""",
                (now, float(confidence), float(importance), 1 if pinned else 0, payload, mid))
        else:
            self.db.execute("INSERT INTO cognitive_memory VALUES(?,?,?,?,?,?,?,?,?,?)",
                (mid, now, now, kind, text, source, max(0,min(1,float(confidence))),
                 max(0,min(1,float(importance))), 1 if pinned else 0, payload))
        self.db.commit()
        if self.memory:
            try:
                self.memory.add(text, f"mind_{kind}", {"mind_id": mid, "source": source, **(metadata or {})},
                                max(.5, float(importance)))
            except Exception:
                pass
        return mid

    def search(self, query: str, limit=18) -> list[dict[str, Any]]:
        terms = [x.lower() for x in re.findall(r"[\w.-]{2,}", query or "")][:16]
        if not terms:
            return self.recent(limit)
        rows = self.db.execute("SELECT * FROM cognitive_memory ORDER BY pinned DESC, updated_at DESC LIMIT 2000").fetchall()
        scored=[]
        for r in rows:
            text=r["text"].lower(); hits=sum(t in text for t in terms)
            if hits:
                score=.55*(hits/len(terms))+.2*float(r["confidence"])+.15*float(r["importance"])+.1*int(r["pinned"])
                scored.append((score,r))
        scored.sort(key=lambda x:(x[0],x[1]["updated_at"]), reverse=True)
        return [self._row(r) for _,r in scored[:max(1,min(int(limit),100))]]

    def recent(self, limit=30):
        rows=self.db.execute("SELECT * FROM cognitive_memory ORDER BY pinned DESC, updated_at DESC LIMIT ?",
                             (max(1,min(int(limit),200)),)).fetchall()
        return [self._row(r) for r in rows]

    def active(self, limit=40):
        kinds=("fact","preference","decision","commitment","goal")
        rows=self.db.execute("SELECT * FROM cognitive_memory WHERE kind IN (?,?,?,?,?) ORDER BY pinned DESC, importance DESC, updated_at DESC LIMIT ?",
                             (*kinds,max(1,min(int(limit),200)))).fetchall()
        return [self._row(r) for r in rows]

    def extract_explicit(self, user_text: str, session_id=None) -> list[str]:
        """Conservative extraction of durable statements; never treats arbitrary text as fact."""
        text=_safe(user_text)
        found=[]
        patterns=[
            ("preference", r"\b(?:i|we)\s+(?:prefer|like|love|hate|don't like|do not like)\s+(.+)$"),
            ("fact", r"\bmy\s+(?:name|project|goal|job|role|device)\s+is\s+(.+)$"),
            ("decision", r"\b(?:we|i)\s+(?:decided|have decided|chose|choose)\s+(?:to\s+)?(.+)$"),
            ("commitment", r"\b(?:we|i)\s+(?:need to|must|will|are going to)\s+(.+)$"),
            ("goal", r"\b(?:our|my|the)\s+goal\s+is\s+(.+)$"),
        ]
        lower=text.lower()
        for kind,pat in patterns:
            m=re.search(pat,text,re.I)
            if m:
                value=m.group(1).strip().rstrip(".!?")
                if len(value)>=3 and len(value)<=1000:
                    mid=self.remember(kind, f"{text}", source=f"conversation:{session_id or 'unknown'}",
                                      confidence=.88, importance=.85, pinned=True,
                                      metadata={"session_id":session_id,"extracted":"explicit"})
                    if mid: found.append(mid)
                    break
        # Explicit memory commands get a dedicated permanent record.
        m=re.match(r"(?is)^\s*(?:remember|memorize|keep this in memory)\s*[:,-]?\s*(.+)$", text)
        if m:
            value=m.group(1).strip()
            if len(value)>=3:
                mid=self.remember("fact", value, source=f"explicit:{session_id or 'unknown'}",
                                  confidence=1.0, importance=1.0, pinned=True,
                                  metadata={"session_id":session_id,"explicit":True})
                if mid: found.append(mid)
        return found

    def build_context(self, query: str, limit=24) -> str:
        rows=self.search(query,limit)
        active=self.active(18)
        merged={x["id"]:x for x in active}
        for x in rows: merged.setdefault(x["id"],x)
        ordered=sorted(merged.values(), key=lambda x:(-int(x["pinned"]),-float(x["importance"]),x["updated_at"]), reverse=False)
        lines=[]
        for x in ordered[:max(1,min(limit,50))]:
            flag="PERMANENT" if x["pinned"] else "DURABLE"
            lines.append(f'- MIND [{flag}/{x["kind"]}]: {x["text"]}')
        return "\n".join(lines)

    def forget(self, memory_id: str) -> bool:
        row=self.db.execute("SELECT id FROM cognitive_memory WHERE id=?",(memory_id,)).fetchone()
        if not row:return False
        self.db.execute("DELETE FROM cognitive_memory WHERE id=?",(memory_id,));self.db.commit();return True

    def stats(self):
        rows=self.db.execute("SELECT kind,COUNT(*) n FROM cognitive_memory GROUP BY kind").fetchall()
        return {"total":sum(int(r[1]) for r in rows),"by_kind":{r[0]:int(r[1]) for r in rows},
                "permanent":int(self.db.execute("SELECT COUNT(*) FROM cognitive_memory WHERE pinned=1").fetchone()[0])}

    @staticmethod
    def _row(r):
        d=dict(r);d["pinned"]=bool(d["pinned"]);d["metadata"]=json.loads(d["metadata"] or "{}");return d

    def close(self): self.db.close()
