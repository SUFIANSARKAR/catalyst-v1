from pathlib import Path


def test_v56_release_surfaces_are_present():
    assert Path('catalyst/version.py').read_text().strip().startswith("__version__='5.7.0'")
    api = Path('catalyst/api/server.py').read_text()
    ui = Path('frontend/index.html').read_text()
    assert "'/api/cognition/pulse'" in api
    assert "def chat(req:ChatRequest, request:Request)" in api
    assert '/api/reasoning/brief' in ui
    assert '/api/apex/missions/' in ui
    assert 'modelgrid' in ui
    assert 'holo-ring' in ui


def test_provider_options_are_filtered_and_merged():
    source = Path('catalyst/providers/openai_compatible.py').read_text()
    assert 'reasoning_effort' in source
    assert 'request_options=self.options.get("chat", self.options)' in source
    assert '"messages"' not in source.split('request_options=', 1)[1].split('if tools:', 1)[0]
