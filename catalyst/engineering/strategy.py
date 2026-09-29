from __future__ import annotations

from pathlib import Path
from typing import Any


class EngineeringTestStrategy:
    """Deterministic test-plan generator from repository shape and changed files."""
    def __init__(self, root: str): self.root=Path(root).resolve()

    def detect(self) -> dict[str,Any]:
        if (self.root/"pyproject.toml").exists() or (self.root/"pytest.ini").exists():
            return {"framework":"pytest","commands":["python -m pytest -q"],"compile":"python -m compileall -q ."}
        if (self.root/"package.json").exists():
            return {"framework":"node","commands":["npm test -- --runInBand"],"compile":"npm run build --if-present"}
        if (self.root/"Cargo.toml").exists(): return {"framework":"cargo","commands":["cargo test"],"compile":"cargo check"}
        if (self.root/"go.mod").exists(): return {"framework":"go","commands":["go test ./..."],"compile":"go test ./..."}
        return {"framework":"unknown","commands":["python -m compileall -q ."],"compile":"python -m compileall -q ."}

    def plan(self, changed_files: list[str]|None=None) -> dict[str,Any]:
        base=self.detect(); changed=changed_files or []
        focused=[]
        for path in changed:
            p=Path(path)
            name=p.name.lower()
            if name.startswith("test_") or name.endswith(("_test.py",".spec.ts",".test.ts",".spec.js",".test.js")):
                focused.append(path)
        for path in changed:
            p=Path(path)
            stem=p.stem
            if not focused and base["framework"]=="pytest":
                candidate=self._find_related_pytest(stem)
                if candidate: focused.append(candidate)
        commands=[]
        if focused and base["framework"]=="pytest": commands.append("python -m pytest -q " + " ".join(focused[:12]))
        commands.extend(base["commands"])
        return {"protocol":"catalyst.test-strategy.v2","framework":base["framework"],"focused":focused,"commands":commands[:8],"compile":base["compile"]}

    def _find_related_pytest(self, stem:str)->str|None:
        for p in self.root.rglob("test_*.py"):
            if stem.lower() in p.name.lower() or stem.lower() in p.read_text(encoding="utf-8",errors="ignore")[:20000].lower():
                return str(p.relative_to(self.root))
        return None
