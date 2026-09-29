import json, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class MemoryStore:
    """Durable memory with lexical recall, recency weighting, dedupe, and consolidation markers."""
    def __init__(self,path:str):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000'); self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute("CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,ts TEXT NOT NULL,kind TEXT NOT NULL,text TEXT NOT NULL,metadata TEXT NOT NULL DEFAULT '{}')")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_memories_ts ON memories(ts)")
        cols={r[1] for r in self.db.execute('PRAGMA table_info(memories)').fetchall()}
        if 'importance' not in cols: self.db.execute("ALTER TABLE memories ADD COLUMN importance REAL NOT NULL DEFAULT 0.5")
        if 'archived' not in cols: self.db.execute("ALTER TABLE memories ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
        self.db.commit(); self._fts=False
        try:
            self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text,content='memories',content_rowid='id')")
            self.db.execute("CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN INSERT INTO memory_fts(rowid,text) VALUES(new.id,new.text); END")
            self.db.execute("CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN INSERT INTO memory_fts(memory_fts,rowid,text) VALUES('delete',old.id,old.text); INSERT INTO memory_fts(rowid,text) VALUES(new.id,new.text); END")
            self.db.commit(); self._fts=True
        except sqlite3.OperationalError: pass

    @staticmethod
    def _norm(text:str)->str:
        return re.sub(r'\s+',' ',(text or '').strip().lower())

    def add(self,text,kind='note',metadata=None,importance=0.5,dedupe=True):
        text=str(text).strip()
        if not text: return None
        metadata=dict(metadata or {}); importance=max(0.0,min(1.0,float(importance)))
        norm=self._norm(text)
        if dedupe:
            recent=self.db.execute("SELECT id,text,importance FROM memories WHERE archived=0 ORDER BY id DESC LIMIT 1000").fetchall()
            for row in recent:
                if self._norm(row['text']) == norm:
                    self.db.execute("UPDATE memories SET importance=MAX(importance,?),kind=?,metadata=? WHERE id=?",(importance,kind,json.dumps(metadata,ensure_ascii=False),row['id'])); self.db.commit(); return int(row['id'])
        cur=self.db.execute("INSERT INTO memories(ts,kind,text,metadata,importance,archived) VALUES(?,?,?,?,?,0)",(datetime.now(timezone.utc).isoformat(),kind,text,json.dumps(metadata,ensure_ascii=False),importance)); self.db.commit(); return int(cur.lastrowid)

    def search(self,query,limit=12):
        limit=max(1,min(int(limit),50)); query=(query or '').strip()
        if not query:return []
        qterms=[w.lower() for w in re.findall(r'[\w.-]{2,}',query)][:20]
        if not qterms:return []
        rows=[]
        if self._fts:
            match=' OR '.join(f'"{w}"' for w in qterms)
            try:
                rows=self.db.execute("SELECT m.*, bm25(memory_fts) AS rank FROM memory_fts f JOIN memories m ON m.id=f.rowid WHERE memory_fts MATCH ? AND m.archived=0 LIMIT ?",(match, min(limit*6,300))).fetchall()
            except sqlite3.OperationalError: rows=[]
        if not rows:
            rows=self.db.execute("SELECT * FROM memories WHERE archived=0 ORDER BY id DESC LIMIT 5000").fetchall()
        now=datetime.now(timezone.utc)
        scored=[]
        for r in rows:
            text=(r['text'] or '').lower(); hits=sum(t in text for t in qterms)
            if hits==0: continue
            try: age_days=max(0.0,(now-datetime.fromisoformat(r['ts'])).total_seconds()/86400)
            except Exception: age_days=30.0
            recency=1.0/(1.0+age_days/14.0)
            importance=float(r['importance']) if 'importance' in r.keys() else 0.5
            lexical=hits/len(qterms)
            fts_bonus=0.0
            if 'rank' in r.keys() and r['rank'] is not None:
                fts_bonus=1.0/(1.0+max(0.0,float(r['rank'])))
            score=0.60*lexical+0.20*recency+0.15*importance+0.05*fts_bonus
            scored.append((score,int(r['id']),r))
        scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
        return [self._row(r) for _,_,r in scored[:limit]]

    def consolidate(self,limit=200):
        """Archive exact duplicates while preserving the newest/highest-importance memory."""
        rows=self.db.execute("SELECT * FROM memories WHERE archived=0 ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),2000)),)).fetchall()
        seen={}; archived=0
        for r in rows:
            key=(r['kind'],self._norm(r['text']))
            if key in seen:
                keep=seen[key]
                if float(r['importance'])>float(keep['importance']):
                    self.db.execute('UPDATE memories SET archived=1 WHERE id=?',(keep['id'],)); seen[key]=r
                    archived+=1
                else:
                    self.db.execute('UPDATE memories SET archived=1 WHERE id=?',(r['id'],)); archived+=1
            else: seen[key]=r
        self.db.commit()
        return {'scanned':len(rows),'archived':archived,'active':len(seen)}

    def archive(self,memory_id:int):
        self.db.execute('UPDATE memories SET archived=1 WHERE id=?',(int(memory_id),)); self.db.commit(); return self.get(memory_id)

    def get(self,memory_id:int):
        r=self.db.execute('SELECT * FROM memories WHERE id=?',(int(memory_id),)).fetchone(); return self._row(r) if r else None

    def recent_active(self,limit=1000):
        rows=self.db.execute('SELECT * FROM memories WHERE archived=0 ORDER BY id DESC LIMIT ?',(max(1,min(int(limit),5000)),)).fetchall()
        return [self._row(r) for r in rows]

    def stats(self):
        rows=self.db.execute('SELECT kind, COUNT(*) FROM memories WHERE archived=0 GROUP BY kind ORDER BY COUNT(*) DESC').fetchall()
        total=sum(int(r[1]) for r in rows)
        archived=int(self.db.execute('SELECT COUNT(*) FROM memories WHERE archived=1').fetchone()[0])
        return {'total':total,'archived':archived,'by_kind':{r[0]:int(r[1]) for r in rows}}

    def close(self): self.db.close()
    @staticmethod
    def _row(row):
        if row is None:return None
        return {'id':row['id'],'timestamp':row['ts'],'kind':row['kind'],'text':row['text'],'metadata':json.loads(row['metadata'] or '{}'),'importance':float(row['importance']) if 'importance' in row.keys() else 0.5,'archived':bool(row['archived']) if 'archived' in row.keys() else False}
