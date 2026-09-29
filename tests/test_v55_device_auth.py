from catalyst.device import DeviceRegistry, DeviceControlPlane


def test_device_token_auth_and_command_lookup(tmp_path):
    reg = DeviceRegistry(str(tmp_path / 'd.db'))
    did = reg.register('Desk','desktop-tauri','2',['open_url'])
    token = reg.issue_token(did)
    assert reg.authenticate(did, token)
    assert not reg.authenticate(did, 'wrong')
    ctl = DeviceControlPlane(str(tmp_path / 'c.db'), reg)
    cmd = ctl.issue(did, 'open_url', {'url':'https://example.com'}, requires_confirmation=False)
    assert ctl.device_id_for_command(cmd['id']) == did


def test_device_command_claim_is_single_consumer(tmp_path):
    reg = DeviceRegistry(str(tmp_path / 'd.db'))
    did = reg.register('Desk','desktop-tauri','2',['open_url'])
    ctl = DeviceControlPlane(str(tmp_path / 'c.db'), reg)
    cmd = ctl.issue(did, 'open_url', {'url':'https://example.com'}, requires_confirmation=False)
    first = ctl.claim(did)
    second = ctl.claim(did)
    assert first and first['id'] == cmd['id']
    assert first['status'] == 'claimed'
    assert second is None
