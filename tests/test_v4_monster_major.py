import json
from pathlib import Path

from catalyst.engineering.repository import RepositoryIntelligence
from catalyst.engineering.git import WorktreeManager
from catalyst.engineering.strategy import EngineeringTestStrategy
from catalyst.engineering.state import EngineeringStateStore
from catalyst.engineering.tools import EngineeringToolbox
from catalyst.engineering.agent import EngineeringAgent


def test_repository_intelligence_builds_python_dependency_graph(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "a.py").write_text("from pkg.b import value\n\nclass Alpha:\n    pass\n")
    (tmp_path / "pkg" / "b.py").write_text("value = 1\n")
    info = RepositoryIntelligence(str(tmp_path))
    graph = info.dependency_graph()
    assert graph["nodes"] >= 3
    assert any(edge["source"].endswith("a.py") and edge["target"].endswith("b.py") for edge in graph["edges_sample"])
    assert info.locate_symbol("Alpha")


def test_test_strategy_detects_pytest_and_focus(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "test_app.py").write_text("def test_app(): assert True\n")
    strategy = EngineeringTestStrategy(str(tmp_path)).plan(["app.py"])
    assert strategy["framework"] == "pytest"
    assert strategy["commands"]


def test_state_store_round_trip(tmp_path):
    store = EngineeringStateStore(str(tmp_path / "runs.db"))
    rid = store.create("fix bug")
    store.event(rid, "checkpoint", {"ok": True})
    store.update(rid, status="completed", phase="verification", payload={"evidence": [1]})
    row = store.get(rid)
    assert row["status"] == "completed"
    assert row["events"][0]["kind"] == "checkpoint"


def test_worktree_manager_reports_non_git_repo(tmp_path):
    manager = WorktreeManager(str(tmp_path), str(tmp_path / "data"))
    assert manager.status()["git"] is False
    assert manager.list()["worktrees"] == []


def test_worktree_manager_creates_and_removes_isolated_branch(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Catalyst Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    manager = WorktreeManager(str(tmp_path), str(tmp_path / "data"))
    created = manager.create("mission-1")
    assert created["created"] is True
    assert any(w.get("branch") == created["branch"] for w in manager.list()["worktrees"])
    removed = manager.remove(created["path"])
    assert removed["removed"] is True


def test_engineering_toolbox_exposes_major_engineering_tools(tmp_path):
    box = EngineeringToolbox(str(tmp_path), str(tmp_path / "data"))
    names = {item["function"]["name"] for item in box.schemas()}
    assert {"architecture_snapshot", "dependency_graph", "worktree_create", "test_strategy", "delegate_specialist"} <= names


def test_execution_requires_verification(tmp_path):
    (tmp_path / "app.py").write_text("print('x')\n")
    calls=[]
    def model(messages, tools):
        calls.append(messages)
        if len(calls) == 1:
            return {"content":"", "tool_calls":[{"id":"1","type":"function","function":{"name":"read_file","arguments":json.dumps({"path":"app.py"})}}]}
        return {"content":"I think this is complete."}
    agent=EngineeringAgent(str(tmp_path), model=model, max_iterations=3, data_root=str(tmp_path/"data"))
    run=agent.run("review the application", execute=True, approval=True)
    assert run.status == "needs_replan"
    assert any(e.get("event") == "verification_required" for e in run.evidence)
