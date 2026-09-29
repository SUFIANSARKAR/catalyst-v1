from catalyst.cognitive import CognitiveStateStore, CognitiveLoop
from catalyst.mind import CatalystMind
from catalyst.memory import MemoryStore
from catalyst.memory.knowledge import KnowledgeMemory
from catalyst.memory.working import WorkingMemory


def test_cognitive_state_persists_objectives_and_episodes(tmp_path):
    s=CognitiveStateStore(str(tmp_path/'c.db'))
    oid=s.objective('Build the engineering intelligence core',priority=.95)
    s.set('focus',{'project':'TC ENGINEERING AI'})
    s.episode('Implemented persistent memory')
    assert oid
    assert s.active_objectives(5)[0]['title'].startswith('Build')
    assert s.get('focus')['project']=='TC ENGINEERING AI'
    assert s.recent_episodes(5)[0]['summary'].startswith('Implemented')
    s.close()


def test_cognitive_loop_records_experience_without_making_arbitrary_facts(tmp_path):
    mem=MemoryStore(str(tmp_path/'memory.db'))
    mind=CatalystMind(str(tmp_path/'mind.db'),mem)
    working=WorkingMemory(str(tmp_path/'working.json'))
    state=CognitiveStateStore(str(tmp_path/'state.db'))
    knowledge=KnowledgeMemory(mem)
    loop=CognitiveLoop(mind,knowledge,working,state)
    loop.before_turn('Please investigate the failing build', 's1')
    loop.after_turn('Please investigate the failing build','I found the failure and verified the fix.','s1',['run_tests'],True,3)
    assert state.get('current_task')=='Please investigate the failing build'
    assert len(state.recent_episodes())==1
    assert any('Request: Please investigate the failing build' in x.get('text','') for x in mem.search('Please investigate the failing build',20))
