import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from catalyst.config import Settings, ProviderProfile
from catalyst.security import PolicyEngine, Principal
from catalyst.identity_auth import IdentityAuthority
from catalyst.memory import MemoryStore
from catalyst.memory.semantic import SemanticMemoryBridge
from catalyst.long_horizon import LongHorizonEvaluator


def test_identity_scoped_roles(tmp_path, monkeypatch):
    monkeypatch.setenv('CATALYST_API_TOKENS','{"creator-token":"creator","research-token":"researcher"}')
    s=Settings(data_root=str(tmp_path/'data'), workspace_root=str(tmp_path/'workspace'), secrets_path=str(tmp_path/'secrets.json'))
    auth=IdentityAuthority(s,PolicyEngine())
    assert auth.authenticate('creator-token','me').principal.role=='creator'
    assert auth.authenticate('research-token','webbot').principal.role=='researcher'
    assert not auth.authenticate('wrong').authenticated


def test_policy_capability_boundary():
    p=PolicyEngine()
    assert p.allowed(Principal('x','researcher'),'research')
    assert not p.allowed(Principal('x','researcher'),'write')


def test_semantic_memory_without_embedding_provider_falls_back_cleanly(tmp_path):
    s=Settings(data_root=str(tmp_path/'data'), workspace_root=str(tmp_path/'workspace'), secrets_path=str(tmp_path/'secrets.json'))
    m=MemoryStore(str(tmp_path/'memory.db'))
    mid=m.add('Catalyst should remember architecture decisions.', 'decision', importance=0.9)
    from catalyst.providers.gateway import ModelGateway
    gw=ModelGateway(s)
    bridge=SemanticMemoryBridge(m,gw,s)
    assert bridge.search('architecture decision')==[]
    assert bridge.upsert_memory(mid)['status']=='skipped'
    assert m.recent_active(10)[0]['id']==mid
    bridge.close(); m.close()


def test_long_horizon_persists_multi_step_run(tmp_path):
    e=LongHorizonEvaluator(str(tmp_path/'long.db'))
    scenario={'name':'resumability smoke','steps':[{'id':'a','action':'echo','value':{'ok':1},'expect':{'ok':1}}, {'id':'b','action':'echo','value':{'ok':2},'expect':{'ok':2}}]}
    report=e.run(scenario,lambda step,seq,previous: step.get('value'),max_steps=10)
    assert report['status']=='passed'
    assert report['passed']==2 and report['completed'] is True
    assert e.recent(1)[0]['status']=='passed'
    e.close()
