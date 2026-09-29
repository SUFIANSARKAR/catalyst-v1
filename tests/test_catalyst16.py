from catalyst.jobs import JobStore
from catalyst.provenance import ProvenanceStore

def test_job_checkpoint(tmp_path):
    db=tmp_path/"jobs.db"; j=JobStore(str(db)); jid=j.create("analysis", {"x":1}); j.start(jid); j.checkpoint(jid,{"step":2}); payload, cp=j.resume_payload(jid); assert payload=={"x":1}; assert cp=={"step":2}; j.close()

def test_provenance(tmp_path):
    p=ProvenanceStore(str(tmp_path/"p.db")); eid=p.add("web","https://example.test","claim",{"ok":True}); rows=p.list(); assert rows[0]["id"]==eid; p.close()
