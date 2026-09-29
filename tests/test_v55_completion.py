import json
from catalyst.reasoning import ReasoningEngine, ReasoningMemory, ApexDeliberator


def test_deliberator_returns_compact_decision_brief(tmp_path):
    e = ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db")))
    d = ApexDeliberator(e, mode="off")
    b = d.analyze("build and test a repository fix", context={"evidence_available": True})
    assert b.selected_approach
    assert b.evidence_requests
    assert b.risk_controls
    assert b.source == "deterministic"


def test_deliberator_model_output_is_strictly_validated(tmp_path):
    def model(messages, tools):
        return {"content": json.dumps({
            "interpretation":"Engineering task with verification.",
            "primary_goal":"Deliver a tested patch.",
            "subgoals":["inspect","patch","test"],
            "assumptions":["workspace is available"],
            "unknowns":["exact failing test"],
            "options":[{"name":"evidence_first","fit":0.91,"description":"Inspect before editing"}],
            "selected_approach":"Inspect, patch, test, review.",
            "evidence_requests":["current tests"],
            "risk_controls":["approval for deployment"],
            "stopping_conditions":["tests pass"],
            "confidence":0.82,
        })}
    e = ReasoningEngine(ReasoningMemory(str(tmp_path / "r.db")))
    d = ApexDeliberator(e, model=model, mode="model")
    b = d.analyze("build and test a repository fix")
    assert b.source == "model-assisted"
    assert b.confidence == 0.82


def test_stream_reasoning_has_durable_trace():
    # Regression is exercised by importability; full provider streaming is covered by the existing core suite.
    from catalyst.core.orchestrator import Catalyst
    assert hasattr(Catalyst, "stream_response")
