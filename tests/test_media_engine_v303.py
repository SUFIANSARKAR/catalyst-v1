from pathlib import Path
from catalyst.media.engine import MediaEngine, MediaJobError
from catalyst.config import ProviderProfile


class S:
    def load_profiles(self):
        return {
            'img': ProviderProfile('img', 'https://example.test/v1', 'image-model', 'secret', 'openrouter_image', ('image_generation',), 'media', {'image_request': {'style': 'cinematic'}}),
            'vid': ProviderProfile('vid', 'https://example.test/v1', 'video-model', 'secret', 'openrouter_video', ('video_generation',), 'media', {}),
        }


class A:
    def __init__(self, root): self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def write_bytes(self, name, data, media_type='application/octet-stream'):
        p = self.root / name; p.write_bytes(data); return {'name': p.name, 'type': media_type}


class X:
    def resolve(self, aid): raise FileNotFoundError


def test_media_profiles_advertise_modes(tmp_path):
    m = MediaEngine(S(), A(tmp_path), X())
    profiles = {x['name']: x for x in m.provider_profiles()}
    assert profiles['img']['supports_image'] is True
    assert profiles['vid']['supports_video'] is True
    assert profiles['img']['supports_video'] is False


def test_media_profile_accepts_capability_alias(tmp_path):
    class S2:
        def load_profiles(self):
            return {'img': ProviderProfile('img', 'https://x', 'm', 'k', 'openai_compatible', ('image',), 'media')}
    m = MediaEngine(S2(), A(tmp_path), X())
    assert m._profile('img', 'image').name == 'img'


def test_reference_limit(tmp_path):
    m = MediaEngine(S(), A(tmp_path), X())
    try:
        m._reference_payload(['1', '2', '3'], mode='Video', max_refs=2)
    except MediaJobError as exc:
        assert 'at most 2' in str(exc)
    else:
        raise AssertionError('expected reference limit')


def test_image_profile_can_use_generation_capability(tmp_path):
    class S2:
        def load_profiles(self):
            return {'img': ProviderProfile('img', 'https://x', 'm', 'k', 'openai_compatible', ('image_generation',), 'media')}
    m = MediaEngine(S2(), A(tmp_path), X())
    assert m._profile('img', 'image').model == 'm'
