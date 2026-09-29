import tempfile
from pathlib import Path
from catalyst.memory import MemoryStore
from catalyst.reasoning import ReasoningRouter
from catalyst.tools.safe_paths import WorkspaceGuard

def test_memory_search():
    with tempfile.TemporaryDirectory() as d:
        m=MemoryStore(str(Path(d)/"m.db")); m.add("TC Engineering uses a security boundary","project"); assert m.search("security boundary")

def test_reasoning_router():
    r=ReasoningRouter(); assert r.choose("fix this repository bug").agent=="engineering"; assert r.choose("hello").strategy=="direct"

def test_workspace_guard():
    with tempfile.TemporaryDirectory() as d:
        g=WorkspaceGuard(d); assert g.resolve("a.txt").parent==Path(d).resolve();
        try: g.resolve("../secret.txt")
        except PermissionError: pass
        else: raise AssertionError("escape allowed")
