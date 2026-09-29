from pathlib import Path
from catalyst.omni import EventLedger, HostDeviceExecutor, UnifiedCognition, EngineeringWorkflowPlanner, CognitiveDeliberator
from catalyst.engineering import EngineeringCatalog


def test_event_ledger_and_host_capabilities(tmp_path):
    e=EventLedger(str(tmp_path/'events.db'))
    row=e.emit('test','unit',{'x':1})
    assert row['kind']=='test'
    assert e.recent(1)[0]['payload']=={'x':1}
    h=HostDeviceExecutor(str(tmp_path/'workspace'))
    assert 'get_system_info' in h.capabilities()
    assert h.execute('get_system_info')['ok']
    e.close()


def test_engineering_workflow_plan(tmp_path):
    e=EventLedger(str(tmp_path/'events.db'))
    p=EngineeringWorkflowPlanner(EngineeringCatalog,e).plan('CFD thermal geometry simulation')
    assert p['steps']
    assert any(x['kind']=='physics_ai' for x in p['steps'])
    e.close()
