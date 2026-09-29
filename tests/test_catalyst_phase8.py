from __future__ import annotations

import json
import struct
from pathlib import Path

from catalyst.avatar import APPEARANCES, EMOTIONS, ACTIONS, AvatarController, avatar_runtime_info
from catalyst.ui_preferences import UIPreferences


def _read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data, 0)
    assert magic == b'glTF' and version == 2 and length == len(data)
    offset = 12
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from('<II', data, offset)
        chunk = data[offset + 8: offset + 8 + chunk_length]
        offset += 8 + chunk_length
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.rstrip(b' \t\r\n\x00').decode('utf-8'))
    raise AssertionError('GLB JSON chunk missing')


def test_phase8_avatar_profiles_and_runtime(tmp_path):
    assert set(APPEARANCES) == {'signature', 'lounge', 'focus', 'night'}
    assert {'neutral', 'happy', 'focused', 'curious'}.issubset(EMOTIONS)
    assert {'idle', 'listen', 'think', 'speak', 'gesture'}.issubset(ACTIONS)

    controller = AvatarController()
    value = controller.set('speaking', emotion='warm')
    assert value['action'] == 'speak'
    assert value['emotion'] == 'warm'
    assert controller.set_motion('reduced')['motion'] == 'reduced'
    assert controller.set_appearance('night')['appearance'] == 'night'


def test_phase8_preferences_are_allowlisted_and_atomic(tmp_path):
    store = UIPreferences(tmp_path / 'prefs.json')
    baseline = store.get()
    assert baseline['theme'] == 'dark'
    updated = store.update({'theme': 'warm', 'voice_auto': True, 'unknown_secret': 'should-not-persist'})
    assert updated['theme'] == 'warm'
    assert updated['voice_auto'] is True
    assert 'unknown_secret' not in updated
    loaded = UIPreferences(tmp_path / 'prefs.json').get()
    assert loaded == updated


def test_phase8_vrm_is_real_glb_humanoid_asset():
    path = Path('frontend/assets/catalyst/catalyst.vrm')
    assert path.is_file() and path.stat().st_size > 100_000
    gltf = _read_glb_json(path)
    assert 'VRMC_vrm' in gltf.get('extensionsUsed', [])
    assert 'VRMC_springBone' in gltf.get('extensionsUsed', [])
    vrm = gltf['extensions']['VRMC_vrm']
    assert vrm['specVersion'] == '1.0'
    assert vrm['meta']['name'] == 'Catalyst'
    assert vrm['humanoid']['humanBones']['head']['node'] == 5
    assert len(gltf.get('nodes', [])) >= 80
    assert len(gltf.get('meshes', [])) >= 50
    catalyst_extra = gltf.get('extras', {}).get('catalyst', {})
    assert catalyst_extra.get('humanoidBoneCount') == 23
    assert catalyst_extra.get('springBone') is True


def test_phase8_runtime_info_exposes_body_contract(tmp_path):
    frontend = tmp_path / 'frontend'
    model = frontend / 'assets' / 'catalyst'
    model.mkdir(parents=True)
    (model / 'catalyst.vrm').write_bytes(b'x' * 100001)
    info = avatar_runtime_info(frontend)
    assert info['model']['installed'] is True
    assert info['model']['path'].endswith('/assets/catalyst/catalyst.vrm')
    assert info['rig']['humanoid_bones'] == 23
    assert info['rig']['spring_bone'] is True


def test_phase8_realtime_voice_socket_allows_voice_capability():
    from fastapi.testclient import TestClient
    from catalyst.api.server import app

    with TestClient(app) as client:
        created = client.post('/api/audio/realtime/session?codec=audio/webm&sample_rate=16000')
        assert created.status_code == 200
        sid = created.json()['id']
        with client.websocket_connect(f'/api/audio/realtime/ws/{sid}') as ws:
            connected = ws.receive_json()
            assert connected['status'] == 'connected'
            ws.send_json({'action': 'stats'})
            assert ws.receive_json()['status'] == 'stats'
            ws.send_json({'action': 'close'})
            assert ws.receive_json()['status'] == 'closed'
