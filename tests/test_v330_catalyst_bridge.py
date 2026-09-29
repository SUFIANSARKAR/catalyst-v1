import json
from pathlib import Path
import importlib.util
import pytest

from catalyst.memory.store import MemoryStore
from catalyst.memory.knowledge import KnowledgeMemory
from catalyst.memory.working import WorkingMemory
from catalyst.world_model import WorldModel
from catalyst.computer_use import PlaywrightComputerUse, ComputerUsePolicy, BrowserObservation, ComputerUsePlanner
from catalyst.perception import PerceptionStore
from catalyst.missions import MissionStore


def test_world_model_temporal_graph_and_knowledge(tmp_path):
    mem = MemoryStore(str(tmp_path / 'memory.db'))
    graph = WorldModel(str(tmp_path / 'world.db'))
    km = KnowledgeMemory(mem, graph)
    km.remember('Catalyst is the active project for Creator', 'decision', {'entities':['Catalyst','Creator']}, 0.9)
    a = graph.facts('Catalyst')
    assert a
    n = graph.neighborhood('Catalyst')
    assert n['nodes']
    assert any(x['name'] == 'Creator' for x in n['nodes'])
    mem.close(); graph.close()


def test_working_memory_compacts(tmp_path):
    wm = WorkingMemory(tmp_path / 'working.json', max_chars=5000, keep_recent=3)
    for i in range(30): wm.append('user', 'x' * 400, {'i': i})
    assert Path(tmp_path / 'working.json').exists()
    assert sum(len(x['content']) for x in wm.context()) <= 5000
    assert any(x['metadata'].get('compacted') for x in wm.context())


def test_computer_use_policy_blocks_dangerous_and_domains():
    policy = ComputerUsePolicy(['example.com'], max_actions=2)
    assert policy.validate({'action':'navigate','url':'https://example.com'})[0]
    assert not policy.validate({'action':'navigate','url':'https://evil.test'})[0]
    assert not policy.validate({'action':'press','key':'Enter','text':'delete everything'})[0]


def test_real_playwright_observe_and_action(tmp_path):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            if not Path(pw.chromium.executable_path).exists(): pytest.skip('Playwright Chromium binary is not installed in this build environment')
    except Exception:
        pytest.skip('Playwright runtime unavailable')
    runner = PlaywrightComputerUse(str(tmp_path), ComputerUsePolicy(max_actions=5))
    sid = runner.start()
    try:
        obs = runner.observe(sid, 0)
        assert isinstance(obs, BrowserObservation)
        assert Path(obs.screenshot).exists()
        result = runner.act(sid, {'action':'wait','seconds':0})
        assert result['status'] == 'ok'
    finally:
        runner.close_all()


def test_perception_persistence(tmp_path):
    p = PerceptionStore(str(tmp_path / 'perception.db'))
    oid = p.add('browser', 'playwright', {'url':'https://example.com'}, 's1')
    assert oid
    assert p.recent(1)[0]['payload']['url'] == 'https://example.com'
    p.close()


def test_mission_step_metadata_supports_recovery(tmp_path):
    m = MissionStore(str(tmp_path / 'missions.db'))
    mid = m.create('recoverable build')
    m.add_step(mid, 1, 'build', 'chat', {'task':'build','max_attempts':3,'checkpoint':True})
    step = m.next_step(mid)
    assert step['payload']['max_attempts'] == 3
    m.update(mid, 'running', checkpoint={'phase':'step_retry','step':1,'attempt':1})
    assert json.loads(m.get(mid)['checkpoint'])['phase'] == 'step_retry'
    m.close()


def test_computer_use_planner_parses_strict_json(tmp_path):
    class Gateway:
        def chat(self, messages, tools, temp, task='general', require_capabilities=()):
            return {'content': json.dumps({'action':'scroll','dy':500,'dx':0,'rationale':'find more content'})}
    shot = tmp_path / 's.png'; shot.write_bytes(b'not-really-png')
    obs = BrowserObservation('s','about:blank','',str(shot),{'width':100,'height':100},'',[], 'now', 0, {})
    a = ComputerUsePlanner(Gateway()).choose_action(obs, 'find more content')
    assert a['action'] == 'scroll'
