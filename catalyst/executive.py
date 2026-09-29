from __future__ import annotations
import json, sqlite3, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class CognitiveExecutive:
    """Durable executive function for Catalyst's long-running objectives.

    It ranks objectives, inspects situational signals, prepares bounded action plans,
    records decisions and outcomes, and exposes a recovery-friendly cognitive cycle.
    It deliberately prepares actions rather than silently executing consequential ones.
    """
    def __init__(self, path='catalyst_data/executive.db', state=None, mind=None, situational=None, missions=None):
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(p, check_same_thread=False, timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000'); self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS cycles(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,objective_id TEXT,title TEXT NOT NULL,decision TEXT NOT NULL,reason TEXT NOT NULL,plan TEXT NOT NULL,status TEXT NOT NULL,metadata TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_cycles_created ON cycles(created_at)')
        self.db.execute('CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,objective_id TEXT,title TEXT NOT NULL,choice TEXT NOT NULL,rationale TEXT NOT NULL,evidence TEXT NOT NULL,confidence REAL NOT NULL,status TEXT NOT NULL)')
        self.db.commit()
        self.state=state; self.mind=mind; self.situational=situational; self.missions=missions

    def _objective_score(self, objective: dict[str, Any], context: dict[str, Any]) -> float:
        score=float(objective.get('priority', .5))
        status=objective.get('status')
        if status == 'active': score += .12
        signals=context.get('signals') or []
        title=str(objective.get('title','')).lower()
        for s in signals:
            blob=f"{s.get('title','')} {s.get('detail','')}".lower()
            terms=set(title.split()) & set(blob.split())
            if terms: score += min(.18, .03*len(terms)) * float(s.get('severity', .5))
        return min(1.0, score)

    def rank_objectives(self, limit=10):
        objectives=self.state.active_objectives(max(10, min(100, int(limit)*3))) if self.state else []
        context=self.situational.context() if self.situational else {'signals': []}
        ranked=[]
        for o in objectives:
            ranked.append((self._objective_score(o,context),o))
        ranked.sort(key=lambda x:(x[0],x[1].get('updated_at','')), reverse=True)
        return [{**o,'executive_score':round(score,4)} for score,o in ranked[:max(1,min(50,int(limit)))]]

    def prepare_cycle(self, catalyst, objective_id=None):
        ranked=self.rank_objectives(20)
        chosen=next((o for o in ranked if o['id']==objective_id),None) if objective_id else (ranked[0] if ranked else None)
        if not chosen:
            return {'status':'idle','reason':'No active objectives','ranked_objectives':ranked}
        title=chosen['title']
        plan=catalyst.plan_mission(title)
        plan['steps']=plan.get('steps',[])[:getattr(catalyst.settings,'mission_max_steps',24)]
        reason=f"Selected by priority, objective state, and current situational signals; executive score={chosen['executive_score']:.3f}."
        cid=hashlib.sha256((datetime.now(timezone.utc).isoformat()+'\0'+title).encode()).hexdigest()[:32]
        self.db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?,?,?,?)',(cid,datetime.now(timezone.utc).isoformat(),chosen['id'],title,'prepare_mission',reason,json.dumps(plan,ensure_ascii=False),'prepared',json.dumps({'objective':chosen,'signals':(self.situational.context().get('signals',[]) if self.situational else [])},ensure_ascii=False)))
        self.db.commit()
        if self.state: self.state.set('executive_focus', {'objective_id':chosen['id'],'title':title,'cycle_id':cid,'score':chosen['executive_score']})
        if self.mind:
            try:self.mind.remember('decision',f'Executive selected objective: {title}',source='executive',confidence=.8,importance=.8,pinned=False,metadata={'objective_id':chosen['id'],'cycle_id':cid})
            except Exception: pass
        return {'status':'prepared','cycle_id':cid,'objective':chosen,'decision':'prepare_mission','reason':reason,'plan':plan}

    def record_decision(self, objective_id, title, choice, rationale, evidence=None, confidence=.7, status='accepted'):
        did=hashlib.sha256((str(objective_id)+'\0'+str(choice)+'\0'+datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:32]
        self.db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?)',(did,datetime.now(timezone.utc).isoformat(),objective_id,title,choice,rationale,json.dumps(evidence or [],ensure_ascii=False),max(0,min(1,float(confidence))),status)); self.db.commit(); return did

    def recent_cycles(self,limit=20):
        rows=self.db.execute('SELECT * FROM cycles ORDER BY created_at DESC LIMIT ?',(max(1,min(100,int(limit))),)).fetchall()
        out=[]
        for r in rows:
            d=dict(r); d['plan']=json.loads(d['plan']); d['metadata']=json.loads(d['metadata']); out.append(d)
        return out

    def stats(self):
        return {'cycles':int(self.db.execute('SELECT COUNT(*) FROM cycles').fetchone()[0]),'decisions':int(self.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])}

    def close(self): self.db.close()
