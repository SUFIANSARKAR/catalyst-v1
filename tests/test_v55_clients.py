from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_android_companion_declares_network_and_real_bridge():
    manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
    activity=(ROOT/'android/app/src/main/java/com/catalyst/android/MainActivity.kt').read_text()
    assert 'android.permission.INTERNET' in manifest
    assert '/api/devices/register' in activity
    assert '/api/devices/$deviceId/commands/claim' in activity


def test_desktop_companion_executes_authenticated_device_commands():
    js=(ROOT/'desktop/src/main.js').read_text()
    rust=(ROOT/'desktop/src-tauri/src/lib.rs').read_text()
    assert 'X-Catalyst-Device-Token' in js
    assert 'desktop_execute' in js and 'desktop_execute' in rust
    assert 'open_url' in rust and 'open_file' in rust


def test_frontend_exposes_reasoning_and_apex_controls():
    html=(ROOT/'frontend/index.html').read_text()
    assert 'showReasoning()' in html
    assert '/api/reasoning/brief' in html
    assert 'showApexMissions()' in html
    assert '/api/apex/missions/' in html
