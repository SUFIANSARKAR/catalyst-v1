from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .codebase import CodebaseIntelligence, DEFAULT_IGNORES, LANG


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    kind: str = "import"


class RepositoryIntelligence(CodebaseIntelligence):
    """Deeper repository intelligence built on deterministic source inspection.

    The graph is intentionally lightweight: it uses Python AST imports when possible,
    heuristic imports for common languages, and project manifests. It gives the model
    structure/coupling evidence without requiring an LSP daemon or embedding service.
    """

    def _python_imports(self, path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return []
        out: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                out.append(node.module)
        return out

    def _text_imports(self, path: Path, language: str) -> list[str]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        patterns = {
            "javascript": [r"(?:import|export).*?from\s*['\"]([^'\"]+)['\"]", r"require\(\s*['\"]([^'\"]+)['\"]"],
            "typescript": [r"(?:import|export).*?from\s*['\"]([^'\"]+)['\"]", r"require\(\s*['\"]([^'\"]+)['\"]"],
            "rust": [r"^\s*(?:pub\s+)?mod\s+([A-Za-z0-9_]+)", r"^\s*use\s+([A-Za-z0-9_:]+)"],
            "go": [r"^\s*\"([^\"]+)\"$"],
        }.get(language, [])
        out=[]
        for pattern in patterns:
            out.extend(re.findall(pattern, text, flags=re.M))
        return sorted(set(out))

    def _module_candidates(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for p, rel in self._iter_files():
            if p.suffix.lower() == ".py":
                stem = rel.with_suffix("")
                parts = list(stem.parts)
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                if parts:
                    mapping[".".join(parts)] = str(rel)
        return mapping

    def dependency_graph(self, max_edges: int = 12000) -> dict[str, Any]:
        files = self.inventory()
        module_map = self._module_candidates()
        edges: list[DependencyEdge] = []
        inbound: dict[str, int] = {}
        outbound: dict[str, int] = {}
        for rec in files:
            if rec.language not in {"python", "javascript", "typescript", "rust", "go"}:
                continue
            p = self.root / rec.path
            imports = self._python_imports(p) if rec.language == "python" else self._text_imports(p, rec.language)
            source = rec.path
            for target in imports:
                if len(edges) >= max_edges:
                    break
                target_path = module_map.get(target)
                if target_path:
                    target = target_path
                edge = DependencyEdge(source, str(target), "import")
                edges.append(edge)
                outbound[source] = outbound.get(source, 0) + 1
                inbound[str(target)] = inbound.get(str(target), 0) + 1
        hotspots = sorted(
            ({"path": p, "inbound": inbound.get(p, 0), "outbound": outbound.get(p, 0), "coupling": inbound.get(p, 0) + outbound.get(p, 0)} for p in set(inbound) | set(outbound)),
            key=lambda x: (-x["coupling"], -x["inbound"], x["path"]),
        )[:100]
        return {
            "protocol": "catalyst.repository-intelligence.v2",
            "root": str(self.root),
            "nodes": len(files),
            "edges": len(edges),
            "edges_truncated": len(edges) >= max_edges,
            "edges_sample": [asdict(e) for e in edges[:4000]],
            "hotspots": hotspots,
        }

    def architecture_snapshot(self) -> dict[str, Any]:
        repo = self.repo_map()
        graph = self.dependency_graph()
        manifests=[]
        for name in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "requirements.txt", "requirements-dev.txt", "Dockerfile", "docker-compose.yml", "compose.yml"):
            p=self.root/name
            if p.exists(): manifests.append(name)
        top_dirs={}
        for rec in self.inventory():
            root=rec.path.split("/")[0] if "/" in rec.path else "(root)"
            top_dirs[root]=top_dirs.get(root,0)+1
        return {
            "protocol": "catalyst.repository-intelligence.v2",
            "repo": repo,
            "dependency_graph": graph,
            "manifests": manifests,
            "top_level_distribution": dict(sorted(top_dirs.items(), key=lambda x:(-x[1],x[0]))[:80]),
        }

    def locate_symbol(self, name: str, kind: str = "") -> list[dict[str, Any]]:
        q=name.strip().lower()
        rows=[]
        for sym in self.symbols(limit=20000):
            if q not in sym.name.lower():
                continue
            if kind and sym.kind != kind:
                continue
            rows.append(asdict(sym))
            if len(rows)>=200: break
        return rows
