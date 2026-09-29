from catalyst.device import DeviceRegistry, ShellBridge
from catalyst.proactive import SituationalStore, SituationalEngine
from catalyst.missions import MissionStore
from catalyst.automation import AutomationStore


def test_device_registry_and_commands(tmp_path):
    reg=DeviceRegistry(str(tmp_path/'d.db'))
    did=reg.register('Test Desktop','desktop-tauri','1', ['open_url','show_notification'], {'os':'test'})
    assert reg.get(did)['platform']=='desktop-tauri'
    bridge=ShellBridge(reg)
    assert bridge.can(did,'open_url')
    cmd=bridge.command(did,'open_url',{'url':'https://example.com'},True)
    assert cmd['protocol']=='catalyst.device.v1' and cmd['requires_confirmation'] is True


def test_proactive_engine_records_failures_without_execution(tmp_path):
    store=SituationalStore(str(tmp_path/'s.db'))
    missions=MissionStore(str(tmp_path/'m.db'))
    mid=missions.create('Investigate failed build')
    missions.update(mid,'failed',error='test failure')
    auto=AutomationStore(str(tmp_path/'a.db'))
    engine=SituationalEngine(store, missions=missions, automations=auto)
    result=engine.scan()
    assert result['signals'] >= 1
    suggestions=store.list_suggestions('pending')
    assert suggestions
    assert all(x['status']=='pending' for x in suggestions)
