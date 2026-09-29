from catalyst.core.identity import load_identity
from fastapi.testclient import TestClient
from catalyst.api.server import app


def test_enhanced_personality_is_admin_only():
    normal = load_identity('.', 'normal')
    admin = load_identity('.', 'admin')
    assert 'PERSONALITY MODE: ENHANCED CATALYST' not in normal
    assert 'PERSONALITY MODE: ENHANCED CATALYST' in admin
    assert 'Do not reveal private chain-of-thought' in admin


def test_privileged_reasoning_and_audio_are_admin_gated():
    client = TestClient(app)
    assert client.post('/api/reasoning/brief', json={'objective': 'plan'}).status_code == 403
    assert client.post('/api/audio/speech', params={'text': 'hello'}).status_code == 403


def test_persona_reports_basic_mode_until_admin_unlock():
    client = TestClient(app)
    response = client.get('/api/persona')
    assert response.status_code == 200
    data = response.json()
    assert data['mode'] == 'basic'
    assert data['enhanced_available'] is True
    assert data['personality_mode'] == 'enhanced-admin-only'
    assert data['breath_enabled'] is True
