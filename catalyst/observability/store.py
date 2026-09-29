import json, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class ObservabilityStore:
    """Small, dependency-free trace/metric store for Catalyst operations."""
    def __init__(self, path='catalyst_data/observability.db'):
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute("""CREATE TABLE IF NOT EXISTS spans(
            id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, operation TEXT NOT NULL,
            started_at TEXT NOT NULL, duration_ms REAL, status TEXT NOT NULL,
            metadata TEXT NOT NULL, error TEXT)""")
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_spans_time ON spans(started_at)')
        self.db.execute("""CREATE TABLE IF NOT EXISTS counters(
            name TEXT PRIMARY KEY, value REAL NOT NULL, updated_at TEXT NOT NULL)""")
        self.db.commit()
    def start_span(self, operation, trace_id=None, metadata=None):
        sid=uuid4().hex; tid=trace_id or uuid4().hex
        started=datetime.now(timezone.utc).isoformat()
        started_mono=time.perf_counter()
        return {'id':sid,'trace_id':tid,'operation':operation,'started_at':started,'started_mono':started_mono,'metadata':metadata or {}}
    def end_span(self, span, status='ok', error=None):
        dur=round((time.perf_counter()-span['started_mono'])*1000,3)
        self.db.execute('INSERT OR REPLACE INTO spans VALUES(?,?,?,?,?,?,?,?)',
            (span['id'],span['trace_id'],span['operation'],span['started_at'],dur,status,json.dumps(span['metadata'],ensure_ascii=False),error))
        self.db.commit()
        return {'trace_id':span['trace_id'],'span_id':span['id'],'duration_ms':dur,'status':status}
    def incr(self,name,amount=1):
        now=datetime.now(timezone.utc).isoformat()
        self.db.execute('INSERT INTO counters(name,value,updated_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET value=value+excluded.value,updated_at=excluded.updated_at',(name,float(amount),now)); self.db.commit()
    def recent(self,limit=200):
        rows=self.db.execute('SELECT * FROM spans ORDER BY started_at DESC LIMIT ?',(max(1,min(limit,1000)),)).fetchall()
        return [{**dict(r),'metadata':json.loads(r['metadata'])} for r in rows]
    def counters(self): return [dict(r) for r in self.db.execute('SELECT * FROM counters ORDER BY name').fetchall()]
    def summary(self):
        rows=self.db.execute('SELECT status,COUNT(*) n,AVG(duration_ms) avg_ms FROM spans GROUP BY status').fetchall()
        return {'spans':[{ 'status':r['status'],'count':r['n'],'avg_duration_ms':round(r['avg_ms'] or 0,3)} for r in rows], 'counters':self.counters()}
    def close(self): self.db.close()
