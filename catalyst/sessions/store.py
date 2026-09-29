import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

class SessionStore:
    def __init__(self,root='catalyst_data/sessions'):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.index_path=self.root.parent/'sessions.db';self.db=sqlite3.connect(self.index_path,check_same_thread=False);self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0,summary TEXT NOT NULL DEFAULT '')")
        cols={r[1] for r in self.db.execute("PRAGMA table_info(sessions)").fetchall()}
        if 'summary' not in cols:
            self.db.execute("ALTER TABLE sessions ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
        self.db.commit()
    def create(self,title='New conversation'):
        sid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();(self.root/f'{sid}.jsonl').touch();self.db.execute("INSERT INTO sessions(id,title,created,updated,cancelled,summary) VALUES(?,?,?,?,0,'')",(sid,title[:120],now,now));self.db.commit();return sid
    def ensure(self,sid):return sid if sid and self.db.execute("SELECT 1 FROM sessions WHERE id=?",(sid,)).fetchone() else self.create()
    def append(self,sid,role,content,metadata=None):
        with (self.root/f'{sid}.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({"ts":datetime.now(timezone.utc).isoformat(),"role":role,"content":content,"metadata":metadata or {}},ensure_ascii=False)+'\n')
        self.db.execute("UPDATE sessions SET updated=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),sid));self.db.commit()
    def read(self,sid,limit=120):
        p=self.root/f'{sid}.jsonl';return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()[-limit:]] if p.exists() else []
    def list(self,limit=50):return [dict(r) for r in self.db.execute("SELECT id,title,created,updated,cancelled FROM sessions ORDER BY updated DESC LIMIT ?",(limit,)).fetchall()]
    def search(self,q,limit=30):
        q=(q or '').strip()
        if not q:return self.list(limit)
        like=f'%{q}%'
        rows=self.db.execute("SELECT id,title,created,updated,cancelled FROM sessions WHERE title LIKE ? OR summary LIKE ? ORDER BY updated DESC LIMIT ?",(like,like,limit)).fetchall()
        return [dict(r) for r in rows]
    def set_title(self,sid,title):
        self.db.execute("UPDATE sessions SET title=?,updated=? WHERE id=?",(title[:120] or 'Conversation',datetime.now(timezone.utc).isoformat(),sid));self.db.commit()
    def get_summary(self,sid):
        r=self.db.execute("SELECT summary FROM sessions WHERE id=?",(sid,)).fetchone();return r[0] if r else ''
    def set_summary(self,sid,summary):
        self.db.execute("UPDATE sessions SET summary=?,updated=? WHERE id=?",(summary,datetime.now(timezone.utc).isoformat(),sid));self.db.commit()
    def cancel(self,sid):self.db.execute("UPDATE sessions SET cancelled=1 WHERE id=?",(sid,));self.db.commit()
    def delete(self,sid):
        self.db.execute("DELETE FROM sessions WHERE id=?",(sid,)); self.db.commit()
        p=self.root/f'{sid}.jsonl'
        if p.exists(): p.unlink()
    def rename(self,sid,title): self.set_title(sid,title)
    def is_cancelled(self,sid):
        r=self.db.execute("SELECT cancelled FROM sessions WHERE id=?",(sid,)).fetchone();return bool(r and r[0])
    def close(self):self.db.close()
