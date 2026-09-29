import tempfile, time
from pathlib import Path
from catalyst.config import Settings
from catalyst.jobs.store import JobStore
from catalyst.automation import AutomationStore

def test_job_atomic_claim_and_retry():
    with tempfile.TemporaryDirectory() as d:
        js=JobStore(str(Path(d)/'jobs.db'))
        jid=js.create('general', {'x':1}, max_attempts=2)
        a=js.claim_next('a'); b=js.claim_next('b')
        assert a['id']==jid and b is None
        assert js.fail_or_retry(jid,'boom',backoff_seconds=1)=='queued'
        row=js.get(jid); assert row['status']=='queued' and row['attempts']==1
        js.close()

def test_automation_claim_is_atomic():
    with tempfile.TemporaryDirectory() as d:
        a=AutomationStore(str(Path(d)/'automation.db'))
        aid=a.create('demo','do something',1)
        # move next_run into the past for an immediate claim
        a.db.execute("UPDATE automations SET next_run=? WHERE id=?", ('2000-01-01T00:00:00+00:00',aid)); a.db.commit()
        one=a.claim_due(1); two=a.claim_due(1)
        assert len(one)==1 and two==[]
        a.mark_dispatched(aid,60)
        a.close()

def test_settings_has_opt_in_auth_and_localhost_cors():
    s=Settings()
    assert hasattr(s,'api_token') and hasattr(s,'cors_origins')
