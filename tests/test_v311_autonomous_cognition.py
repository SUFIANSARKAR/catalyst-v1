from catalyst.autonomy import AutonomousCognition
from catalyst.executive import CognitiveExecutive
from catalyst.cognitive import CognitiveStateStore
from catalyst.mind import CatalystMind
from catalyst.memory import MemoryStore
from catalyst.proactive import SituationalStore, SituationalEngine
from catalyst.missions import MissionStore
from catalyst.jobs.store import JobStore

class FakeCatalyst:
    def plan_mission(self, title):
        return {'objective': title, 'steps':[{'name':'inspect','kind':'chat','task':title}]}

def test_autonomous_cognition_prepares_manual_objective(tmp_path):
    mem=MemoryStore(str(tmp_path/'m.db')); mind=CatalystMind(str(tmp_path/'mind.db'),mem); state=CognitiveStateStore(str(tmp_path/'state.db'))
    missions=MissionStore(str(tmp_path/'missions.db')); jobs=JobStore(str(tmp_path/'jobs.db')); sit=SituationalEngine(SituationalStore(str(tmp_path/'sit.db')),missions=missions)
    oid=state.objective('Review the engineering project',priority=.9,metadata={'autonomy':'manual'})
    ex=CognitiveExecutive(str(tmp_path/'ex.db'),state,mind,sit,missions); ac=AutonomousCognition(str(tmp_path/'auto.db'),ex,mind,state,sit,missions,jobs)
    result=ac.run_once(catalyst=FakeCatalyst())
    assert result['deliberation']['decision']=='prepare_for_approval'
    assert result['dispatch']['status']=='awaiting_approval'

def test_autonomous_cognition_dispatches_approved_objective(tmp_path):
    mem=MemoryStore(str(tmp_path/'m.db')); mind=CatalystMind(str(tmp_path/'mind.db'),mem); state=CognitiveStateStore(str(tmp_path/'state.db'))
    missions=MissionStore(str(tmp_path/'missions.db')); jobs=JobStore(str(tmp_path/'jobs.db')); sit=SituationalEngine(SituationalStore(str(tmp_path/'sit.db')),missions=missions)
    state.objective('Run diagnostics on the workspace',priority=.95,metadata={'autonomy':'approved'})
    ex=CognitiveExecutive(str(tmp_path/'ex.db'),state,mind,sit,missions); ac=AutonomousCognition(str(tmp_path/'auto.db'),ex,mind,state,sit,missions,jobs)
    result=ac.run_once(catalyst=FakeCatalyst())
    assert result['deliberation']['decision']=='auto_dispatch'
    assert result['dispatch']['status']=='dispatched'
    assert jobs.list()[0]['kind']=='mission'

def test_autonomous_outcome_reconciles_objective(tmp_path):
    mem=MemoryStore(str(tmp_path/'m.db')); mind=CatalystMind(str(tmp_path/'mind.db'),mem); state=CognitiveStateStore(str(tmp_path/'state.db'))
    missions=MissionStore(str(tmp_path/'missions.db')); jobs=JobStore(str(tmp_path/'jobs.db')); sit=SituationalEngine(SituationalStore(str(tmp_path/'sit.db')),missions=missions)
    oid=state.objective('Finish the diagnostic mission',priority=.9,metadata={'autonomy':'approved'})
    ex=CognitiveExecutive(str(tmp_path/'ex.db'),state,mind,sit,missions); ac=AutonomousCognition(str(tmp_path/'auto.db'),ex,mind,state,sit,missions,jobs)
    result=ac.run_once(catalyst=FakeCatalyst())
    mid=result['dispatch']['mission_id']; missions.update(mid,'completed',result={'ok':True})
    ac.run_once(dispatch=False)
    assert state.active_objectives(5)[0]['status'] != 'active' if state.active_objectives(5) else True
