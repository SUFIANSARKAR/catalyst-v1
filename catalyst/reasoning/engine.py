from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .tool_search import BoundedToolSearch


@dataclass(frozen=True)
class ReasoningPlan:
    """Structured reasoning contract selected for one objective."""

    strategy: str
    objective_type: str
    specialist: str = "general"
    depth: int = 4
    verification: bool = True
    evidence_required: bool = True
    risk: float = 0.2
    uncertainty: float = 0.4
    max_steps: int = 8
    parallel_lanes: int = 1
    retrieval_depth: int = 8
    tool_search_depth: int = 3
    rationale: tuple[str, ...] = ()

    @property
    def agent(self) -> str:
        """Backward-compatible alias used by the v4.x core."""
        return self.specialist

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rationale"] = list(self.rationale)
        return data


@dataclass
class Evidence:
    kind: str
    statement: str
    source: str = "unknown"
    confidence: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Hypothesis:
    statement: str
    confidence: float = 0.5
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReasoningTrace:
    run_id: str
    objective: str
    plan: ReasoningPlan
    hypotheses: list[Hypothesis] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    reflections: list[dict[str, Any]] = field(default_factory=list)
    deliberation: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "plan": self.plan.as_dict(),
            "hypotheses": [h.as_dict() for h in self.hypotheses],
            "evidence": [e.as_dict() for e in self.evidence[-120:]],
            "decisions": self.decisions[-80:],
            "reflections": self.reflections[-40:],
            "deliberation": self.deliberation,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ReasoningMemory:
    """Small durable reasoning ledger; raw prompts are not required to be persisted."""

    def __init__(self, path: str = "catalyst_data/reasoning.db"):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS reasoning_runs("
            "run_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,"
            "objective TEXT NOT NULL,plan TEXT NOT NULL,status TEXT NOT NULL,trace TEXT NOT NULL)"
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_status ON reasoning_runs(status,updated_at)")
        self.db.commit()

    def save(self, trace: ReasoningTrace) -> None:
        payload = json.dumps(trace.as_dict(), ensure_ascii=False)
        self.db.execute(
            "INSERT OR REPLACE INTO reasoning_runs VALUES(?,?,?,?,?,?,?)",
            (
                trace.run_id,
                trace.created_at,
                trace.updated_at,
                trace.objective,
                json.dumps(trace.plan.as_dict(), ensure_ascii=False),
                trace.status,
                payload,
            ),
        )
        self.db.commit()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT trace FROM reasoning_runs ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
        out = []
        for row in rows:
            try:
                out.append(json.loads(row["trace"]))
            except Exception:
                continue
        return out

    def close(self) -> None:
        self.db.close()


class ReasoningEngine:
    """Catalyst's adaptive reasoning core.

    This is a deterministic orchestration layer, not a fake second LLM. It selects a
    reasoning contract, tracks hypotheses/evidence, scores decisions, and can optionally
    ask a configured model to propose a bounded plan. Execution remains outside this class.
    """

    _PATTERNS: dict[str, tuple[str, ...]] = {
        "engineering": ("code", "coding", "bug", "debug", "repository", "repo", "github", "implement", "refactor", "test", "software", "build"),
        "research": ("research", "latest", "sources", "investigate", "paper", "evidence", "compare", "review"),
        "data": ("data", "dataset", "csv", "json", "sql", "statistics", "analyze", "analysis", "chart", "metrics"),
        "planning": ("plan", "strategy", "roadmap", "architect", "architecture", "design", "optimize", "complex", "multi-step"),
        "creative": ("image", "video", "story", "script", "scene", "shot", "creative", "visual", "media", "edit"),
        "computer_use": ("browser", "website", "web page", "click", "navigate", "computer", "desktop", "screen"),
        "device": ("phone", "android", "device", "notification", "clipboard", "lock device", "launch app"),
    }

    _HIGH_RISK = ("delete", "remove", "publish", "send", "deploy", "payment", "purchase", "credential", "secret", "production", "device")
    _HIGH_UNCERTAINTY = ("guess", "maybe", "probably", "unknown", "unclear", "not sure", "assume")

    def __init__(
        self,
        memory: ReasoningMemory | None = None,
        model: Callable[[list[dict[str, Any]], list[dict[str, Any]] | None], dict[str, Any]] | None = None,
    ):
        self.memory = memory or ReasoningMemory()
        self.model = model

    @staticmethod
    def _run_id(objective: str) -> str:
        seed = f"{datetime.now(timezone.utc).isoformat()}|{objective}"
        return "r_" + hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:18]

    @staticmethod
    def _match_score(text: str, patterns: Iterable[str]) -> int:
        low = text.lower()
        return sum(1 for p in patterns if p in low)

    def classify(self, objective: str) -> dict[str, Any]:
        scores = {name: self._match_score(objective, patterns) for name, patterns in self._PATTERNS.items()}
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0
        return {
            "scores": scores,
            "objective_type": best if best_score else "general",
            "dominant_score": best_score,
            "ambiguity": round(max(0.0, min(1.0, 1.0 - ((best_score - second_score) / max(1, best_score)))), 3) if best_score else 1.0,
        }

    def choose(self, objective: str, *, context: dict[str, Any] | None = None) -> ReasoningPlan:
        text = str(objective or "").strip()
        cls = self.classify(text)
        kind = cls["objective_type"]
        scores = cls["scores"]
        risk = min(1.0, 0.12 * self._match_score(text, self._HIGH_RISK) + (0.12 if kind in {"engineering", "device", "computer_use"} else 0.0))
        uncertainty = min(1.0, 0.18 * self._match_score(text, self._HIGH_UNCERTAINTY) + 0.3 * float(cls["ambiguity"]))
        rationale: list[str] = [f"dominant_objective={kind}"]
        if cls["ambiguity"] > 0.45:
            rationale.append("objective signals are mixed; use adaptive verification")
        if risk >= 0.45:
            rationale.append("risk indicators require stronger governance and verification")
        if context and context.get("evidence_available"):
            rationale.append("grounded context is available")
            uncertainty = max(0.05, uncertainty - 0.1)

        settings = {
            "engineering": ("tool-assisted", "engineering", 14, 2, 5),
            "research": ("research-verified", "research", 12, 2, 4),
            "data": ("data-analysis", "analyst", 12, 2, 4),
            "planning": ("deep-verified", "general", 14, 2, 5),
            "creative": ("creative-production", "creative", 10, 2, 3),
            "computer_use": ("computer-use-verified", "computer_use", 12, 1, 5),
            "device": ("device-verified", "device", 10, 1, 4),
            "general": ("direct", "general", 7, 1, 3),
        }
        strategy, specialist, max_steps, lanes, search_depth = settings.get(kind, settings["general"])
        if sum(v > 0 for k, v in scores.items() if k != kind) >= 2:
            lanes = min(4, lanes + 1)
            rationale.append("multiple capability domains detected; allow specialist parallelism")
        if uncertainty > 0.65:
            max_steps = min(20, max_steps + 3)
            rationale.append("high uncertainty expands investigation before commitment")
        if risk > 0.65:
            max_steps = min(20, max_steps + 2)
            rationale.append("high-risk objective adds an explicit verification pass")
        verification = True
        evidence_required = True
        return ReasoningPlan(
            strategy=strategy,
            objective_type=kind,
            specialist=specialist,
            depth=max(2, min(12, max_steps // 2)),
            verification=verification,
            evidence_required=evidence_required,
            risk=round(risk, 3),
            uncertainty=round(uncertainty, 3),
            max_steps=max_steps,
            parallel_lanes=lanes,
            retrieval_depth=12 if kind in {"research", "engineering", "data", "planning"} else 8,
            tool_search_depth=search_depth,
            rationale=tuple(rationale),
        )

    def start(self, objective: str, *, context: dict[str, Any] | None = None) -> ReasoningTrace:
        plan = self.choose(objective, context=context)
        trace = ReasoningTrace(self._run_id(objective), objective, plan)
        trace.evidence.append(Evidence("observation", f"Objective classified as {plan.objective_type}", "reasoning.classifier", 0.92))
        trace.decisions.append({"type": "route", "strategy": plan.strategy, "specialist": plan.specialist, "risk": plan.risk, "uncertainty": plan.uncertainty})
        self.memory.save(trace)
        return trace

    def set_deliberation(self, trace: ReasoningTrace, brief: dict[str, Any]) -> dict[str, Any]:
        trace.deliberation = dict(brief or {})
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self.memory.save(trace)
        return trace.deliberation

    def add_evidence(self, trace: ReasoningTrace, kind: str, statement: str, *, source: str = "unknown", confidence: float = 0.5, metadata: dict[str, Any] | None = None) -> Evidence:
        ev = Evidence(kind, str(statement)[:12000], source, max(0.0, min(1.0, float(confidence))), metadata=metadata or {})
        trace.evidence.append(ev)
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self._reconcile_hypotheses(trace)
        self.memory.save(trace)
        return ev

    def add_hypothesis(self, trace: ReasoningTrace, statement: str, confidence: float = 0.5) -> Hypothesis:
        h = Hypothesis(str(statement)[:4000], max(0.0, min(1.0, float(confidence))))
        trace.hypotheses.append(h)
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self.memory.save(trace)
        return h

    @staticmethod
    def _token_set(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9_]{3,}", text.lower()))

    def _reconcile_hypotheses(self, trace: ReasoningTrace) -> None:
        for hypothesis in trace.hypotheses:
            h_tokens = self._token_set(hypothesis.statement)
            if not h_tokens:
                continue
            for ev in trace.evidence[-32:]:
                overlap = len(h_tokens & self._token_set(ev.statement)) / max(1, len(h_tokens))
                if overlap < 0.18:
                    continue
                if ev.kind in {"contradiction", "failure", "negative"}:
                    if ev.statement not in hypothesis.contradicting:
                        hypothesis.contradicting.append(ev.statement)
                elif ev.kind in {"observation", "test", "verification", "source", "result", "success"}:
                    if ev.statement not in hypothesis.supporting:
                        hypothesis.supporting.append(ev.statement)
            support = min(1.0, 0.10 * len(hypothesis.supporting))
            conflict = min(0.9, 0.16 * len(hypothesis.contradicting))
            hypothesis.confidence = round(max(0.02, min(0.98, hypothesis.confidence + support - conflict)), 3)

    def score_decision(self, *, evidence_quality: float, expected_value: float, cost: float = 0.0, risk: float | None = None, uncertainty: float | None = None) -> float:
        r = 0.2 if risk is None else max(0.0, min(1.0, risk))
        u = 0.3 if uncertainty is None else max(0.0, min(1.0, uncertainty))
        score = 0.42 * max(0.0, min(1.0, evidence_quality)) + 0.38 * max(0.0, min(1.0, expected_value))
        score -= 0.12 * max(0.0, min(1.0, cost)) + 0.18 * r + 0.14 * u
        return round(max(0.0, min(1.0, score)), 4)

    def decide(self, trace: ReasoningTrace, action: str, *, evidence_quality: float, expected_value: float, cost: float = 0.0, note: str = "") -> dict[str, Any]:
        score = self.score_decision(evidence_quality=evidence_quality, expected_value=expected_value, cost=cost, risk=trace.plan.risk, uncertainty=trace.plan.uncertainty)
        threshold = 0.72 if trace.plan.risk >= 0.65 else 0.58
        decision = {
            "action": action,
            "score": score,
            "threshold": threshold,
            "approved_by_reasoning": score >= threshold,
            "note": note,
            "risk": trace.plan.risk,
            "uncertainty": trace.plan.uncertainty,
        }
        trace.decisions.append(decision)
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self.memory.save(trace)
        return decision

    def build_plan(self, trace: ReasoningTrace, *, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        kind = trace.plan.objective_type
        common = [
            {"id": "understand", "phase": "understand", "goal": "define objective, constraints, success criteria", "verification": "explicit success criteria"},
            {"id": "retrieve", "phase": "retrieve", "goal": "collect the minimum high-value evidence and context", "verification": "source/tool evidence"},
            {"id": "plan", "phase": "plan", "goal": "generate and rank a bounded action plan", "verification": "dependencies and risk reviewed"},
        ]
        lane = {
            "engineering": {"id": "engineer", "phase": "act", "goal": "implement in an isolated, verifiable workspace", "verification": "tests + diff review"},
            "research": {"id": "research", "phase": "act", "goal": "collect and reconcile source evidence", "verification": "source-backed synthesis"},
            "data": {"id": "analyze", "phase": "act", "goal": "inspect, transform and analyze the data", "verification": "reproducible calculations"},
            "creative": {"id": "produce", "phase": "act", "goal": "execute the production contract with continuity controls", "verification": "coverage + continuity review"},
            "computer_use": {"id": "operate", "phase": "act", "goal": "perform bounded computer actions with state observation", "verification": "actual UI/result observation"},
            "device": {"id": "operate", "phase": "act", "goal": "perform finite-vocabulary device actions through the control plane", "verification": "ack/result evidence"},
            "planning": {"id": "architect", "phase": "act", "goal": "compare alternatives and select a constraint-aware design", "verification": "trade-off review"},
            "general": {"id": "solve", "phase": "act", "goal": "solve the objective using available evidence and tools", "verification": "grounded result"},
        }[kind]
        common.append(lane)
        common.extend([
            {"id": "verify", "phase": "verify", "goal": "test claims and outcomes against deterministic evidence", "verification": "independent evidence gate"},
            {"id": "reflect", "phase": "reflect", "goal": "diagnose gaps, contradictions, or recovery requirements", "verification": "open risks are explicit"},
            {"id": "report", "phase": "report", "goal": "report the actual outcome, confidence, evidence and remaining work", "verification": "no unsupported completion claim"},
        ])
        for idx, step in enumerate(common):
            step["depends_on"] = [] if idx == 0 else [common[idx - 1]["id"]]
            step["max_attempts"] = 2 if step["id"] in {"act", "engineer", "research", "analyze", "produce", "operate", "solve", "architect"} else 1
        if trace.plan.parallel_lanes > 1:
            common[1]["parallelizable"] = True
            common[2]["parallel_lanes"] = trace.plan.parallel_lanes
        if context and context.get("candidate_tools"):
            common[2]["candidate_tools"] = context["candidate_tools"][:16]
        return common[: trace.plan.max_steps]

    def refine_plan(self, trace: ReasoningTrace, deterministic_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optionally ask the configured reasoning model to improve a bounded plan.

        The model is not trusted with execution. Catalyst validates the returned structure,
        dependency order and size, then falls back to the deterministic plan on any defect.
        """
        if not self.model:
            return deterministic_plan
        system = (
            "You are Catalyst's planning verifier. Return JSON only. Improve the supplied plan "
            "without inventing capabilities, tools or results. Keep the number of steps within the "
            "given bound. Every dependency must refer to an earlier step. Preserve explicit verification "
            "and recovery gates. Do not execute anything."
        )
        payload = {
            "objective": trace.objective,
            "contract": trace.plan.as_dict(),
            "deterministic_plan": deterministic_plan,
            "evidence": [e.as_dict() for e in trace.evidence[-16:]],
        }
        try:
            response = self.model(
                [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                None,
            )
            raw = str((response or {}).get("content") or "")
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end < start:
                return deterministic_plan
            obj = json.loads(raw[start:end + 1])
            candidate = obj.get("steps") if isinstance(obj, dict) else None
            if not isinstance(candidate, list):
                return deterministic_plan
            candidate = candidate[: trace.plan.max_steps]
            allowed_phases = {"understand", "retrieve", "plan", "act", "verify", "reflect", "report"}
            seen = set()
            clean = []
            for step in candidate:
                if not isinstance(step, dict):
                    continue
                sid = str(step.get("id") or "").strip()
                phase = str(step.get("phase") or "").strip()
                goal = str(step.get("goal") or "").strip()
                deps = step.get("depends_on") or []
                if not sid or not goal or phase not in allowed_phases or sid in seen or not isinstance(deps, list):
                    return deterministic_plan
                if any(str(d) not in seen for d in deps):
                    return deterministic_plan
                clean.append({**step, "id": sid, "phase": phase, "goal": goal, "depends_on": [str(d) for d in deps]})
                seen.add(sid)
            if len(clean) < 3 or clean[-1]["phase"] != "report":
                return deterministic_plan
            trace.decisions.append({"type": "model_plan_refinement", "accepted": True, "steps": len(clean)})
            trace.updated_at = datetime.now(timezone.utc).isoformat()
            self.memory.save(trace)
            return clean
        except Exception as exc:
            trace.decisions.append({"type": "model_plan_refinement", "accepted": False, "error": str(exc)[:1000]})
            trace.updated_at = datetime.now(timezone.utc).isoformat()
            self.memory.save(trace)
            return deterministic_plan

    def search_actions(
        self,
        initial_state: Any,
        candidates: Callable[[Any, int], Iterable[dict[str, Any]]],
        transition: Callable[[Any, dict[str, Any]], Any],
        validate: Callable[[Any, list[dict[str, Any]]], bool],
        score: Callable[[Any, list[dict[str, Any]]], float] | None = None,
        *,
        depth: int | None = None,
    ) -> dict[str, Any]:
        search = BoundedToolSearch(max_depth=depth or 3, max_nodes=96, branch_limit=4)
        result = search.search(initial_state, candidates, transition, validate, score)
        return {
            "found": bool(result and result.valid),
            "actions": result.actions if result else [],
            "score": result.score if result else 0.0,
            "nodes_expanded": search.nodes_expanded,
            "trace": search.trace[-120:],
        }

    def reflect(self, trace: ReasoningTrace) -> dict[str, Any]:
        supported = sum(1 for e in trace.evidence if e.kind in {"verification", "test", "success", "source", "result"})
        failures = sum(1 for e in trace.evidence if e.kind in {"failure", "contradiction", "negative"})
        unresolved = [h.statement for h in trace.hypotheses if h.confidence < 0.55]
        verified_ratio = supported / max(1, supported + failures)
        reflection = {
            "verified_evidence": supported,
            "negative_evidence": failures,
            "verification_ratio": round(verified_ratio, 3),
            "unresolved_hypotheses": unresolved[:20],
            "needs_replan": failures > 0 or bool(unresolved),
            "recommendation": "replan from fresh evidence" if (failures or unresolved) else "proceed with current plan",
        }
        trace.reflections.append(reflection)
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self.memory.save(trace)
        return reflection

    def finish(self, trace: ReasoningTrace, status: str = "completed") -> ReasoningTrace:
        trace.status = status
        trace.updated_at = datetime.now(timezone.utc).isoformat()
        self.memory.save(trace)
        return trace
