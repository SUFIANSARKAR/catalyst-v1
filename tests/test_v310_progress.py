import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from catalyst import __version__
from catalyst.config import ProviderProfile, Settings
from catalyst.memory import MemoryStore
from catalyst.missions import MissionStore


def test_v310_version():
    assert tuple(map(int, __version__.split('.'))) >= (3, 14, 0)


def test_memory_dedup_and_consolidation(tmp_path):
    m=MemoryStore(str(tmp_path/'memory.db'))
    a=m.add('Catalyst will verify before claiming success.', 'decision', importance=0.7)
    b=m.add('  Catalyst   will verify before claiming success.  ', 'note', importance=0.9)
    assert a == b
    assert m.get(a)['importance'] == 0.9
    stats=m.consolidate()
    assert stats['archived'] == 0
    assert m.search('verify claiming success', 5)[0]['id'] == a
    m.close()


def test_memory_archive(tmp_path):
    m=MemoryStore(str(tmp_path/'memory.db'))
    mid=m.add('temporary context', importance=0.2)
    assert m.archive(mid)['archived'] is True
    assert m.search('temporary context', 5) == []
    m.close()


def test_mission_pause_cancel_resume(tmp_path):
    ms=MissionStore(tmp_path/'missions.db')
    mid=ms.create('build a tool')
    assert ms.pause(mid)['status']=='paused'
    assert ms.resume(mid)['status']=='queued'
    assert ms.cancel(mid)['status']=='cancelled'
    ms.close()


def test_provider_options_roundtrip(tmp_path):
    s=Settings(data_root=str(tmp_path/'data'), workspace_root=str(tmp_path/'workspace'), secrets_path=str(tmp_path/'secrets.json'))
    profile=ProviderProfile('media','https://example.invalid/v1','m','k',capabilities=('image','video'),options={'image_request':{'size':'1536x1024'}})
    s.save_profile(profile)
    loaded=s.load_profiles()['media']
    assert loaded.options['image_request']['size']=='1536x1024'
