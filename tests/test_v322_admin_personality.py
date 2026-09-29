from pathlib import Path
from catalyst.core.identity import load_identity

def test_normal_and_admin_identity_modes_are_distinct():
    normal=load_identity('.', 'normal')
    admin=load_identity('.', 'admin')
    assert 'ACCESS MODE: NORMAL USER' in normal
    assert 'ACCESS MODE: CREATOR / ADMIN' in admin
    assert 'Creator Sir' not in normal.split('ACCESS MODE: NORMAL USER',1)[1].split('Operating constitution:',1)[0]
    assert 'Creator Sir' in admin
    assert 'girlfriend/boyfriend/companion' in admin

def test_frontend_exposes_admin_state():
    html=Path('frontend/index.html').read_text()
    assert 'Creator · Admin' in html
    assert 'Unlock Creator Admin' in html or 'Unlock full Catalyst' in html
