import tempfile
from pathlib import Path
from catalyst.approvals import ApprovalStore
from catalyst.core.models import TaskResult
from catalyst.agent_protocol import normalize_result

def test_approval_resume_state_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        s=ApprovalStore(str(Path(d)/"a.db")); aid=s.create("session","write it","write_file",{"path":"x","content":"ok"}); row=s.resolve(aid,True,{"status":"ok","result":"done"}); assert row["status"]=="approved" and row["result"]; s.close()

def test_agent_contract_normalization():
    x=normalize_result({"summary":"done","tests":[{"name":"t","status":"passed"}]},"tc","1"); assert x["protocol"]=="catalyst.agent.v1" and x["summary"]=="done"
