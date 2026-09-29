import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from catalyst import __version__
from catalyst.capabilities import manifest
from catalyst.config import ProviderProfile, Settings
from catalyst.core.orchestrator import Catalyst
from catalyst.providers.gateway import ModelGateway


def test_release_version_is_single_source_of_truth():
    assert tuple(map(int, __version__.split('.'))) >= (3, 14, 0)


def test_gateway_honors_required_capabilities(monkeypatch, tmp_path):
    s = Settings(data_root=str(tmp_path / 'data'), workspace_root=str(tmp_path / 'workspace'))
    s.save_profile(ProviderProfile('plain', 'https://example.invalid/v1', 'plain-model', 'key', capabilities=('chat',)))
    s.save_profile(ProviderProfile('vision', 'https://example.invalid/v1', 'vision-model', 'key', capabilities=('chat', 'vision')))
    gateway = ModelGateway(s)

    class FakeProvider:
        def __init__(self, name):
            self.name = name
        def chat(self, *args, **kwargs):
            return {'content': self.name}
        def stream(self, *args, **kwargs):
            yield {'content': self.name}

    gateway._providers['plain'] = FakeProvider('plain')
    gateway._providers['vision'] = FakeProvider('vision')
    gateway.active_name = 'plain'

    assert gateway.chat([{'role': 'user', 'content': 'x'}], require_capabilities=('vision',))['content'] == 'vision'


def test_messages_use_context_manager_when_session_is_present(tmp_path):
    from catalyst.sessions import SessionStore
    sessions = SessionStore(tmp_path / 'sessions')
    sid = sessions.create('Test')

    class DummyContext:
        def build_messages(self, session_id, current_user_text, system_message):
            return [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': current_user_text}]

    c = Catalyst(provider=object(), memory=object(), tools=object(), settings=object(), sessions=sessions)
    c._system = lambda q: ('S', type('P', (), {'strategy':'x'})())
    c.context_manager = DummyContext()
    messages, _ = c._messages('hello', session_id=sid)
    assert messages[-1] == {'role': 'user', 'content': 'hello'}
    sessions.close()


def test_capability_manifest_reports_runtime_release(tmp_path):
    class DummyGateway:
        active_profile = None
    class DummyTools:
        def list(self): return []
    class DummyAgents:
        def describe(self): return []
    class DummyPlugins:
        def list(self): return []
    class DummyMedia:
        def provider_profiles(self): return []
    class DummyWorker:
        thread = None
    class DummyPolicy:
        def describe(self): return {}

    s = Settings(data_root=str(tmp_path / 'data'), workspace_root=str(tmp_path / 'workspace'))
    out = manifest(s, DummyGateway(), DummyTools(), DummyAgents(), DummyPlugins(), DummyMedia(), DummyWorker(), DummyPolicy())
    assert out['version'] == __version__
