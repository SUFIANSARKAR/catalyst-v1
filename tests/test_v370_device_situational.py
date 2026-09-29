from catalyst.device import DeviceRegistry, DeviceControlPlane
from catalyst.proactive import SituationalStore, SituationalEngine
from catalyst.missions import MissionStore


def test_device_control_claim_complete_and_capability_gate(tmp_path):
    reg=DeviceRegistry(str(tmp_path/'d.db')); did=reg.register('Desk','desktop-tauri','1',['open_url'])
    ctl=DeviceControlPlane(str(tmp_path/'c.db'),reg)
    cmd=ctl.issue(did,'open_url',{'url':'https://example.com'},requires_confirmation=False)
    assert cmd['status']=='pending'
    claimed=ctl.claim(did); assert claimed['status']=='claimed'
    done=ctl.complete(cmd['id'],{'ok':True}); assert done['status']=='completed' and done['result']['ok']
    try: ctl.issue(did,'capture_screen')
    except ValueError as e: assert 'does not advertise' in str(e)
    else: assert False


def test_situational_ingest_dedup_and_priority(tmp_path):
    store=SituationalStore(str(tmp_path/'s.db')); missions=MissionStore(str(tmp_path/'m.db'))
    engine=SituationalEngine(store,missions=missions)
    a=engine.ingest('build_failure','ci','Build failed','Tests failed',.9,{'job':'42'})
    b=engine.ingest('build_failure','ci','Build failed','Tests failed',.9,{'job':'42'})
    assert a['signal_id']==b['signal_id']
    result=engine.scan(); assert result['signals']==0
    assert engine.prioritize(5)==[]
