from catalyst.apex import ApexRuntime
from catalyst.reasoning import ReasoningEngine, ReasoningMemory


def test_apex_route_reports_registered_handler(tmp_path):
    runtime = ApexRuntime(ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db"))))
    runtime.register_subsystem("engineering", lambda objective, mission=None: {"objective": objective}, label="engineering-factory")
    mission = runtime.plan("build and test a repository fix")
    route = runtime.route(mission)
    assert route["objective_type"] == "engineering"
    assert route["available"] is True
    assert route["handler"] == "engineering-factory"


def test_apex_dispatch_requires_approval_and_then_executes(tmp_path):
    calls=[]
    runtime = ApexRuntime(ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db"))))
    runtime.register_subsystem("engineering", lambda objective, mission=None: calls.append(objective) or {"ok": True})
    mission = runtime.plan("build and test a repository fix")
    blocked = runtime.dispatch(mission.mission_id, execute=True, approval=False)
    assert blocked["status"] == "approval_required"
    completed = runtime.dispatch(mission.mission_id, execute=True, approval=True)
    assert completed["status"] == "completed"
    assert calls == [mission.objective]
    assert completed["mission"]["state"] == "completed"


def test_apex_dispatch_without_handler_pauses_mission(tmp_path):
    runtime = ApexRuntime(ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db"))))
    mission = runtime.plan("research something carefully")
    result = runtime.dispatch(mission.mission_id, execute=True, approval=True)
    assert result["status"] == "unavailable"
    assert result["mission"]["state"] == "paused"


def test_apex_dispatch_persists_execution_evidence_and_failure_state(tmp_path):
    runtime = ApexRuntime(ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db"))))
    runtime.register_subsystem("engineering", lambda objective, mission=None: {"status": "failed", "error": "tests failed"})
    mission = runtime.plan("build and test a repository fix")
    result = runtime.dispatch(mission.mission_id, execute=True, approval=True)
    assert result["status"] == "failed"
    row = runtime.store.get(mission.mission_id)
    assert row["state"] == "failed"
    assert any(e.get("kind") == "failure" for e in (row["payload"].get("reasoning", {}).get("evidence") or []))
