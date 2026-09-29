from pathlib import Path
from catalyst.media.engine import MediaEngine, MediaJobError

class S:
    sandbox_timeout=5
    def load_profiles(self): return {}

class A:
    def __init__(self, root): self.root=Path(root)
    def write_bytes(self,name,data,media_type='application/octet-stream'):
        p=self.root/name; p.write_bytes(data); return {'name':p.name,'type':media_type}
    def _meta(self,path,kind): return {'name':path.name,'type':kind}

class X:
    def resolve(self, aid): raise FileNotFoundError


def test_media_profile_empty():
    m=MediaEngine(S(),A('catalyst_data/test_media'),X())
    assert m.provider_profiles()==[]
    try: m._profile(None,'image')
    except MediaJobError as exc: assert 'No configured image' in str(exc)
    else: raise AssertionError('expected missing provider error')
