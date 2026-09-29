from pathlib import Path
from catalyst.engineering.codebase import CodebaseIntelligence
from catalyst.engineering.agent import EngineeringAgent
from catalyst.monster import CatalystMonster, MonsterConfig
from catalyst.providers.local import LocalModelProvider, LocalModelConfig
from catalyst.benchmarks.engineering import EngineeringBenchmark


def test_codebase_intelligence(tmp_path):
    (tmp_path/'app.py').write_text('class App:\n    def run(self):\n        return 1\n')
    (tmp_path/'test_app.py').write_text('def test_run():\n    assert True\n')
    m=CodebaseIntelligence(str(tmp_path)).repo_map()
    assert m['files'] == 2 and m['tests'] == 1
    assert any(s['name']=='App' for s in m['symbols'])


def test_engineering_agent_is_governed(tmp_path):
    (tmp_path/'main.py').write_text('print(1)\n')
    agent=EngineeringAgent(str(tmp_path))
    run=agent.run('fix main.py', execute=True, approval=False)
    assert run.status == 'awaiting_approval'


def test_monster_status_without_local_model(tmp_path):
    monster=CatalystMonster(str(tmp_path), config=MonsterConfig(local_model=''))
    status=monster.status()
    assert status['protocol']=='catalyst.monster.v4'
    assert status['local']['configured'] is False


def test_local_provider_configuration():
    p=LocalModelProvider(LocalModelConfig(model='qwen-local'))
    assert p.configured


def test_engineering_benchmark():
    b=EngineeringBenchmark()
    out=b.run(lambda c: {'repo_map':True,'tests':True,'steps':True,'verification':True,'failure':True,'replan':True,'evidence':True})
    assert out['score']==1.0
