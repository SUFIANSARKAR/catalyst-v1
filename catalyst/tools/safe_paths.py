from pathlib import Path

class WorkspaceGuard:
    def __init__(self, root: str): self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
    def resolve(self, path: str) -> Path:
        p = Path(path)
        candidate = (self.root / p).resolve() if not p.is_absolute() else p.resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise PermissionError(f"Path escapes Catalyst workspace: {path}")
        return candidate
