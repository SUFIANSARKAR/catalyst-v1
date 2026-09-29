from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..execution.sandbox import SandboxRunner
from .repository import RepositoryIntelligence
from .git import WorktreeManager
from .strategy import EngineeringTestStrategy
from .intelligence import EngineeringIntelligence


@dataclass(frozen=True)
class EngineeringTool:
    name: str
    description: str
    parameters: dict[str, Any]
    requires_approval: bool
    handler: Any

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class EngineeringToolbox:
    """Real, bounded software-engineering tools for Catalyst's Monster loop.

    Read-only reconnaissance is available during planning. Mutating operations
    and command execution remain approval-gated. All filesystem operations are
    rooted in the target workspace.
    """

    def __init__(self, root: str, data_root: str, sandbox: SandboxRunner | None = None, specialist_executor=None):
        self.root = Path(root).resolve()
        self.data_root = Path(data_root).resolve()
        self.checkpoint_root = self.data_root / "monster_checkpoints"
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.sandbox = sandbox or SandboxRunner(str(self.root), str(self.data_root))
        self.repository = RepositoryIntelligence(str(self.root))
        self.worktrees = WorktreeManager(str(self.root), str(self.data_root / "monster_worktrees"))
        self.test_strategy = EngineeringTestStrategy(str(self.root))
        self.intelligence = EngineeringIntelligence(self.repository, self.test_strategy)
        self.specialist_executor = specialist_executor
        self._tools = {
            t.name: t
            for t in (
                EngineeringTool("repo_map", "Return deterministic repository structure, language counts, test files, symbols, and large files.", {"type": "object", "properties": {}}, False, self.repo_map),
                EngineeringTool("architecture_snapshot", "Build a deeper deterministic architecture snapshot including dependency edges, coupling hotspots, manifests, and top-level distribution.", {"type": "object", "properties": {}}, False, self.architecture_snapshot),
                EngineeringTool("dependency_graph", "Return lightweight source dependency/coupling evidence for the repository.", {"type": "object", "properties": {}}, False, self.dependency_graph),
                EngineeringTool("context_pack", "Build a bounded evidence-rich repository context pack for a coding objective.", {"type": "object", "properties": {"objective": {"type": "string"}, "focus_files": {"type": "array", "items": {"type": "string"}}, "max_files": {"type": "integer", "minimum": 1, "maximum": 80}, "max_chars": {"type": "integer", "minimum": 1000, "maximum": 300000}}, "required": ["objective"]}, False, self.context_pack),
                EngineeringTool("impact_analysis", "Estimate direct dependencies, reverse dependents, affected files, and tests for a change set.", {"type": "object", "properties": {"changed_files": {"type": "array", "items": {"type": "string"}}}, "required": ["changed_files"]}, False, self.impact_analysis),
                EngineeringTool("review_diff", "Perform a deterministic pre-completion code review of the current diff and test evidence.", {"type": "object", "properties": {"changed_files": {"type": "array", "items": {"type": "string"}}, "test_results": {"type": "array"}}, "required": ["changed_files"]}, False, self.review_diff),
                EngineeringTool("recovery_plan", "Classify a failure and produce a bounded deterministic repair loop.", {"type": "object", "properties": {"failure_text": {"type": "string"}, "changed_files": {"type": "array", "items": {"type": "string"}}}, "required": ["failure_text"]}, False, self.recovery_plan),
                EngineeringTool("locate_symbol", "Find source symbols by name and optional kind.", {"type": "object", "properties": {"name": {"type": "string"}, "kind": {"type": "string"}}, "required": ["name"]}, False, self.locate_symbol),
                EngineeringTool("list_files", "List files under a workspace-relative directory. Excludes build/cache directories.", {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}, False, self.list_files),
                EngineeringTool("search_code", "Search source text for a literal or regular-expression pattern and return matching file/line evidence.", {"type": "object", "properties": {"query": {"type": "string"}, "path": {"type": "string"}, "regex": {"type": "boolean"}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, "required": ["query"]}, False, self.search_code),
                EngineeringTool("read_file", "Read a bounded workspace file with line numbers for code investigation.", {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1}, "max_lines": {"type": "integer", "minimum": 1, "maximum": 1200}}, "required": ["path"]}, False, self.read_file),
                EngineeringTool("git_status", "Return repository Git status and current branch when available.", {"type": "object", "properties": {}}, False, self.git_status),
                EngineeringTool("git_diff", "Return the current working-tree diff, optionally limited to one file.", {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}, False, self.git_diff),
                EngineeringTool("worktree_list", "List Catalyst-managed Git worktrees and branches.", {"type": "object", "properties": {}}, False, self.worktree_list),
                EngineeringTool("worktree_create", "Create an isolated Git worktree/branch for a coding mission.", {"type": "object", "properties": {"mission_id": {"type": "string"}, "base_ref": {"type": "string"}}, "required": ["mission_id"]}, True, self.worktree_create),
                EngineeringTool("worktree_remove", "Remove an isolated Git worktree after a mission.", {"type": "object", "properties": {"path": {"type": "string"}, "force": {"type": "boolean"}}, "required": ["path"]}, True, self.worktree_remove),
                EngineeringTool("test_strategy", "Generate a deterministic focused+full test strategy from repository shape and changed files.", {"type": "object", "properties": {"changed_files": {"type": "array", "items": {"type": "string"}}}, "required": []}, False, self.test_strategy_plan),
                EngineeringTool("create_checkpoint", "Create a timestamped backup of selected files before mutation.", {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}, "label": {"type": "string"}}, "required": ["paths"]}, False, self.create_checkpoint),
                EngineeringTool("write_file", "Write a complete text file. Mutating and approval-gated.", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}, True, self.write_file),
                EngineeringTool("apply_patch", "Apply a standard unified diff to workspace files. Mutating and approval-gated.", {"type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]}, True, self.apply_patch),
                EngineeringTool("run_command", "Run a bounded command inside the workspace sandbox. Mutating/execution and approval-gated.", {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer", "minimum": 1, "maximum": 600}}, "required": ["command"]}, True, self.run_command),
                EngineeringTool("run_tests", "Discover and run a bounded focused test command. Mutating/execution and approval-gated.", {"type": "object", "properties": {"target": {"type": "string"}, "timeout": {"type": "integer", "minimum": 1, "maximum": 600}}, "required": []}, True, self.run_tests),
                EngineeringTool("delegate_specialist", "Delegate a bounded subtask to one of Catalyst's registered specialist agents and return the concrete result.", {"type": "object", "properties": {"agent": {"type": "string"}, "objective": {"type": "string"}, "cwd": {"type": "string"}, "wait": {"type": "boolean"}}, "required": ["agent", "objective"]}, True, self.delegate_specialist),
                EngineeringTool("delegate_specialists", "Run multiple bounded specialist passes in parallel and return independent evidence for synthesis.", {"type": "object", "properties": {"tasks": {"type": "array", "items": {"type": "object"}}, "max_workers": {"type": "integer", "minimum": 1, "maximum": 8}}, "required": ["tasks"]}, True, self.delegate_specialists),
            )
        }

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def get(self, name: str) -> EngineeringTool | None:
        return self._tools.get(name)

    def architecture_snapshot(self): return self.repository.architecture_snapshot()
    def dependency_graph(self): return self.repository.dependency_graph()
    def context_pack(self, objective: str, focus_files=None, max_files: int = 24, max_chars: int = 120000): return self.intelligence.context_pack(objective, focus_files, max_files, max_chars)
    def impact_analysis(self, changed_files): return self.intelligence.impact_analysis(changed_files or [])
    def review_diff(self, changed_files, test_results=None): return self.intelligence.review_report(self.git_diff().get("diff", ""), changed_files or [], test_results or [])
    def recovery_plan(self, failure_text: str, changed_files=None): return self.intelligence.recovery_plan(failure_text, changed_files or [])
    def locate_symbol(self, name: str, kind: str = ""): return self.repository.locate_symbol(name, kind)
    def worktree_list(self): return self.worktrees.list()
    def worktree_create(self, mission_id: str, base_ref: str = "HEAD"): return self.worktrees.create(mission_id, base_ref)
    def worktree_remove(self, path: str, force: bool = False): return self.worktrees.remove(path, force)
    def test_strategy_plan(self, changed_files=None): return self.test_strategy.plan(changed_files or [])
    def delegate_specialist(self, agent: str, objective: str, cwd: str = ".", wait: bool = True):
        if not self.specialist_executor: return {"status":"unavailable","reason":"specialist executor not connected"}
        result = self.specialist_executor.run([{"id":"monster-delegation","title":objective,"description":objective,"agent":agent,"cwd":cwd,"wait":wait}], max_workers=1, synthesize=False)
        return result
    def delegate_specialists(self, tasks, max_workers: int = 4):
        if not self.specialist_executor: return {"status":"unavailable","reason":"specialist executor not connected"}
        normalized=[]
        for i, item in enumerate((tasks or [])[:8]):
            if not isinstance(item, dict) or not item.get("objective"):
                continue
            normalized.append({"id": item.get("id", f"monster-{i}"), "title": item.get("title", item["objective"]), "description": item["objective"], "agent": item.get("agent", "general"), "cwd": item.get("cwd", "."), "wait": bool(item.get("wait", True))})
        if not normalized: return {"status":"empty","results":[]}
        return self.specialist_executor.run(normalized, max_workers=max(1,min(int(max_workers),8)), synthesize=False)

    def _resolve(self, relative: str) -> Path:
        p = (self.root / relative).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError("Path escapes workspace root")
        return p

    def _iter_files(self):
        ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", ".next", "target"}
        for p in self.root.rglob("*"):
            if p.is_file() and not any(part in ignored for part in p.parts):
                yield p

    def repo_map(self) -> dict[str, Any]:
        files = []
        languages: dict[str, int] = {}
        tests: list[str] = []
        suffixes = {".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript", ".rs": "rust", ".go": "go", ".java": "java", ".cpp": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".kt": "kotlin", ".swift": "swift"}
        for p in self._iter_files():
            rel = str(p.relative_to(self.root))
            lang = suffixes.get(p.suffix.lower(), "other")
            try:
                size = p.stat().st_size
                text = p.read_text(encoding="utf-8", errors="ignore")
                lines = text.count("\n") + (1 if text else 0)
            except OSError:
                continue
            files.append((rel, lang, size, lines))
            languages[lang] = languages.get(lang, 0) + 1
            if re.search(r"(^|/)(tests?/|test_|.*_test\.|.*\.spec\.)", rel, re.I):
                tests.append(rel)
        files.sort(key=lambda x: x[2], reverse=True)
        return {
            "root": str(self.root),
            "file_count": len(files),
            "total_bytes": sum(x[2] for x in files),
            "total_lines": sum(x[3] for x in files),
            "languages": dict(sorted(languages.items(), key=lambda kv: (-kv[1], kv[0]))),
            "test_files": tests[:1000],
            "largest_files": [{"path": p, "language": l, "bytes": b, "lines": n} for p, l, b, n in files[:80]],
        }

    def list_files(self, path: str = ".") -> list[str]:
        base = self._resolve(path or ".")
        if not base.exists():
            raise FileNotFoundError(path)
        if base.is_file():
            return [str(base.relative_to(self.root))]
        return [str(p.relative_to(self.root)) for p in sorted(base.rglob("*")) if p.is_file()][:3000]

    def search_code(self, query: str, path: str = ".", regex: bool = False, limit: int = 50) -> dict[str, Any]:
        base = self._resolve(path or ".")
        if not base.exists():
            raise FileNotFoundError(path)
        pattern = re.compile(query, re.I | re.M) if regex else None
        hits = []
        for p in self._iter_files():
            if base != self.root and base not in p.parents and p != base:
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, 1):
                matched = bool(pattern.search(line)) if pattern else query.lower() in line.lower()
                if matched:
                    hits.append({"path": str(p.relative_to(self.root)), "line": idx, "text": line[:1000]})
                    if len(hits) >= min(max(1, int(limit)), 200):
                        return {"query": query, "regex": regex, "hits": hits, "truncated": True}
        return {"query": query, "regex": regex, "hits": hits, "truncated": False}

    def read_file(self, path: str, start_line: int = 1, max_lines: int = 600) -> dict[str, Any]:
        p = self._resolve(path)
        if not p.is_file():
            raise FileNotFoundError(path)
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(1, int(start_line))
        end = min(len(lines), start + min(max(1, int(max_lines)), 1200) - 1)
        body = "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))
        return {"path": str(p.relative_to(self.root)), "start_line": start, "end_line": end, "total_lines": len(lines), "content": body}

    def git_status(self) -> dict[str, Any]:
        if not (self.root / ".git").exists():
            return {"git": False, "reason": "not a git repository"}
        cp = subprocess.run(["git", "status", "--short", "--branch"], cwd=self.root, text=True, capture_output=True, timeout=30)
        return {"git": True, "returncode": cp.returncode, "status": cp.stdout[-12000:], "stderr": cp.stderr[-4000:]}

    def git_diff(self, path: str = "") -> dict[str, Any]:
        args = ["git", "diff", "--no-ext-diff", "--unified=80"]
        if path:
            args += ["--", str(self._resolve(path).relative_to(self.root))]
        cp = subprocess.run(args, cwd=self.root, text=True, capture_output=True, timeout=30)
        return {"returncode": cp.returncode, "diff": cp.stdout[-80000:], "stderr": cp.stderr[-6000:]}

    def create_checkpoint(self, paths: list[str], label: str = "checkpoint") -> dict[str, Any]:
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label or "checkpoint")[:80]
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = self.checkpoint_root / f"{stamp}-{safe_label}"
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for rel in paths[:200]:
            src = self._resolve(rel)
            if src.is_file():
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)
                copied.append(rel)
        manifest = {"created_at": time.time(), "root": str(self.root), "paths": copied}
        (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"checkpoint": str(dest), "copied": copied}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        p = self._resolve(path)
        old = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "ok", "path": path, "bytes": len(content.encode("utf-8")), "changed": old != content}

    def apply_patch(self, patch: str) -> dict[str, Any]:
        # Use git apply for robust unified-diff semantics and path containment.
        if not patch.strip():
            raise ValueError("patch is empty")
        cp = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], input=patch, cwd=self.root, text=True, capture_output=True, timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(f"git apply failed: {cp.stderr[-8000:]}")
        return {"status": "ok", "applied": True, "stdout": cp.stdout[-4000:], "stderr": cp.stderr[-4000:]}

    def run_command(self, command: str, cwd: str = ".", timeout: int = 120) -> dict[str, Any]:
        requested = max(1, min(int(timeout), 600))
        result = self.sandbox.run(command, cwd)
        return asdict(result) | {"requested_timeout": requested}

    def _test_command(self, target: str = "") -> str:
        if (self.root / "pytest.ini").exists() or (self.root / "pyproject.toml").exists() or (self.root / "pytest.toml").exists():
            if target:
                return f"python -m pytest -q {target}"
            return "python -m pytest -q"
        if (self.root / "package.json").exists():
            return "npm test -- --runInBand"
        if (self.root / "Cargo.toml").exists():
            return "cargo test"
        if (self.root / "go.mod").exists():
            return "go test ./..."
        return "python -m compileall -q ."

    def run_tests(self, target: str = "", timeout: int = 300) -> dict[str, Any]:
        command = self._test_command(target)
        result = self.sandbox.run(command, ".")
        out = asdict(result)
        out["command"] = command
        return out
