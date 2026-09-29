from pathlib import Path
from catalyst.core.identity import load_identity
from catalyst.persona import load_persona
from catalyst.api.server import app
from fastapi.testclient import TestClient


def test_female_persona_is_part_of_identity():
    text = load_identity('.', 'normal')
    assert 'female' in text.lower()
    assert 'natural, expressive' in text


def test_persona_endpoint():
    r = TestClient(app).get('/api/persona')
    assert r.status_code == 200
    data = r.json()
    assert data['presentation'] == 'female'
    assert data['voice_preset'] == load_persona().voice_preset


def test_premium_persona_ui_is_present():
    html = Path('frontend/index.html').read_text()
    for needle in ['Female AI', 'persona-orb', 'Persona & voice', 'Natural · expressive · conversational']:
        assert needle in html
