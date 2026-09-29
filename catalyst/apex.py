from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reasoning import ClaimVerifier, ReasoningEngine


@dataclass
class ApexMission:
    objective: str
    mission_id: str
    reasoning: Any
    plan: list[dict[str, Any]]
    state: str = "planned"
    capabilities: list[str] = field(default_factory=list)
    governance: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": "catalyst.apex-mission.v2",
            "objective": self.objective,
            "mission_id": self.mission_id,
            "state": self.state,
            "capabilities": self.capabilities,
            "governance": self.governance,
            "reasoning": self.reasoning.as_dict(),
            "plan": self.plan,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ApexMissionStore:
    """Durable mission lifecycle/checkpoint store for Apex contracts."""

    TERMINAL = {"completed", "failed", "cancelled"}
    ALLOWED = {"planned", "queued", "running", "paused", "completed", "failed", "cancelled"}

    def __init__(self, path: str = "catalyst_data/apex_missions.db"):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS missions("
            "id TEXT PRIMARY KEY, objective TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL,"
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, checkpoint INTEGER NOT NULL DEFAULT 0,"
            "last_event TEXT NOT NULL DEFAULT '')"
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_apex_state ON missions(state,updated_at)")
        self.events_table()
        self.db.commit()

    def events_table(self):
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS events("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, state TEXT NOT NULL,"
            "checkpoint INTEGER NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)"
        )

    def save(self, mission: ApexMission, checkpoint: int = 0, event: str = "planned"):
        now = datetime.now(timezone.utc).isoformat()
        mission.updated_at = now
        payload = json.dumps(mission.as_dict(), ensure_ascii=False)
        self.db.execute(
            "INSERT OR REPLACE INTO missions(id,objective,state,payload,created_at,updated_at,checkpoint,last_event) VALUES(?,?,?,?,?,?,?,?)",
            (mission.mission_id, mission.objective, mission.state, payload, mission.created_at, now, int(checkpoint), event),
        )
        self.db.execute(
            "INSERT INTO events(mission_id,state,checkpoint,detail,created_at) VALUES(?,?,?,?,?)",
            (mission.mission_id, mission.state, int(checkpoint), event, now),
        )
        self.db.commit()
        return self.get(mission.mission_id)

    def get(self, mission_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["payload"] = json.loads(data["payload"])
        except Exception:
            data["payload"] = {}
        return data

    def list(self, state: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        q = "SELECT * FROM missions"
        args: list[Any] = []
        if state:
            q += " WHERE state=?"
            args.append(state)
        q += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        rows = self.db.execute(q, args).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                item["payload"] = {}
            out.append(item)
        return out

    def transition(self, mission_id: str, state: str, *, checkpoint: int | None = None, detail: str = "state transition"):
        if state not in self.ALLOWED:
            raise ValueError(f"Unsupported Apex mission state: {state}")
        current = self.get(mission_id)
        if not current:
            raise KeyError(mission_id)
        if current["state"] in self.TERMINAL and state != current["state"]:
            raise ValueError("Terminal Apex mission cannot transition")
        now = datetime.now(timezone.utc).isoformat()
        cp = current["checkpoint"] if checkpoint is None else max(0, int(checkpoint))
        self.db.execute("UPDATE missions SET state=?,updated_at=?,checkpoint=?,last_event=? WHERE id=?", (state, now, cp, detail[:500], mission_id))
        self.db.execute("INSERT INTO events(mission_id,state,checkpoint,detail,created_at) VALUES(?,?,?,?,?)", (mission_id, state, cp, detail[:500], now))
        self.db.commit()
        return self.get(mission_id)

    def events(self, mission_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM events WHERE mission_id=? ORDER BY id DESC LIMIT ?", (mission_id, max(1, min(int(limit), 500)))).fetchall()
        return [dict(r) for r in rows]

    def update_reasoning(self, mission_id: str, trace) -> dict[str, Any]:
        current = self.get(mission_id)
        if not current:
            raise KeyError(mission_id)
        payload = dict(current.get("payload") or {})
        payload["reasoning"] = trace.as_dict()
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute("UPDATE missions SET payload=?,updated_at=?,last_event=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), now, "reasoning-updated", mission_id))
        self.db.execute("INSERT INTO events(mission_id,state,checkpoint,detail,created_at) VALUES(?,?,?,?,?)", (mission_id, current["state"], current["checkpoint"], "reasoning-updated", now))
        self.db.commit()
        return self.get(mission_id)

    def close(self):
        self.db.close()


def _mission_trace_from_payload(row: dict[str, Any]):
    """Rehydrate a lightweight reasoning trace for execution evidence updates."""
    from .reasoning.engine import ReasoningTrace, ReasoningPlan, Hypothesis, Evidence
    payload = row.get("payload") or {}
    raw = payload.get("reasoning") or {}
    p = raw.get("plan") or {}
    plan = ReasoningPlan(
        strategy=p.get("strategy", "direct"), objective_type=p.get("objective_type", "general"),
        specialist=p.get("specialist", "general"), depth=int(p.get("depth", 4)),
        verification=bool(p.get("verification", True)), evidence_required=bool(p.get("evidence_required", True)),
        risk=float(p.get("risk", .2)), uncertainty=float(p.get("uncertainty", .4)),
        max_steps=int(p.get("max_steps", 8)), parallel_lanes=int(p.get("parallel_lanes", 1)),
        retrieval_depth=int(p.get("retrieval_depth", 8)), tool_search_depth=int(p.get("tool_search_depth", 3)),
        rationale=tuple(p.get("rationale") or ()),
    )
    return ReasoningTrace(
        run_id=row.get("mission_id", "apex"), objective=row.get("objective", ""), plan=plan,
        hypotheses=[Hypothesis(**h) for h in (raw.get("hypotheses") or []) if isinstance(h, dict)],
        evidence=[Evidence(**e) for e in (raw.get("evidence") or []) if isinstance(e, dict)],
        decisions=list(raw.get("decisions") or []), reflections=list(raw.get("reflections") or []),
        deliberation=dict(raw.get("deliberation") or {}), status=raw.get("status", "active"),
        created_at=raw.get("created_at", datetime.now(timezone.utc).isoformat()),
        updated_at=raw.get("updated_at", datetime.now(timezone.utc).isoformat()),
    )


class ApexRuntime:
    """Unified top-level mission controller for Catalyst's major runtime.

    Apex owns mission contracts, routing, lifecycle and evidence state. It does not
    invent execution capabilities: concrete subsystem handlers must be explicitly
    registered by the host runtime and remain behind their own policy boundaries.
    """

    protocol = "catalyst.apex-runtime.v3"

    def __init__(self, reasoning: ReasoningEngine, *, context_provider=None, subsystem_registry=None, deliberator=None, store: ApexMissionStore | None = None):
        self.reasoning = reasoning
        self.verifier = ClaimVerifier()
        self.context_provider = context_provider
        self.subsystems = dict(subsystem_registry or {})
        self.deliberator = deliberator
        self.store = store or ApexMissionStore()

    def register_subsystem(self, kind: str, handler, *, label: str | None = None) -> None:
        if not callable(handler):
            raise TypeError("Apex subsystem handler must be callable")
        self.subsystems[str(kind)] = {"handler": handler, "label": label or str(kind)}

    def unregister_subsystem(self, kind: str) -> None:
        self.subsystems.pop(str(kind), None)

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        aliases = {"coder": "engineering", "coding": "engineering", "analyst": "data", "browser": "computer_use"}
        return aliases.get(str(kind), str(kind))

    def route(self, mission: ApexMission | dict[str, Any]) -> dict[str, Any]:
        if isinstance(mission, dict):
            payload = mission.get("payload") or mission
            kind = payload.get("reasoning", {}).get("plan", {}).get("objective_type") or mission.get("objective_type") or "general"
            objective = str(payload.get("objective") or mission.get("objective") or "")
            mission_id = payload.get("mission_id") or mission.get("mission_id")
        else:
            kind = mission.reasoning.plan.objective_type
            objective = mission.objective
            mission_id = mission.mission_id
        kind = self._normalize_kind(kind)
        binding = self.subsystems.get(kind)
        if isinstance(binding, dict):
            label = binding.get("label") or kind
            available = callable(binding.get("handler"))
        else:
            label = kind
            available = callable(binding)
        return {
            "mission_id": mission_id,
            "objective": objective,
            "objective_type": kind,
            "handler": label,
            "available": available,
            "execution_authority": "registered-subsystem",
            "note": "Apex routes only to explicitly registered subsystem handlers; execution remains policy-bound.",
        }

    def dispatch(self, mission_id: str, *, execute: bool = False, approval: bool = False, **kwargs: Any) -> dict[str, Any]:
        row = self.store.get(mission_id)
        if not row:
            raise KeyError(mission_id)
        route = self.route(row)
        if not execute:
            return {"status": "planned", "route": route, "mission": row}
        if row["state"] in self.store.TERMINAL:
            return {"status": "terminal", "route": route, "mission": row}
        if row.get("payload", {}).get("governance", {}).get("approval_required_for_consequential_actions", True) and not approval:
            return {"status": "approval_required", "route": route, "mission": row}
        binding = self.subsystems.get(route["objective_type"])
        handler = binding.get("handler") if isinstance(binding, dict) else binding
        if not callable(handler):
            self.store.transition(mission_id, "paused", checkpoint=row["checkpoint"], detail=f"No registered handler for {route['objective_type']}")
            return {"status": "unavailable", "route": route, "mission": self.store.get(mission_id)}
        self.store.transition(mission_id, "queued", checkpoint=row["checkpoint"], detail="Apex dispatch queued")
        self.store.transition(mission_id, "running", checkpoint=row["checkpoint"], detail=f"Apex dispatch -> {route['objective_type']}")
        try:
            result = handler(row["objective"], mission=row, **kwargs)
            normalized = str(result.get("status", "") if isinstance(result, dict) else "").lower()
            if normalized in {"failed", "error"}:
                final_state, final_status = "failed", "failed"
            elif normalized in {"paused", "awaiting_approval"}:
                final_state, final_status = "paused", normalized
            elif normalized in {"queued", "running", "partial"}:
                final_state, final_status = ("running" if normalized == "running" else "queued"), normalized
            else:
                final_state, final_status = "completed", "completed"
            trace = _mission_trace_from_payload(row)
            self.reasoning.add_evidence(
                trace,
                "execution" if final_state in {"completed", "running", "queued"} else "failure",
                f"Subsystem {route['objective_type']} returned status={final_status}.",
                source=f"apex:{route['objective_type']}",
                confidence=.95 if final_state != "failed" else .9,
                metadata={"result_type": type(result).__name__, "status": final_status},
            )
            self.store.update_reasoning(mission_id, trace)
            self.store.transition(mission_id, final_state, checkpoint=max(row["checkpoint"], 1), detail=f"Apex dispatch {final_status}")
            return {"status": final_status, "route": route, "result": result, "mission": self.store.get(mission_id)}
        except Exception as exc:
            self.store.transition(mission_id, "failed", checkpoint=row["checkpoint"], detail=f"Apex dispatch failed: {exc}")
            return {"status": "failed", "route": route, "error": str(exc), "mission": self.store.get(mission_id)}

    def _capabilities(self, kind: str, objective: str) -> list[str]:
        base = {
            "engineering": ["repository-intelligence", "coding-agent", "tests", "diff-review", "recovery"],
            "research": ["evidence-research", "source-reconciliation", "synthesis"],
            "data": ["data-inspection", "analysis", "reproducible-verification"],
            "creative": ["story-director", "image-generation", "video-generation", "continuity", "post-production"],
            "computer_use": ["browser", "computer-observation", "bounded-actions"],
            "device": ["device-control", "acknowledgements", "policy-gated-actions"],
            "planning": ["architecture-reasoning", "trade-off-analysis", "verification"],
            "general": ["reasoning", "memory", "tool-use", "verification"],
        }
        out = list(base.get(kind, base["general"]))
        low = objective.lower()
        if any(x in low for x in ("memory", "remember", "context")):
            out += ["persistent-mind"]
        if any(x in low for x in ("autonomous", "long-running", "continue", "monitor")):
            out += ["autonomous-cognition", "recovery"]
        return list(dict.fromkeys(out))

    def plan(self, objective: str, *, context: dict[str, Any] | None = None) -> ApexMission:
        ctx = dict(context or {})
        if self.context_provider:
            try:
                supplied = self.context_provider(objective)
                if isinstance(supplied, dict):
                    ctx.update(supplied)
            except Exception:
                pass
        trace = self.reasoning.start(objective, context=ctx)
        plan = self.reasoning.build_plan(trace, context=ctx)
        if self.deliberator:
            try:
                brief = self.deliberator.analyze(objective, plan=trace.plan, context=ctx)
                self.reasoning.set_deliberation(trace, brief.as_dict())
            except Exception:
                pass
        kind = trace.plan.objective_type
        mission = ApexMission(
            objective=objective,
            mission_id=trace.run_id,
            reasoning=trace,
            plan=plan,
            capabilities=self._capabilities(kind, objective),
            governance={
                "approval_required_for_consequential_actions": True,
                "evidence_required": True,
                "verification_required": True,
                "bounded_steps": trace.plan.max_steps,
                "risk": trace.plan.risk,
                "uncertainty": trace.plan.uncertainty,
                "execution_authority": "subsystem-policy-boundaries",
            },
        )
        self.store.save(mission, checkpoint=0, event="planned")
        return mission

    def checkpoint(self, mission_id: str, checkpoint: int, *, state: str | None = None, detail: str = "checkpoint"):
        current = self.store.get(mission_id)
        if not current:
            raise KeyError(mission_id)
        target = state or current["state"]
        return self.store.transition(mission_id, target, checkpoint=max(0, int(checkpoint)), detail=detail)

    def transition(self, mission_id: str, state: str, *, checkpoint: int | None = None, detail: str = "state transition"):
        return self.store.transition(mission_id, state, checkpoint=checkpoint, detail=detail)

    def observe(self, mission: ApexMission, kind: str, statement: str, *, source: str, confidence: float = 0.8, metadata: dict[str, Any] | None = None):
        self.reasoning.add_evidence(mission.reasoning, kind, statement, source=source, confidence=confidence, metadata=metadata)
        self.store.save(mission, event=f"evidence:{kind}")
        return mission.reasoning.as_dict()

    def reflect(self, mission: ApexMission) -> dict[str, Any]:
        result = self.reasoning.reflect(mission.reasoning)
        self.store.save(mission, event="reflection")
        return result

    def verify_answer(self, mission: ApexMission, answer: str) -> dict[str, Any]:
        evidence = [e.as_dict() for e in mission.reasoning.evidence]
        result = self.verifier.verify(answer, evidence)
        self.reasoning.add_evidence(
            mission.reasoning,
            "verification" if result.verified else "negative",
            f"Claim verification: verified={result.verified}; confidence={result.confidence}",
            source="apex.claim-verifier",
            confidence=result.confidence,
            metadata=result.as_dict(),
        )
        self.store.save(mission, event="answer-verification")
        return result.as_dict()

    def status(self, mission: ApexMission) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "mission_id": mission.mission_id,
            "objective": mission.objective,
            "state": mission.state,
            "objective_type": mission.reasoning.plan.objective_type,
            "strategy": mission.reasoning.plan.strategy,
            "risk": mission.reasoning.plan.risk,
            "uncertainty": mission.reasoning.plan.uncertainty,
            "evidence_count": len(mission.reasoning.evidence),
            "hypothesis_count": len(mission.reasoning.hypotheses),
            "decision_count": len(mission.reasoning.decisions),
            "reflection_count": len(mission.reasoning.reflections),
            "deliberation_ready": bool(mission.reasoning.deliberation),
        }
