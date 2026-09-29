import json
from pathlib import Path

from catalyst.apex import ApexRuntime
from catalyst.reasoning import ClaimVerifier, ReasoningEngine, ReasoningMemory


def test_reasoning_engine_detects_mixed_objective_and_risk(tmp_path):
    engine = ReasoningEngine(ReasoningMemory(str(tmp_path / 'reasoning.db')))
    plan = engine.choose('research the latest repo security issue and then deploy the fix')
    assert plan.objective_type == 'engineering'
    assert plan.risk > 0.0
    assert plan.verification
    assert plan.evidence_required


def test_reasoning_engine_builds_dependency_order_and_refines_with_model(tmp_path):
    seen = {}
    def model(messages, tools):
        seen['called'] = True
        return {'content': json.dumps({'steps': [
            {'id':'u','phase':'understand','goal':'define success','depends_on':[]},
            {'id':'p','phase':'plan','goal':'rank options','depends_on':['u']},
            {'id':'v','phase':'verify','goal':'check outcome','depends_on':['p']},
            {'id':'r','phase':'report','goal':'report evidence','depends_on':['v']},
        ]})}
    engine = ReasoningEngine(ReasoningMemory(str(tmp_path / 'reasoning.db')), model=model)
    trace = engine.start('architect a solution')
    deterministic = engine.build_plan(trace)
    refined = engine.refine_plan(trace, deterministic)
    assert seen['called']
    assert [s['id'] for s in refined] == ['u','p','v','r']
    assert refined[2]['depends_on'] == ['p']


def test_reasoning_engine_rejects_invalid_model_plan(tmp_path):
    def model(messages, tools):
        return {'content': '{"steps":[{"id":"bad","phase":"act","goal":"invent","depends_on":["missing"]}]}' }
    engine = ReasoningEngine(ReasoningMemory(str(tmp_path / 'reasoning.db')), model=model)
    trace = engine.start('build software')
    deterministic = engine.build_plan(trace)
    assert engine.refine_plan(trace, deterministic) == deterministic


def test_claim_verifier_requires_actual_support():
    verifier = ClaimVerifier()
    unsupported = verifier.verify('The database migration definitely succeeded.', [])
    assert not unsupported.verified
    supported = verifier.verify('The migration succeeded.', [{'kind':'verification','statement':'Migration succeeded with returncode 0'}])
    assert supported.verified


def test_apex_runtime_creates_governed_unified_mission(tmp_path):
    memory = ReasoningMemory(str(tmp_path / 'reasoning.db'))
    apex = ApexRuntime(ReasoningEngine(memory=memory))
    mission = apex.plan('build and test a repository fix')
    assert mission.mission_id
    assert mission.reasoning.plan.objective_type == 'engineering'
    assert mission.governance['approval_required_for_consequential_actions']
    assert mission.plan[-1]['phase'] == 'report'
    assert 'repository-intelligence' in mission.capabilities
