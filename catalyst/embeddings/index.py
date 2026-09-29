import json, math, sqlite3, struct
from pathlib import Path

class EmbeddingIndex:
    """Optional provider-backed vector index. Falls back cleanly when embeddings are unavailable."""
    def __init__(self, path: str):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS embeddings(id INTEGER PRIMARY KEY, namespace TEXT NOT NULL, ref TEXT NOT NULL, text TEXT NOT NULL, vector BLOB NOT NULL, UNIQUE(namespace,ref))")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_ns ON embeddings(namespace)"); self.db.commit()
    @staticmethod
    def _pack(vec): return struct.pack(f'<{len(vec)}f', *vec)
    @staticmethod
    def _unpack(blob): return list(struct.unpack(f'<{len(blob)//4}f', blob))
    @staticmethod
    def cosine(a,b):
        if not a or not b or len(a)!=len(b): return 0.0
        dot=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
        return dot/(na*nb) if na and nb else 0.0
    def upsert(self, namespace, ref, text, vector):
        self.db.execute("INSERT INTO embeddings(namespace,ref,text,vector) VALUES(?,?,?,?) ON CONFLICT(namespace,ref) DO UPDATE SET text=excluded.text, vector=excluded.vector",(namespace,ref,text,self._pack(vector))); self.db.commit()
    def search(self, namespace, vector, limit=12):
        rows=[]
        for r in self.db.execute("SELECT * FROM embeddings WHERE namespace=?",(namespace,)):
            score=self.cosine(vector,self._unpack(r['vector'])); rows.append((score,r))
        rows.sort(key=lambda x:x[0],reverse=True)
        return [{"ref":r['ref'],"text":r['text'],"score":round(s,6)} for s,r in rows[:max(1,min(limit,50))]]
    def count(self, namespace=None):
        if namespace is None: return int(self.db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0])
        return int(self.db.execute('SELECT COUNT(*) FROM embeddings WHERE namespace=?',(namespace,)).fetchone()[0])
    def close(self): self.db.close()
