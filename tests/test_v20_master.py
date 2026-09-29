from pathlib import Path
from catalyst.observability import ObservabilityStore
from catalyst.missions import MissionStore
from catalyst.config import ProviderProfile
from catalyst.providers.gateway import ModelGateway
from catalyst.config import Settings
import tempfile, json

def test_observability_roundtrip(tmp_path):
    o=ObservabilityStore(str(tmp_path/'obs.db')); s=o.start_span('x',metadata={'a':1}); o.end_span(s); o.incr('x'); assert o.summary()['counters'][0]['value']==1.0; o.close()

def test_mission_steps(tmp_path):
    m=MissionStore(str(tmp_path/'m.db')); mid=m.create('build'); sid=m.add_step(mid,1,'one','chat',{'task':'x'}); assert m.next_step(mid)['id']==sid; m.update_step(sid,'completed',{'ok':1}); assert m.next_step(mid) is None; m.close()

def test_provider_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('CATALYST_SECRETS_PATH', str(tmp_path/'s.json'))
    monkeypatch.setenv('CATALYST_MODEL','')
    monkeypatch.setenv('CATALYST_API_KEY','')
    s=Settings(); p=ProviderProfile('x','https://example.test/v1','m','k','openai_compatible',('vision','reasoning'),'general'); s.save_profile(p); d=s.load_profiles()['x']; assert d.capabilities==('vision','reasoning'); assert d.role=='general'
