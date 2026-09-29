from __future__ import annotations
import hashlib, json, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AutonomousCognitionDaemon:
    """Background scheduler that invokes bounded cognition cycles on a safe interval."""
    def __init__(self, engine, interval_seconds=60, enabled=False):
        self.engine=engine; self.interval_seconds=max(10,int(interval_seconds)); self.enabled=bool(enabled)
        self._stop=threading.Event(); self.thread=None
    def start(self):
        if not self.enabled or (self.thread and self.thread.is_alive()): return
        self._stop.clear(); self.thread=threading.Thread(target=self._run,name='catalyst-autonomous-cognition',daemon=True); self.thread.start()
    def stop(self):
        self._stop.set()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=min(self.interval_seconds+1,10))
    def _run(self):
        while not self._stop.is_set():
            try:self.engine.run_once(dispatch=True)
            except Exception: pass
            self._stop.wait(self.interval_seconds)

class AutonomousCognition:
    """Continuous, bounded cognition over Catalyst's existing mind/executive stack.

    The engine separates observation and deliberation from consequential execution.
    It may automatically launch only objectives explicitly marked autonomy='approved'.
    All cycle decisions/outcomes are durable and fed back into the cognitive mind.
    """
    def __init__(self, path='catalyst_data/autonomy.db', executive=None, mind=None, state=None,
                 situational=None, missions=None, jobs=None, max_cycles_per_run=1):
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(p, check_same_thread=False, timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000'); self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS cognition_runs(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,phase TEXT NOT NULL,objective_id TEXT,title TEXT,decision TEXT NOT NULL,reason TEXT NOT NULL,context TEXT NOT NULL,status TEXT NOT NULL,result TEXT,metadata TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_cognition_runs_created ON cognition_runs(created_at)')
        self.db.commit()
        self.executive=executive; self.mind=mind; self.state=state; self.situational=situational; self.missions=missions; self.jobs=jobs
        self.max_cycles_per_run=max(1,min(int(max_cycles_per_run),5))
        self._lock=threading.Lock()

    @staticmethod
    def _id(*parts):
        return hashlib.sha256('\0'.join(str(x) for x in parts).encode()).hexdigest()[:32]

    def _context(self, query=''):
        out={'mind': [], 'state': '', 'situational': {}, 'ranked_objectives': []}
        if self.mind:
            try: out['mind']=self.mind.search(query,18) if query else self.mind.active(18)
            except Exception: pass
        if self.state:
            try: out['state']=self.state.context(12)
            except Exception: pass
        if self.situational:
            try: out['situational']=self.situational.context()
            except Exception: pass
        if self.executive:
            try: out['ranked_objectives']=self.executive.rank_objectives(12)
            except Exception: pass
        return out

    def reconcile(self):
        """Reflect completed/failed autonomous missions back into objectives and memory."""
        if not self.state or not self.missions: return []
        focus=self.state.get('autonomous_focus',{}) or {}; mission_id=focus.get('mission_id')
        if not mission_id: return []
        mission=self.missions.get(mission_id)
        if not mission or mission.get('status') not in {'completed','failed','cancelled'}: return []
        oid=focus.get('objective_id')
        if oid and mission.get('status')=='completed': self.state.update_objective(oid,'completed')
        event={'mission_id':mission_id,'objective_id':oid,'status':mission.get('status'),'objective':mission.get('objective')}
        try:self.state.episode(f"Autonomous mission '{mission.get('objective')}' ended with status {mission.get('status')}.", 'completed' if mission.get('status')=='completed' else 'failed', metadata={'autonomous':True,**event})
        except Exception:pass
        if self.mind:
            try:self.mind.remember('episode',f"Autonomous mission '{mission.get('objective')}' -> {mission.get('status')}",source='autonomy',confidence=.9,importance=.78,metadata=event)
            except Exception:pass
        self.state.set('autonomous_focus',{})
        return [event]

    def observe(self):
        """Collect fresh environment signals without performing actions."""
        self.reconcile()
        if self.situational:
            try:self.situational.scan()
            except Exception:pass
        ctx=self._context()
        self._record('observe',None,None,'observe','Refresh situation and persistent cognitive context.',ctx,'completed')
        return ctx

    def deliberate(self, objective_id=None, catalyst=None):
        if not self.executive:
            return {'status':'idle','reason':'Executive layer unavailable'}
        ranked=self.executive.rank_objectives(20)
        chosen=next((o for o in ranked if o['id']==objective_id),None) if objective_id else (ranked[0] if ranked else None)
        if not chosen:
            return {'status':'idle','reason':'No active objectives','ranked_objectives':ranked}
        ctx=self._context(chosen['title'])
        explicit=chosen.get('metadata') or {}
        autonomy=str(explicit.get('autonomy','manual')).lower()
        auto_allowed=autonomy in {'approved','autonomous','auto'}
        decision='auto_dispatch' if auto_allowed else 'prepare_for_approval'
        reason=(f"Selected '{chosen['title']}' from the executive ranking using objective priority, state, and current situation. "
                f"Autonomy policy={autonomy}; consequential execution remains governed by existing mission/tool policies.")
        plan=None
        if catalyst:
            try: plan=catalyst.plan_mission(chosen['title'])
            except Exception as exc: reason+=f' Planning failed: {exc}'
        result={'status':'deliberated','objective':chosen,'decision':decision,'reason':reason,'plan':plan,'context':ctx}
        self.executive.record_decision(chosen['id'],chosen['title'],decision,reason,ctx.get('situational',{}),.78,'accepted')
        self._record('deliberate',chosen['id'],chosen['title'],decision,reason,ctx,'ready')
        if self.mind:
            try:self.mind.remember('decision',f"Cognition chose: {chosen['title']} ({decision})",source='autonomy',confidence=.82,importance=.82,pinned=False,metadata={'objective_id':chosen['id'],'decision':decision})
            except Exception:pass
        return result

    def dispatch(self, deliberation):
        """Dispatch an approved autonomous objective into the durable job queue."""
        if deliberation.get('decision')!='auto_dispatch':
            return {'status':'awaiting_approval','reason':'Objective is not autonomy-approved.','deliberation':deliberation}
        obj=deliberation['objective'];
        focus=self.state.get('autonomous_focus',{}) if self.state else {}
        if focus and focus.get('objective_id')==obj.get('id') and focus.get('mission_id'):
            existing=self.missions.get(focus.get('mission_id')) if self.missions else None
            if existing and existing.get('status') in {'queued','planned','running','paused'}:
                return {'status':'already_active','mission_id':focus.get('mission_id'),'job_id':focus.get('job_id'),'objective':obj}
        if not self.jobs or not self.missions:
            return {'status':'prepared_only','reason':'Mission/job runtime unavailable.'}
        objective=obj['title']; mission_id=self.missions.create(objective,priority=round(float(obj.get('priority',.5))*100))
        self.missions.update(mission_id,'queued',plan=deliberation.get('plan') or {'objective':objective})
        job_id=self.jobs.create('mission',{'objective':objective,'mission_id':mission_id,'autonomous':True},max_attempts=3)
        self._record('act',obj['id'],objective,'dispatch_mission','Objective is explicitly autonomy-approved; dispatched to governed mission worker.',deliberation.get('context',{}),'dispatched',{'mission_id':mission_id,'job_id':job_id})
        if self.state:
            try:self.state.set('autonomous_focus',{'objective_id':obj['id'],'mission_id':mission_id,'job_id':job_id,'title':objective,'started_at':datetime.now(timezone.utc).isoformat()})
            except Exception:pass
        return {'status':'dispatched','mission_id':mission_id,'job_id':job_id,'objective':obj}

    def run_once(self, objective_id=None, catalyst=None, dispatch=True):
        with self._lock:
            observed=self.observe()
            deliberation=self.deliberate(objective_id,catalyst)
            dispatched=self.dispatch(deliberation) if dispatch else {'status':'not_dispatched'}
            return {'observed':observed,'deliberation':deliberation,'dispatch':dispatched}

    def recent(self, limit=50):
        rows=self.db.execute('SELECT * FROM cognition_runs ORDER BY created_at DESC LIMIT ?',(max(1,min(200,int(limit))),)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            for k in ('context','result','metadata'):
                try:d[k]=json.loads(d[k]) if d[k] else None
                except Exception:pass
            out.append(d)
        return out

    def stats(self):
        total=int(self.db.execute('SELECT COUNT(*) FROM cognition_runs').fetchone()[0])
        by_phase={r['phase']:int(r['n']) for r in self.db.execute('SELECT phase,COUNT(*) n FROM cognition_runs GROUP BY phase').fetchall()}
        return {'runs':total,'by_phase':by_phase}

    def _record(self,phase,objective_id,title,decision,reason,context,status,result=None,metadata=None):
        rid=self._id(datetime.now(timezone.utc).isoformat(),phase,objective_id,title,decision)
        self.db.execute('INSERT OR IGNORE INTO cognition_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
            rid,datetime.now(timezone.utc).isoformat(),phase,objective_id,title or '',decision,reason,
            json.dumps(context or {},ensure_ascii=False),status,json.dumps(result,ensure_ascii=False) if result is not None else None,json.dumps(metadata or {},ensure_ascii=False)))
        self.db.commit()
        return rid

    def close(self): self.db.close()
