from catalyst.adaptive import AdaptiveMissionController
from catalyst.missions import MissionStore
from catalyst.jobs.store import JobStore


def test_failed_step_gets_bounded_recovery(tmp_path):
    m=MissionStore(str(tmp_path/'m.db')); j=JobStore(str(tmp_path/'j.db'))
    mid=m.create('Build and test project'); m.update(mid,'running',plan={'objective':'Build and test project'})
    sid=m.add_step(mid,1,'Build','chat',{'kind':'chat','task':'build project','max_attempts':2})
    m.update_step(sid,'failed',error='dependency resolution failed'); m.update(mid,'failed',error='step failure')
    c=AdaptiveMissionController(str(tmp_path/'a.db'),m,j)
    out=c.supervise_once()
    assert out and out[0]['status']=='recovered'
    step=m.steps(mid)[0]
    assert step['status']=='queued'
    assert 'previous_failure' in step['payload']
    assert len(j.list())==1


def test_stalled_mission_requeues_once(tmp_path):
    m=MissionStore(str(tmp_path/'m.db')); j=JobStore(str(tmp_path/'j.db'))
    mid=m.create('Continue long mission'); m.update(mid,'running',plan={'objective':'Continue long mission'},checkpoint={'phase':'waiting'})
    c=AdaptiveMissionController(str(tmp_path/'a.db'),m,j,stall_seconds=60)
    # Make it old without relying on sleep.
    m.db.execute("UPDATE missions SET updated_at='2020-01-01T00:00:00+00:00' WHERE id=?",(mid,)); m.db.commit()
    out=c.supervise_once()
    assert out and out[0]['status']=='recovered_stall'
    assert len(j.list())==1
    out2=c.supervise_once()
    assert len(j.list())==1
