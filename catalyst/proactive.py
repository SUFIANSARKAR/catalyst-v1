import json, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

@dataclass
class Signal:
    kind:str; source:str; title:str; detail:str; severity:float=.5; actionable:bool=True; metadata:dict|None=None
@dataclass
class Suggestion:
    id:str; title:str; rationale:str; action:str; confidence:float; urgency:float; status:str='pending'; created_at:str=''; metadata:dict|None=None

class SituationalStore:
    def __init__(self,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(p,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row; self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('CREATE TABLE IF NOT EXISTS signals(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,kind TEXT NOT NULL,source TEXT NOT NULL,title TEXT NOT NULL,detail TEXT NOT NULL,severity REAL NOT NULL,actionable INTEGER NOT NULL,metadata TEXT NOT NULL,fingerprint TEXT)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_signals_fingerprint ON signals(fingerprint,created_at)')
        self.db.execute('CREATE TABLE IF NOT EXISTS suggestions(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,title TEXT NOT NULL,rationale TEXT NOT NULL,action TEXT NOT NULL,confidence REAL NOT NULL,urgency REAL NOT NULL,status TEXT NOT NULL,metadata TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS focus(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL)'); self.db.commit()
    def add_signal(self,s):
        import hashlib
        now=datetime.now(timezone.utc); meta=s.metadata or {}; fp=hashlib.sha256(json.dumps([s.kind,s.source,s.title,meta],sort_keys=True,default=str).encode()).hexdigest(); cutoff=(now-timedelta(minutes=15)).isoformat(); row=self.db.execute('SELECT id FROM signals WHERE fingerprint=? AND created_at>? ORDER BY created_at DESC LIMIT 1',(fp,cutoff)).fetchone()
        if row:return row['id']
        sid=uuid4().hex; self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,now.isoformat(),s.kind,s.source,s.title,s.detail,float(max(0,min(1,s.severity))),1 if s.actionable else 0,json.dumps(meta),fp)); self.db.commit(); return sid
    def list_signals(self,limit=50):return [self._signal(r) for r in self.db.execute('SELECT * FROM signals ORDER BY created_at DESC LIMIT ?',(max(1,min(500,int(limit))),)).fetchall()]
    def add_suggestion(self,s):
        now=s.created_at or datetime.now(timezone.utc).isoformat(); self.db.execute('INSERT INTO suggestions VALUES(?,?,?,?,?,?,?,?,?)',(s.id,now,s.title,s.rationale,s.action,float(s.confidence),float(s.urgency),s.status,json.dumps(s.metadata or {}))); self.db.commit(); return s.id
    def update_suggestion(self,sid,status):
        if status not in {'approved','rejected','dismissed'}: raise ValueError('invalid suggestion status')
        self.db.execute('UPDATE suggestions SET status=? WHERE id=?',(status,sid)); self.db.commit(); return self.get_suggestion(sid)
    def get_suggestion(self,sid):
        r=self.db.execute('SELECT * FROM suggestions WHERE id=?',(sid,)).fetchone(); return self._suggestion(r) if r else None
    def list_suggestions(self,status=None,limit=50):
        q='SELECT * FROM suggestions';a=[]
        if status:q+=' WHERE status=?';a.append(status)
        q+=' ORDER BY urgency DESC,created_at DESC LIMIT ?';a.append(max(1,min(500,int(limit))))
        return [self._suggestion(r) for r in self.db.execute(q,a).fetchall()]
    def set_focus(self,key,value):self.db.execute('INSERT INTO focus(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,json.dumps(value),datetime.now(timezone.utc).isoformat()));self.db.commit()
    def focus(self):return {r['key']:json.loads(r['value']) for r in self.db.execute('SELECT * FROM focus').fetchall()}
    def _signal(self,r):
        d=dict(r);d['actionable']=bool(d['actionable']);d['metadata']=json.loads(d['metadata']);return d
    def _suggestion(self,r):
        d=dict(r);d['metadata']=json.loads(d['metadata']);return d
    def close(self):self.db.close()

class SituationalEngine:
    """Event-aware proactive intelligence. It prioritizes and suggests; it never silently executes."""
    def __init__(self,store,world_model=None,missions=None,automations=None,devices=None):self.store=store;self.world_model=world_model;self.missions=missions;self.automations=automations;self.devices=devices
    def ingest(self,kind,source,title,detail,severity=.5,metadata=None,actionable=True):
        sid=self.store.add_signal(Signal(kind,source,title,detail,severity,actionable,metadata)); return {'signal_id':sid,'created':True}
    def scan(self):
        signals=[]; now=datetime.now(timezone.utc)
        if self.missions:
            for m in self.missions.list()[:100]:
                st=str(m.get('status','')).lower()
                if st in {'failed','blocked'}:signals.append(Signal('mission_failure','missions',f"Mission needs attention: {m.get('objective','')[:100]}",f"Mission {m.get('id','')} is {st}.",.92,True,{'mission_id':m.get('id'),'status':st}))
                elif st in {'running','queued'}:
                    try:
                        updated=datetime.fromisoformat(str(m.get('updated_at',''))); age=(now-updated).total_seconds()
                        if age>3600:signals.append(Signal('mission_stalled','missions',f"Mission may be stalled: {m.get('objective','')[:80]}",f"No mission update for {int(age//60)} minutes.",.78,True,{'mission_id':m.get('id'),'age_seconds':int(age)}))
                    except Exception:pass
        if self.automations:
            try:
                for a in self.automations.peek_due()[:10]:signals.append(Signal('automation_due','automation',f"Automation due: {a.get('name','')}",a.get('objective',''),.6,True,{'automation_id':a.get('id')}))
            except Exception:pass
        if self.devices:
            for d in self.devices.list():
                try:age=(now-datetime.fromisoformat(d['last_seen'])).total_seconds()
                except Exception:continue
                if age>3600:signals.append(Signal('device_stale','device',f"Device may be offline: {d['name']}",f"Last heartbeat was {int(age//60)} minutes ago.",.45,True,{'device_id':d['id'],'last_seen':d['last_seen']}))
        for s in signals:self.store.add_signal(s)
        pending=self.store.list_suggestions('pending',200); suggestions=[]
        for s in signals:
            meta=s.metadata or {}
            if any(x['title']==s.title and x['status']=='pending' for x in pending):continue
            urgency=min(1,s.severity); conf=min(1,.55+s.severity*.45); sug=Suggestion(uuid4().hex,s.title,s.detail,'review',conf,urgency,metadata=meta);self.store.add_suggestion(sug);suggestions.append(sug)
        return {'signals':len(signals),'suggestions':len(suggestions),'timestamp':now.isoformat()}
    def prioritize(self,limit=10):
        rows=self.store.list_suggestions('pending',max(1,min(100,int(limit))));
        return sorted(rows,key=lambda x:(x['urgency']*.65+x['confidence']*.35),reverse=True)
    def context(self):return {'focus':self.store.focus(),'signals':self.store.list_signals(20),'suggestions':self.prioritize(20)}
    def act_on_suggestion(self,sid,status='approved'):return self.store.update_suggestion(sid,status)
