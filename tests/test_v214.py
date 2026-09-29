from fastapi.testclient import TestClient

def test_app_session_shape(monkeypatch,tmp_path):
    # import after redirecting settings data paths via env for isolation
    monkeypatch.setenv("CATALYST_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("CATALYST_DATA_DIR", str(tmp_path / "data"))
    from catalyst.api.server import app, sessions
    sid=sessions.create("Test")
    c=TestClient(app)
    r=c.get(f"/api/sessions/{sid}")
    assert r.status_code==200 and r.json()["id"]==sid and "messages" in r.json()
