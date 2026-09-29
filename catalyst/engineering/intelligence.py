from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any


class EngineeringIntelligence:
    """Higher-order deterministic context, impact, review and recovery intelligence.

    This layer does not edit code itself. It converts a large repository into compact,
    evidence-backed structures that an agent can reason over repeatedly.
    """

    def __init__(self, repository, test_strategy):
        self.repository = repository
        self.test_strategy = test_strategy

    def context_pack(self, objective: str, focus_files: list[str] | None = None,
                     max_files: int = 24, max_chars: int = 120_000) -> dict[str, Any]:
        focus = [str(x) for x in (focus_files or []) if x]
        repo = self.repository.repo_map()
        graph = self.repository.dependency_graph()
        candidates: list[str] = []
        seen = set()
        for item in focus:
            if item not in seen:
                candidates.append(item); seen.add(item)
        terms = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", objective)][:20]
        for rec in repo.get("largest_files", []):
            path = rec["path"]
            if path in seen:
                continue
            if any(term in path.lower() for term in terms):
                candidates.append(path); seen.add(path)
        for edge in graph.get("hotspots", []):
            path = edge["path"]
            if path in seen:
                continue
            if edge.get("coupling", 0) >= 2:
                candidates.append(path); seen.add(path)
            if len(candidates) >= max_files:
                break
        candidates = candidates[:max(1, min(int(max_files), 80))]
        excerpts = []
        total = 0
        root = Path(self.repository.root)
        for rel in candidates:
            p = (root / rel).resolve()
            if root not in p.parents and p != root or not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            remaining = max_chars - total
            if remaining <= 0:
                break
            body = text[:min(18_000, remaining)]
            excerpts.append({"path": rel, "content": body, "truncated": len(body) < len(text)})
            total += len(body)
        return {
            "protocol": "catalyst.engineering-intelligence.v1",
            "objective": objective,
            "candidate_files": candidates,
            "excerpts": excerpts,
            "repo": repo,
            "hotspots": graph.get("hotspots", [])[:40],
            "test_strategy": self.test_strategy.plan(candidates),
            "char_count": total,
        }

    def impact_analysis(self, changed_files: list[str]) -> dict[str, Any]:
        changed = {str(x).replace("\\", "/") for x in (changed_files or []) if x}
        graph = self.repository.dependency_graph()
        forward = defaultdict(list)
        reverse = defaultdict(list)
        for edge in graph.get("edges_sample", []):
            src, dst = edge.get("source"), edge.get("target")
            if src and dst:
                forward[src].append(dst); reverse[dst].append(src)
        direct = sorted(changed)
        dependents = sorted({p for target in changed for p in reverse.get(target, [])})
        dependencies = sorted({p for source in changed for p in forward.get(source, [])})
        affected = sorted(set(direct) | set(dependents) | set(dependencies))
        return {
            "changed_files": direct,
            "direct_dependencies": dependencies,
            "reverse_dependents": dependents,
            "affected_files": affected[:500],
            "affected_count": len(affected),
            "test_strategy": self.test_strategy.plan(affected[:200]),
        }

    def review_report(self, diff: str, changed_files: list[str], test_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        tests = list(test_results or [])
        risks: list[str] = []
        diff_text = diff or ""
        if len(diff_text) > 120_000:
            risks.append("large-diff")
        if re.search(r"TODO|FIXME|XXX", diff_text, re.I):
            risks.append("unfinished-markers")
        if re.search(r"except\s+Exception\s*:\s*pass", diff_text):
            risks.append("silent-exception")
        if re.search(r"subprocess\.run\([^\n]*shell\s*=\s*True", diff_text):
            risks.append("shell-true")
        if re.search(r"verify=False", diff_text):
            risks.append("tls-verification-disabled")
        failures = []
        for row in tests:
            if isinstance(row, dict) and row.get("returncode", 0) not in (0, None):
                failures.append(row)
        return {
            "protocol": "catalyst.engineering-review.v1",
            "changed_files": list(dict.fromkeys(changed_files or [])),
            "diff_bytes": len(diff_text.encode("utf-8")),
            "risks": risks,
            "test_count": len(tests),
            "test_failures": len(failures),
            "ready_for_completion": not failures and "shell-true" not in risks and "tls-verification-disabled" not in risks,
        }

    def recovery_plan(self, failure_text: str, changed_files: list[str] | None = None) -> dict[str, Any]:
        text = (failure_text or "").strip()
        category = "unknown"
        if re.search(r"(ModuleNotFoundError|ImportError)", text, re.I):
            category = "dependency-or-import"
        elif re.search(r"(SyntaxError|IndentationError)", text, re.I):
            category = "syntax"
        elif re.search(r"(AssertionError|FAILED|test_.*failed)", text, re.I):
            category = "test-regression"
        elif re.search(r"(Timeout|timed out|deadline)", text, re.I):
            category = "timeout"
        elif re.search(r"(PermissionError|permission denied)", text, re.I):
            category = "permissions"
        return {
            "protocol": "catalyst.engineering-recovery.v1",
            "category": category,
            "failure": text[:20_000],
            "changed_files": list(changed_files or []),
            "actions": [
                "inspect the failing symbol and nearest call site",
                "reproduce with the narrowest deterministic test or command",
                "make one coherent repair",
                "rerun focused verification",
                "rerun regression verification before completion",
            ],
        }
