from pathlib import Path
from catalyst.embeddings import EmbeddingIndex
from catalyst.execution import SandboxRunner
from catalyst.policy import policy_for
from catalyst.improvement import ImprovementManager

def test_embedding_index(tmp_path):
    idx=EmbeddingIndex(str(tmp_path/'e.db')); idx.upsert('project','a#0','alpha',[1,0]); idx.upsert('project','b#0','beta',[0.8,0.2]); out=idx.search('project',[1,0],1); assert out[0]['ref']=='a#0'; idx.close()

def test_policy_defaults():
    assert policy_for('developer').allow_write is True
    assert policy_for('creator').allow_write is False

def test_improvement_proposal_and_benchmark(tmp_path):
    m=ImprovementManager(tmp_path); p=m.propose('change x','reason','pytest'); assert Path(p).exists(); r=m.run_command_benchmark('python -c "print(1)"',cwd=str(tmp_path)); assert r['status']=='passed'

def test_sandbox_local(tmp_path):
    ws=tmp_path/'ws'; ws.mkdir(); s=SandboxRunner(str(ws),str(tmp_path/'data'),'local',timeout=10); r=s.run('python -c "print(42)"'); assert r.status=='completed' and '42' in r.stdout
