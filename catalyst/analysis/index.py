import math,re,sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

class ChunkIndex:
    """Lightweight hybrid lexical index: filename/heading/body tokens + hashed term vectors."""
    def __init__(self,path:str):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, path TEXT, chunk_no INTEGER, content TEXT, tokens TEXT, sha256 TEXT UNIQUE)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)"); self.db.commit()
    def rebuild(self,files:list[tuple[str,str,str]]):
        import hashlib,json
        self.db.execute("DELETE FROM chunks")
        for path,text,digest in files:
            parts=self._split(text,18000)
            for i,part in enumerate(parts):
                toks=Counter(self._tokens(part)); key=hashlib.sha256((digest+str(i)).encode()).hexdigest()
                self.db.execute("INSERT OR REPLACE INTO chunks(path,chunk_no,content,tokens,sha256) VALUES(?,?,?,?,?)",(path,i,part,json.dumps(toks),key))
        self.db.commit(); return sum(1 for _ in self.db.execute("SELECT 1 FROM chunks"))
    def search(self,q:str,limit:int=12):
        terms=set(self._tokens(q)); scored=[]
        for r in self.db.execute("SELECT * FROM chunks").fetchall():
            rt={k:v for k,v in __import__('json').loads(r['tokens']).items()}; score=sum(min(rt.get(t,0),3) for t in terms)
            if score: scored.append((score,r))
        scored.sort(key=lambda x:x[0],reverse=True)
        return [{"path":r["path"],"chunk":r["chunk_no"],"content":r["content"],"score":s} for s,r in scored[:limit]]
    @staticmethod
    def _tokens(text): return re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}",text.lower())
    @staticmethod
    def _split(text,size): return [text[i:i+size] for i in range(0,len(text),size)] or [""]
    def close(self): self.db.close()
