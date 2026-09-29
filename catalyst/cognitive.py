from __future__ import annotations
import hashlib, json, sqlite3, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class CognitiveStateStore:
    """Durable high-level state for Catalyst's continuous mind.

    Stores the current focus, active objectives, recent outcomes and stable
    self-observations. It complements long-term memory rather than replacing it.
    """
    def __init__(self, path='catalyst_data/cognitive_state.db'):
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(p, check_same_thread=False, timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000'); self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS objectives(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,priority REAL NOT NULL,metadata TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,session_id TEXT,summary TEXT NOT NULL,outcome TEXT NOT NULL,metadata TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_objectives_status ON objectives(status,priority,updated_at)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at)')
        self.db.commit()

    def set(self,key,value):
        now=datetime.now(timezone.utc).isoformat(); payload=json.dumps(value,ensure_ascii=False)
        self.db.execute('INSERT INTO state(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,payload,now)); self.db.commit()

    def get(self,key,default=None):
        r=self.db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
        if not r:return default
        try:return json.loads(r['value'])
        except Exception:return default

    def objective(self,title,status='active',priority=.7,metadata=None):
        clean=str(title).strip(); oid=hashlib.sha256(clean.lower().encode()).hexdigest()[:32]; now=datetime.now(timezone.utc).isoformat()
        self.db.execute('''INSERT INTO objectives(id,created_at,updated_at,title,status,priority,metadata) VALUES(?,?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,status=excluded.status,priority=MAX(priority,excluded.priority),metadata=excluded.metadata''',
                        (oid,now,now,clean,status,max(0,min(1,float(priority))),json.dumps(metadata or {},ensure_ascii=False)))
        self.db.commit(); return oid

    def update_objective(self,oid,status):
        if status not in {'active','paused','completed','cancelled'}: raise ValueError('invalid objective status')
        now=datetime.now(timezone.utc).isoformat(); cur=self.db.execute('UPDATE objectives SET status=?,updated_at=? WHERE id=?',(status,now,oid)); self.db.commit(); return cur.rowcount>0

    def active_objectives(self,limit=20):
        rows=self.db.execute('SELECT * FROM objectives WHERE status IN (\'active\',\'paused\') ORDER BY priority DESC,updated_at DESC LIMIT ?',(max(1,min(100,int(limit))),)).fetchall()
        return [self._obj(r) for r in rows]

    def episode(self,summary,outcome='completed',session_id=None,metadata=None):
        now=datetime.now(timezone.utc).isoformat(); eid=hashlib.sha256((now+'\0'+str(summary)).encode()).hexdigest()
        self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?)',(eid,now,session_id,str(summary).strip(),str(outcome),json.dumps(metadata or {},ensure_ascii=False))); self.db.commit(); return eid

    def recent_episodes(self,limit=8):
        rows=self.db.execute('SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?',(max(1,min(50,int(limit))),)).fetchall(); return [dict(r) | {'metadata':json.loads(r['metadata'] or '{}')} for r in rows]

    def context(self,limit=8):
        focus=self.get('focus',{}) or {}; current=self.get('current_task',''); objectives=self.active_objectives(limit); episodes=self.recent_episodes(limit)
        lines=[]
        if current: lines.append(f'- CURRENT TASK: {current}')
        if focus: lines.append('- FOCUS: '+json.dumps(focus,ensure_ascii=False)[:3000])
        for o in objectives: lines.append(f'- ACTIVE OBJECTIVE [{o["status"]}/{o["priority"]:.2f}]: {o["title"]}')
        for e in episodes: lines.append(f'- RECENT EXPERIENCE [{e["outcome"]}]: {e["summary"][:1800]}')
        return '\n'.join(lines)

    @staticmethod
    def _obj(r):
        d=dict(r); d['metadata']=json.loads(d['metadata'] or '{}'); return d

    def stats(self):
        return {
            'current_task': bool(self.get('current_task')),
            'active_objectives': int(self.db.execute("SELECT COUNT(*) FROM objectives WHERE status IN ('active','paused')").fetchone()[0]),
            'episodes': int(self.db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]),
            'state_keys': int(self.db.execute('SELECT COUNT(*) FROM state').fetchone()[0]),
        }

    def close(self): self.db.close()

class CognitiveLoop:
    """Connects memory, working state, world state and outcomes into one turn lifecycle."""
    def __init__(self,mind,knowledge,working_memory,state,situational=None,world_model=None):
        self.mind=mind; self.knowledge=knowledge; self.working=working_memory; self.state=state; self.situational=situational; self.world=world_model

    def before_turn(self,user_text,session_id=None):
        self.state.set('current_task', str(user_text).strip()[:4000])
        try:self.mind.extract_explicit(user_text,session_id)
        except Exception:pass
        if self.situational:
            try:self.situational.scan()
            except Exception:pass
        return self.state.context(8)

    def after_turn(self,user_text,answer,session_id=None,tools=None,verified=False,steps=0):
        # Explicit memory is authoritative; generic turns become experience rather than facts.
        try:self.mind.extract_explicit(user_text,session_id)
        except Exception:pass
        summary=f"Request: {str(user_text)[:900]} | Result: {str(answer)[:1600]}"
        outcome='verified' if verified else ('completed' if answer else 'failed')
        try:self.state.episode(summary,outcome,session_id,{'tools':tools or [],'steps':steps})
        except Exception:pass
        try:self.knowledge.record_event('cognitive_turn',summary,{'session_id':session_id,'tools':tools or [],'verified':verified},.55)
        except Exception:pass
        try:self.working.append('experience',summary,{'verified':verified,'tools':tools or []})
        except Exception:pass
        return self.state.context(8)
