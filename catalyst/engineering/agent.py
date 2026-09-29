from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ..reasoning.tool_search import BoundedToolSearch
from .codebase import CodebaseIntelligence
from .tools import EngineeringToolbox
from .repository import RepositoryIntelligence
from .strategy import EngineeringTestStrategy
from .state import EngineeringStateStore


@dataclass
class EngineeringRun:
    objective: str
    run_id: str = ""
    phase: str = "recon"
    plan: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    status: str = "planned"
    iterations: int = 0
    tool_calls: int = 0
    final: str = ""
    pending_approval: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": "catalyst.engineering.v6",
            "objective": self.objective,
            "run_id": self.run_id,
            "phase": self.phase,
            "plan": self.plan,
            "evidence": self.evidence[-120:],
            "status": self.status,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "final": self.final,
            "pending_approval": self.pending_approval,
        }


class EngineeringAgent:
    """Catalyst's serious coding-agent loop.

    The model is a planner/reasoner; tools provide grounded repository access;
    sandbox execution verifies reality. Mutations and commands remain approval gated.
    """

    protocol = "catalyst.engineering.v6"

    def __init__(self, root: str, model: Callable[[list[dict[str, Any]], list[dict[str, Any]] | None], dict[str, Any]] | None = None,
                 executor: Callable[[str], dict[str, Any]] | None = None, max_iterations: int = 24,
                 data_root: str = "catalyst_data", sandbox=None, specialist_executor=None):
        self.root = root
        self.codebase = RepositoryIntelligence(root)
        self.repository = self.codebase
        self.test_strategy = EngineeringTestStrategy(root)
        self.state = EngineeringStateStore(str(__import__("pathlib").Path(data_root) / "engineering_runs.db"))
        self.model = model
        self.executor = executor
        self.max_iterations = max(1, min(int(max_iterations), 64))
        self.toolbox = EngineeringToolbox(root, data_root, sandbox=sandbox, specialist_executor=specialist_executor)

    def reconnaissance(self, objective: str) -> dict[str, Any]:
        m = self.codebase.repo_map()
        return {"protocol": self.protocol, "objective": objective, "repo_map": m, "evidence_level": "deterministic-recon"}

    def plan(self, objective: str) -> EngineeringRun:
        recon = self.reconnaissance(objective)
        run = EngineeringRun(objective=objective, evidence=[recon])
        if not self.model:
            run.plan = self._fallback_plan(objective)
            return run
        messages = [
            {"role": "system", "content": self._system_prompt() + "\nPlanning mode: do not mutate or execute; produce a JSON plan only."},
            {"role": "user", "content": json.dumps({"objective": objective, "repo": recon["repo_map"]}, ensure_ascii=False)[:200000]},
        ]
        try:
            response = self.model(messages, None)
            data = self._json_from_text(str(response.get("content", "")))
            run.plan = data.get("steps") or []
        except Exception as exc:
            run.evidence.append({"event": "planning_error", "error": str(exc)})
        if not run.plan:
            run.plan = self._fallback_plan(objective)
        return run

    def _fallback_plan(self, objective: str) -> list[dict[str, Any]]:
        return [
            {"id": "recon", "action": "inspect repository, tests, and relevant symbols", "verification": "grounded file evidence"},
            {"id": "diagnose", "action": f"identify the root cause of: {objective}", "verification": "specific failing behavior and source locations"},
            {"id": "implement", "action": "apply the smallest coherent change", "verification": "git diff reviewed"},
            {"id": "test", "action": "run focused tests and regression tests", "verification": "captured exit status and output"},
            {"id": "review", "action": "review final diff, tests, and unresolved risks", "verification": "evidence-backed completion"},
        ]

    def _system_prompt(self) -> str:
        return (
            "You are Catalyst's Engineering Executive. Work like a professional coding agent. "
            "Never claim a file changed, a test passed, or a command succeeded unless a tool result proves it. "
            "Start by understanding the repository and objective. Prefer search/read over guessing. "
            "For non-trivial changes, use an isolated Git worktree when available, then checkpoint before mutation. "
            "Use small, coherent edits. After edits, run focused verification, inspect failures, repair and retest; then run broader regression checks when practical. "
            "Do not declare an execution mission complete without deterministic verification evidence. "
            "Use parallel specialist delegation when independent coding, review, research, or engineering passes can improve correctness. "
            "Before final completion, run review_diff and require ready_for_completion=true in addition to deterministic test evidence. "
            "Do not expose secrets. Do not bypass approvals or workspace boundaries. "
            "When uncertain, say what evidence is missing."
        )

    @staticmethod
    def _json_from_text(text: str) -> dict[str, Any]:
        text = text.strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            return {}
        try:
            obj = json.loads(text[start:end + 1])
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}

    def execute_step(self, run: EngineeringRun, step: dict[str, Any], require_approval: bool = True) -> dict[str, Any]:
        if require_approval:
            result = {"status": "approval_required", "step": step}
        elif self.executor:
            result = self.executor(step.get("action") or step.get("target") or "")
        else:
            result = {"status": "no_executor", "step": step}
        run.evidence.append({"step": step, "result": result})
        return result

    def _tool_call(self, name: str, arguments: dict[str, Any], run: EngineeringRun, approved: bool) -> tuple[dict[str, Any], bool]:
        tool = self.toolbox.get(name)
        if not tool:
            return {"status": "tool_error", "error": f"Unknown tool: {name}"}, False
        if tool.requires_approval and not approved:
            pending = {"tool": name, "arguments": arguments, "requires_approval": True}
            run.pending_approval.append(pending)
            return {"status": "approval_required", **pending}, True
        try:
            result = tool.handler(**arguments)
            return {"status": "ok", "tool": name, "result": result}, False
        except Exception as exc:
            return {"status": "tool_error", "tool": name, "error": str(exc)}, False

    def run(self, objective: str, execute: bool = False, approval: bool = False) -> EngineeringRun:
        run_id = self.state.create(objective)
        run = self.plan(objective)
        run.run_id = run_id
        run.evidence.append({"event":"run_created","run_id":run_id})
        self.state.event(run_id,"recon",run.evidence[0] if run.evidence else {})
        if not self.model:
            run.phase = "execution" if execute else "planning"
            if execute:
                for step in run.plan:
                    run.iterations += 1
                    result = self.execute_step(run, step, require_approval=not approval)
                    if result.get("status") == "approval_required":
                        run.status = "awaiting_approval"
                        return run
                    if result.get("status") not in {"ok", "completed", "passed"}:
                        run.status = "needs_replan"
                        return run
                run.phase = "verification"
                run.status = "completed"
            return run

        run.phase = "investigation"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": f"Engineering objective:\n{objective}\n\nRepository root: {self.root}\nUse tools aggressively for evidence. Solve the objective, do not merely describe how."},
        ]
        pending = False
        verification_seen = False
        review_seen = False
        for _ in range(self.max_iterations):
            run.iterations += 1
            try:
                response = self.model(messages, self.toolbox.schemas())
            except Exception as exc:
                run.evidence.append({"event": "model_error", "error": str(exc)})
                run.status = "failed"
                self.state.update(run_id,status=run.status,phase=run.phase,payload=run.as_dict())
                self.state.event(run_id,"model_error",{"error":str(exc)})
                return run
            if not isinstance(response, dict):
                response = {"content": str(response)}
            tool_calls = response.get("tool_calls") or []
            assistant_message = {"role": "assistant", "content": response.get("content") or ""}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            messages.append(assistant_message)

            if not tool_calls:
                final = str(response.get("content") or "").strip()
                run.final = final
                if execute and (not verification_seen or not review_seen):
                    run.phase = "verification"
                    run.status = "needs_replan"
                    run.evidence.append({"event":"verification_required","message":"Execution mission requires deterministic test evidence and a final diff review before completion.","verification_seen":verification_seen,"review_seen":review_seen})
                else:
                    run.phase = "verification" if (verification_seen or review_seen) else ("investigation" if run.tool_calls else "planning")
                    run.status = "completed" if run.tool_calls else "planned"
                run.evidence.append({"event": "final", "content": final[:20000], "grounded": bool(run.tool_calls), "verification_seen": verification_seen})
                self.state.update(run_id,status=run.status,phase=run.phase,payload=run.as_dict())
                self.state.event(run_id,"final",{"content":final[:20000],"grounded":bool(run.tool_calls)})
                return run

            for call in tool_calls:
                run.tool_calls += 1
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                name = function.get("name") or call.get("name") or ""
                raw_args = function.get("arguments") or call.get("arguments") or {}
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be an object")
                except Exception as exc:
                    result, waiting = {"status": "tool_error", "error": f"Invalid arguments: {exc}"}, False
                else:
                    result, waiting = self._tool_call(name, args, run, approved=(execute and approval))
                if waiting:
                    pending = True
                messages.append({"role": "tool", "tool_call_id": call.get("id", f"call-{run.tool_calls}"), "content": json.dumps(result, ensure_ascii=False)[:50000]})
                run.evidence.append({"event": "tool", "name": name, "arguments": args, "result": result})
                if name == "review_diff" and result.get("status") == "ok":
                    nested = result.get("result") or {}
                    review_seen = bool(isinstance(nested, dict) and nested.get("ready_for_completion"))
                if name in {"run_tests", "run_command"} and result.get("status") == "ok":
                    nested = result.get("result") or {}
                    if isinstance(nested, dict) and nested.get("status") in {"completed", "passed", "ok"} and nested.get("returncode", 0) == 0:
                        verification_seen = True
                if waiting:
                    break
            if pending:
                run.status = "awaiting_approval"
                run.phase = "execution"
                return run
        run.status = "needs_replan"
        run.phase = "recovery"
        run.evidence.append({"event": "iteration_limit", "max_iterations": self.max_iterations})
        self.state.update(run_id,status=run.status,phase=run.phase,payload=run.as_dict())
        self.state.event(run_id,"iteration_limit",{"max_iterations":self.max_iterations})
        return run

    def bounded_replan(self, state: dict[str, Any], candidates, transition, validate) -> dict[str, Any]:
        search = BoundedToolSearch(max_depth=5, max_nodes=48, branch_limit=3)
        node = search.search(state, candidates, transition, validate)
        return {"found": bool(node and node.valid), "actions": node.actions if node else [], "score": node.score if node else None, "nodes_expanded": search.nodes_expanded, "trace": search.trace[-100:]}
