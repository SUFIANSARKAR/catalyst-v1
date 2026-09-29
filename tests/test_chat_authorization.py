from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from catalyst.api import server


@pytest.mark.parametrize('path', ['/api/chat', '/api/chat/stream'])
@pytest.mark.parametrize('admin', [False, True], ids=['normal-user', 'creator-admin'])
def test_chat_endpoints_share_normal_and_admin_access_modes(monkeypatch, path, admin):
    monkeypatch.setattr(server.settings, 'api_token', '')
    monkeypatch.setattr(server.settings, 'api_tokens', {'phase1-normal-token': 'guest'})
    monkeypatch.setitem(server.identity.tokens, 'phase1-normal-token', 'guest')
    monkeypatch.setattr(server.settings, 'admin_password_sha256', sha256(b'phase1-admin').hexdigest())
    monkeypatch.setattr(server.sessions, 'ensure', lambda session_id=None: 'phase1-session')

    access_modes = []

    def respond(message, **kwargs):
        access_modes.append(kwargs['access_mode'])
        return SimpleNamespace(answer='normal response', steps=1, tools_used=[], verified=True, stopped_reason=None)

    def stream_response(message, **kwargs):
        access_modes.append(kwargs['access_mode'])
        yield {'type': 'done', 'answer': 'streamed response'}

    monkeypatch.setattr(server.catalyst, 'respond', respond)
    monkeypatch.setattr(server.catalyst, 'stream_response', stream_response)

    headers = {'Authorization': 'Bearer phase1-normal-token'}
    if admin:
        admin_token = server.identity.unlock_admin('phase1-admin')
        assert admin_token
        headers = {'Authorization': f'Bearer {admin_token}'}

    response = TestClient(server.app).post(path, json={'message': 'hello'}, headers=headers)

    assert response.status_code == 200
    assert access_modes == ['admin' if admin else 'normal']
    if path.endswith('/stream'):
        assert 'streamed response' in response.text
    else:
        assert response.json()['answer'] == 'normal response'