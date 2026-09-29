from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any


class WorktreeManager:
    """Git worktree isolation for Catalyst coding missions."""
    def __init__(self, root: str, storage: str = "catalyst_data/worktrees"):
        self.root=Path(root).resolve()
        self.storage=Path(storage).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)

    def _git(self, *args: str, cwd: Path|None=None, timeout: int=60) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd or self.root, text=True, capture_output=True, timeout=timeout)

    def available(self) -> bool:
        return (self.root/".git").exists() or subprocess.run(["git","-C",str(self.root),"rev-parse","--git-dir"],text=True,capture_output=True).returncode==0

    def status(self) -> dict[str,Any]:
        if not self.available(): return {"git":False,"reason":"not a git repository"}
        head=self._git("rev-parse","--abbrev-ref","HEAD")
        status=self._git("status","--short","--branch")
        return {"git":True,"branch":head.stdout.strip(),"status":status.stdout[-20000:],"stderr":status.stderr[-4000:]}

    def list(self) -> dict[str,Any]:
        if not self.available(): return {"git":False,"worktrees":[]}
        cp=self._git("worktree","list","--porcelain")
        rows=[]; current=None
        for line in cp.stdout.splitlines():
            if line.startswith("worktree "):
                if current: rows.append(current)
                current={"path":line[9:]}
            elif current is not None and line.startswith("HEAD "):
                current["head"]=line[5:]
            elif current is not None and line.startswith("branch "):
                current["branch"]=line[7:].removeprefix("refs/heads/")
            elif current is not None and line=="detached":
                current["detached"]=True
        if current: rows.append(current)
        return {"git":True,"worktrees":rows,"stderr":cp.stderr[-4000:]}

    def create(self, mission_id: str, base_ref: str = "HEAD") -> dict[str,Any]:
        if not self.available(): raise RuntimeError("Worktrees require a git repository")
        safe=re.sub(r"[^A-Za-z0-9_.-]+","-",mission_id).strip("-")[:60] or "mission"
        stamp=time.strftime("%Y%m%d-%H%M%S")
        branch=f"catalyst/{safe}-{stamp}"
        dest=self.storage/branch.replace("/","__")
        if dest.exists(): raise FileExistsError(dest)
        cp=self._git("worktree","add","-b",branch,str(dest),base_ref,timeout=120)
        if cp.returncode!=0: raise RuntimeError(cp.stderr[-8000:] or cp.stdout[-8000:])
        return {"path":str(dest),"branch":branch,"base":base_ref,"created":True}

    def remove(self, path: str, force: bool=False) -> dict[str,Any]:
        p=Path(path).resolve()
        if p == self.root: raise PermissionError("Cannot remove the primary worktree")
        args=["worktree","remove"] + (["--force"] if force else []) + [str(p)]
        cp=self._git(*args,timeout=120)
        return {"removed":cp.returncode==0,"path":str(p),"stdout":cp.stdout[-4000:],"stderr":cp.stderr[-8000:],"returncode":cp.returncode}
