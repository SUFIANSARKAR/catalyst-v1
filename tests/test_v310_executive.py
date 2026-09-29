from catalyst.executive import CognitiveExecutive
from catalyst.cognitive import CognitiveStateStore
from catalyst.mind import CatalystMind
from catalyst.memory import MemoryStore
from catalyst.proactive import SituationalStore, SituationalEngine
from catalyst.missions import MissionStore

class FakeCatalyst:
    class S: mission_max_steps=4
    settings=S()
    def plan_mission(self, title):
        return {'objective':title,'steps':[{'name':'Inspect','kind':'chat','task':title},{'name':'Verify','kind':'chat','task':'verify'}]}

def test_executive_ranks_and_prepares_objective(tmp_path):
    state=CognitiveStateStore(str(tmp_path/'state.db')); mem=MemoryStore(str(tmp_path/'m.db')); mind=CatalystMind(str(tmp_path/'mind.db'),mem)
    ms=MissionStore(str(tmp_path/'missions.db')); ss=SituationalStore(str(tmp_path/'situational.db')); sit=SituationalEngine(ss,missions=ms)
    state.objective('Build the engineering intelligence core',priority=.95)
    ex=CognitiveExecutive(str(tmp_path/'exec.db'),state,mind,sit,ms)
    ranked=ex.rank_objectives(5)
    assert ranked[0]['title'].startswith('Build')
    result=ex.prepare_cycle(FakeCatalyst())
    assert result['status']=='prepared' and result['plan']['steps']
    assert ex.stats()['cycles']==1
