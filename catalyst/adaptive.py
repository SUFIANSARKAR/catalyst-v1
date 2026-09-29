from __future__ import annotations
import json, re, sqlite3, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


class AdaptiveMissionController:
    """Closed-loop mission supervision.

    It observes persisted mission/step outcomes, creates bounded recovery
    decisions, and requeues failed/stalled missions through the existing job
    and approval boundaries. It never executes tools directly.
    """
    def __init__(self, path='catalyst_data/adaptive_missions.db', missions=None, jobs=None,
                 mind=None, state=None, situational=None, provider=None,
                 max_recoveries_per_mission=3, stall_seconds=900):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS adaptations(
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, mission_id TEXT NOT NULL,
            step_id TEXT, trigger TEXT NOT NULL, diagnosis TEXT NOT NULL,
            strategy TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL,
            evidence TEXT NOT NULL, metadata TEXT NOT NULL)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_adapt_mission ON adaptations(mission_id,created_at)')
        self.db.commit()
        self.missions = missions; self.jobs = jobs; self.mind = mind; self.state = state
        self.situational = situational; self.provider = provider
        self.max_recoveries_per_mission = max(1, min(int(max_recoveries_per_mission), 10))
        self.stall_seconds = max(60, int(stall_seconds))

    @staticmethod
    def _id(*parts):
        return hashlib.sha256('\0'.join(str(x) for x in parts).encode()).hexdigest()[:32]

    def _count_recoveries(self, mission_id: str) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM adaptations WHERE mission_id=? AND trigger IN ('failed_step','stalled_mission')", (mission_id,)).fetchone()[0])

    def _already_handled(self, mission_id: str, step_id: str | None, trigger: str) -> bool:
        if not step_id:
            row = self.db.execute("SELECT 1 FROM adaptations WHERE mission_id=? AND trigger=? ORDER BY created_at DESC LIMIT 1", (mission_id, trigger)).fetchone()
        else:
            row = self.db.execute("SELECT 1 FROM adaptations WHERE mission_id=? AND step_id=? AND trigger=? ORDER BY created_at DESC LIMIT 1", (mission_id, step_id, trigger)).fetchone()
        return bool(row)

    def _fallback_recovery(self, objective: str, step: dict[str, Any], error: str) -> dict[str, Any]:
        kind = str(step.get('kind') or step.get('payload', {}).get('kind') or 'chat')
        payload = dict(step.get('payload') or {})
        if kind == 'research':
            query = str(payload.get('query') or objective)
            return {'diagnosis':'Research step failed; narrow or diversify the evidence query.',
                    'strategy':'retry_with_refined_query', 'payload_update': {'query': query + ' with primary sources and explicit evidence'}}
        if kind == 'analysis':
            return {'diagnosis':'Analysis step failed; retry with smaller bounded input and clearer limits.',
                    'strategy':'retry_with_bounded_analysis', 'payload_update': {'max_rows': min(int(payload.get('max_rows',1000)),500)}}
        if kind == 'computer_use':
            return {'diagnosis':'Computer-use step failed; require a fresh observation before retrying.',
                    'strategy':'reobserve_then_retry', 'payload_update': {'reobserve_before_action': True}}
        if kind == 'agent':
            return {'diagnosis':'Specialist execution failed; retry with explicit failure context and verification.',
                    'strategy':'retry_with_failure_context', 'payload_update': {'recovery_context': error[-3000:]}}
        return {'diagnosis':'Generic step failed; retry with explicit failure evidence and a narrower objective.',
                'strategy':'retry_with_failure_context', 'payload_update': {'recovery_context': error[-3000:]}}

    def _model_recovery(self, objective: str, step: dict[str, Any], error: str) -> dict[str, Any] | None:
        if not self.provider:
            return None
        prompt = {
            'objective': objective,
            'step': step,
            'failure': error[-6000:],
            'instruction': 'Return strict JSON with keys diagnosis, strategy, payload_update. payload_update must only contain bounded changes to the existing step. Do not propose direct execution, credentials, policy bypasses, or destructive actions.'
        }
        try:
            msg = self.provider.chat([
                {'role':'system','content':'You are Catalyst\'s mission recovery planner. Analyze failure evidence and propose one conservative, testable recovery modification. Never invent unseen evidence. Return JSON only.'},
                {'role':'user','content':json.dumps(prompt, ensure_ascii=False)}
            ], None, 0.1, task='planning')
            raw = str(msg.get('content') or '').strip()
            match = re.search(r'\{.*\}', raw, re.S)
            if not match: return None
            data = json.loads(match.group(0))
            if not isinstance(data, dict): return None
            data.setdefault('payload_update', {})
            if not isinstance(data.get('payload_update'), dict): data['payload_update'] = {}
            # Keep recovery bounded to known step keys.
            current = step.get('payload') or {}
            data['payload_update'] = {k:v for k,v in data['payload_update'].items() if k in current or k in {'recovery_context','reobserve_before_action','max_rows','query','task','prompt'}}
            data['diagnosis'] = str(data.get('diagnosis') or 'Model proposed conservative recovery.')[:2000]
            data['strategy'] = str(data.get('strategy') or 'model_guided_retry')[:2000]
            return data
        except Exception:
            return None

    def _record(self, mission_id, step_id, trigger, diagnosis, strategy, action, status, evidence=None, metadata=None):
        aid = self._id(mission_id, step_id, trigger, datetime.now(timezone.utc).isoformat())
        self.db.execute('INSERT INTO adaptations VALUES(?,?,?,?,?,?,?,?,?,?,?)', (
            aid, datetime.now(timezone.utc).isoformat(), mission_id, step_id, trigger,
            diagnosis, strategy, action, status, json.dumps(evidence or {}, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False)))
        self.db.commit()
        return aid

    def _enqueue(self, mission: dict[str, Any], reason: str) -> dict[str, Any]:
        if not self.jobs:
            return {'status':'prepared_only', 'reason':'Job runtime unavailable.'}
        jid = self.jobs.create('mission', {'objective': mission['objective'], 'mission_id': mission['id'], 'adaptive': True, 'reason': reason}, max_attempts=3)
        self.missions.update(mission['id'], 'queued', checkpoint={'phase':'adaptive_requeue','reason':reason,'job_id':jid})
        return {'status':'requeued', 'job_id':jid}

    def recover_failed(self, mission: dict[str, Any]) -> dict[str, Any] | None:
        steps = self.missions.steps(mission['id']) if self.missions else []
        failed = next((s for s in steps if s.get('status') == 'failed'), None)
        if not failed or self._already_handled(mission['id'], failed['id'], 'failed_step'):
            return None
        if self._count_recoveries(mission['id']) >= self.max_recoveries_per_mission:
            return {'status':'recovery_limit_reached', 'mission_id':mission['id']}
        error = failed.get('error') or 'Unknown step failure.'
        decision = self._model_recovery(mission['objective'], failed, error) or self._fallback_recovery(mission['objective'], failed, error)
        payload = dict(failed.get('payload') or {})
        payload.update(decision.get('payload_update') or {})
        payload['recovery_attempt'] = int(payload.get('recovery_attempt', 0)) + 1
        payload['previous_failure'] = error[-4000:]
        self.missions.update_step(failed['id'], 'queued', result={'adaptive_recovery': decision['strategy'], 'diagnosis': decision['diagnosis']})
        # Persist the updated step payload while keeping the original identity/order.
        self.missions.update_step_payload(failed['id'], payload)
        self.missions.update(mission['id'], 'queued', error=None, checkpoint={'phase':'adaptive_recovery','step':failed['seq'],'strategy':decision['strategy']})
        rec_id = self._record(mission['id'], failed['id'], 'failed_step', decision['diagnosis'], decision['strategy'], 'retry_failed_step', 'planned', {'error':error,'step':failed}, {'payload_update':decision.get('payload_update') or {}})
        queued = self._enqueue(mission, f"adaptive recovery for step {failed['seq']}")
        self._remember(mission, failed, decision, error, rec_id)
        return {'status':'recovered', 'mission_id':mission['id'], 'step_id':failed['id'], 'adaptation_id':rec_id, 'decision':decision, 'dispatch':queued}

    def recover_stalled(self, mission: dict[str, Any]) -> dict[str, Any] | None:
        updated = mission.get('updated_at')
        if not updated or mission.get('status') not in {'running','queued','planned'}: return None
        try: age = (datetime.now(timezone.utc) - datetime.fromisoformat(updated)).total_seconds()
        except Exception: return None
        if age < self.stall_seconds or self._already_handled(mission['id'], None, 'stalled_mission'):
            return None
        if self._count_recoveries(mission['id']) >= self.max_recoveries_per_mission:
            return {'status':'recovery_limit_reached', 'mission_id':mission['id']}
        checkpoint = mission.get('checkpoint') or '{}'
        diagnosis = f"Mission has not advanced for {int(age)} seconds; resume from the persisted checkpoint and re-observe current state."
        self.missions.update(mission['id'], 'queued', checkpoint={'phase':'adaptive_stall_recovery','previous': checkpoint})
        rec_id = self._record(mission['id'], None, 'stalled_mission', diagnosis, 'resume_from_checkpoint', 'requeue_mission', 'planned', {'age_seconds':age,'checkpoint':checkpoint})
        queued = self._enqueue(mission, 'stalled mission recovery')
        self._remember(mission, None, {'diagnosis':diagnosis,'strategy':'resume_from_checkpoint'}, '', rec_id)
        return {'status':'recovered_stall', 'mission_id':mission['id'], 'adaptation_id':rec_id, 'dispatch':queued}

    def _remember(self, mission, step, decision, error, adaptation_id):
        if self.mind:
            try:
                text = f"Adaptive mission recovery: '{mission['objective']}' -> {decision.get('strategy')} ({decision.get('diagnosis')})."
                self.mind.remember('decision', text, source='adaptive_mission_control', confidence=.82, importance=.8, metadata={'mission_id':mission['id'],'step_id':step.get('id') if step else None,'adaptation_id':adaptation_id,'failure':error[-2000:] if error else ''})
            except Exception: pass
        if self.state:
            try:self.state.episode(f"Adaptive controller adjusted mission '{mission['objective']}' using {decision.get('strategy')}.", 'recovery_planned', metadata={'mission_id':mission['id'],'adaptation_id':adaptation_id})
            except Exception: pass

    def supervise_once(self, limit=25) -> list[dict[str, Any]]:
        if not self.missions: return []
        out=[]
        missions = self.missions.list(limit=max(1,min(int(limit),100)))
        for mission in missions:
            if mission.get('status') == 'failed':
                item = self.recover_failed(mission)
                if item: out.append(item)
            elif mission.get('status') in {'running','queued','planned'}:
                item = self.recover_stalled(mission)
                if item: out.append(item)
        return out

    def recent(self, limit=50):
        rows=self.db.execute('SELECT * FROM adaptations ORDER BY created_at DESC LIMIT ?', (max(1,min(int(limit),200)),)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            for k in ('evidence','metadata'):
                try:d[k]=json.loads(d[k])
                except Exception:pass
            out.append(d)
        return out

    def stats(self):
        return {
            'adaptations': int(self.db.execute('SELECT COUNT(*) FROM adaptations').fetchone()[0]),
            'missions_with_adaptations': int(self.db.execute('SELECT COUNT(DISTINCT mission_id) FROM adaptations').fetchone()[0]),
            'failed_step_recoveries': int(self.db.execute("SELECT COUNT(*) FROM adaptations WHERE trigger='failed_step'").fetchone()[0]),
            'stall_recoveries': int(self.db.execute("SELECT COUNT(*) FROM adaptations WHERE trigger='stalled_mission'").fetchone()[0]),
        }

    def close(self): self.db.close()
