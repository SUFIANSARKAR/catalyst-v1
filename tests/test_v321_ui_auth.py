from pathlib import Path
from fastapi.testclient import TestClient
from catalyst.api.server import app
from catalyst.identity_auth import ADMIN_PASSWORD_SHA256
import hashlib

def test_creator_bootstrap_password_digest_and_no_plaintext_source():
    raw='5448452043524541544F52'
    assert hashlib.sha256(raw.encode()).hexdigest()==ADMIN_PASSWORD_SHA256
    source=Path('catalyst/identity_auth.py').read_text()
    assert raw not in source

def test_admin_unlock_and_logout():
    c=TestClient(app)
    bad=c.post('/api/auth/admin/unlock',json={'password':'incorrect'})
    assert bad.status_code==401
    good=c.post('/api/auth/admin/unlock',json={'password':'5448452043524541544F52'})
    assert good.status_code==200 and good.json()['admin'] is True
    me=c.get('/api/auth/whoami').json()
    assert me['admin'] is True and me['role']=='creator'
    out=c.post('/api/auth/logout')
    assert out.status_code==200

def test_pwa_routes():
    c=TestClient(app)
    assert c.get('/manifest.json').status_code==200
    assert c.get('/sw.js').status_code==200
    assert c.get('/icon.svg').status_code==200

def test_frontend_has_dual_ui_and_real_auth_buttons():
    html=Path('frontend/index.html').read_text()
    for needle in ['Continue with Google','Creator Admin Access','mobilebar','manifest.json','/api/auth/admin/unlock']:
        assert needle in html
