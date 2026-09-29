from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .agent import EngineeringAgent, EngineeringRun


@dataclass
class EngineeringCycle:
    cycle: int
    objective: str
    status: str
    phase: str
    run_id: str
    iterations: int
    tool_calls: int
    evidence_count: int
    recovery_target: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "objective": self.objective,
            "status": self.status,
            "phase": self.phase,
            "run_id": self.run_id,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "evidence_count": self.evidence_count,
            "recovery_target": self.recovery_target,
        }


@dataclass
class EngineeringFactoryResult:
    protocol: str = "catalyst.engineering-factory.v1"
    objective: str = ""
    status: str = "planned"
    cycles: list[EngineeringCycle] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    final: str = ""
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "objective": self.objective,
            "status": self.status,
            "cycles": [c.as_dict() for c in self.cycles],
            "plan": self.plan,
            "final": self.final,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


class EngineeringProductionFactory:
    """Bounded autonomous software-production supervisor.

    It does not invent a second coding engine. It supervises the existing EngineeringAgent,
    turning one-shot execution into a bounded multi-cycle loop: reconnaissance -> implementation
    -> verification -> recovery -> review. Approval semantics stay owned by the underlying tools.
    """

    protocol = "catalyst.engineering-factory.v1"

    def __init__(self, agent: EngineeringAgent, max_cycles: int = 3):
        self.agent = agent
        self.max_cycles = max(1, min(int(max_cycles), 6))

    def prepare(self, objective: str, focus_files: list[str] | None = None) -> dict[str, Any]:
        run = self.agent.plan(objective)
        context = self.agent.toolbox.context_pack(objective, focus_files or [], max_files=40, max_chars=180_000)
        return {
            "protocol": self.protocol,
            "objective": objective,
            "base_plan": run.plan,
            "repository": {
                "file_count": context.get("repo", {}).get("file_count", 0),
                "total_lines": context.get("repo", {}).get("total_lines", 0),
                "languages": context.get("repo", {}).get("languages", {}),
                "hotspots": context.get("hotspots", [])[:20],
            },
            "candidate_files": context.get("candidate_files", [])[:40],
            "test_strategy": context.get("test_strategy", {}),
            "parallel_lanes": [
                {"lane": "implementation", "purpose": "coherent code change in isolated workspace", "approval": True},
                {"lane": "verification", "purpose": "focused tests and regression evidence", "approval": True},
                {"lane": "review", "purpose": "diff, dependency-impact and risk review", "approval": False},
            ],
            "recovery": {
                "enabled": True,
                "max_cycles": self.max_cycles,
                "bounded": True,
                "requires_new_evidence": True,
            },
        }

    @staticmethod
    def _evidence_summary(run: EngineeringRun) -> dict[str, Any]:
        tool_events = [e for e in run.evidence if e.get("event") == "tool"]
        names = []
        failures = []
        for event in tool_events:
            name = str(event.get("name", ""))
            if name:
                names.append(name)
            result = event.get("result") or {}
            nested = result.get("result") if isinstance(result, dict) else {}
            text = json.dumps(nested if isinstance(nested, dict) else result, ensure_ascii=False)
            if any(term in text.lower() for term in ("failed", "error", "assertionerror", "traceback")):
                failures.append(text[:1500])
        return {
            "tools": list(dict.fromkeys(names)),
            "verification_tools_seen": any(x in names for x in ("run_tests", "run_command")),
            "review_tools_seen": "review_diff" in names,
            "failures": failures[-8:],
        }

    def _recovery_objective(self, objective: str, run: EngineeringRun) -> str:
        summary = self._evidence_summary(run)
        failure = "\n".join(summary.get("failures") or [])
        if not failure:
            failure = "Execution did not reach a deterministic completion gate; inspect the latest evidence and continue from the existing checkpoint."
        return (
            f"Recover and complete the existing engineering objective: {objective}\n\n"
            "This is a bounded recovery cycle. Do not restart unrelated work. Inspect the latest repository state, "
            "reproduce the failure, make the smallest coherent repair, rerun focused verification, then regression-test "
            "and perform final diff review.\n\nLatest evidence:\n" + failure[:9000]
        )

    def run(self, objective: str, execute: bool = False, approval: bool = False,
            focus_files: list[str] | None = None) -> EngineeringFactoryResult:
        started = time.perf_counter()
        result = EngineeringFactoryResult(objective=objective, plan=self.prepare(objective, focus_files))
        current_objective = objective
        for cycle in range(1, self.max_cycles + 1):
            run = self.agent.run(current_objective, execute=execute, approval=approval)
            summary = self._evidence_summary(run)
            recovery_target = ""
            if run.status in {"needs_replan", "failed"} and cycle < self.max_cycles and execute:
                recovery_target = self._recovery_objective(objective, run)
            result.cycles.append(EngineeringCycle(
                cycle=cycle, objective=current_objective, status=run.status, phase=run.phase,
                run_id=run.run_id, iterations=run.iterations, tool_calls=run.tool_calls,
                evidence_count=len(run.evidence), recovery_target=recovery_target,
            ))
            result.final = run.final
            if run.status in {"completed", "awaiting_approval", "planned"}:
                result.status = run.status
                break
            if not recovery_target:
                result.status = run.status
                break
            current_objective = recovery_target
        else:
            result.status = result.cycles[-1].status if result.cycles else "failed"
        result.elapsed_seconds = time.perf_counter() - started
        return result
