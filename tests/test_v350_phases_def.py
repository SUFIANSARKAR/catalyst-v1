from catalyst.realtime import RealtimeVoiceStore
from catalyst.research_evidence import EvidenceResearchEngine
from catalyst.improvement_lab import ImprovementLab

class FakeResearch:
    def research(self,q,limit=5):
        return {'sources':[
            {'title':'A','url':'https://a.example','content':'The system supports higher throughput before migration.'},
            {'title':'B','url':'https://b.example','content':'The system has lower throughput after migration.'}
        ]}

def test_realtime_voice_session_buffers_and_closes(tmp_path):
    s=RealtimeVoiceStore(str(tmp_path/'rt'))
    row=s.create(codec='audio/pcm',sample_rate=48000)
    rid=row['id']; s.append(rid,b'abc'); s.append(rid,b'def')
    assert s.get(rid)['bytes_received']==6
    assert s.audio_path(rid).read_bytes()==b'abcdef'
    assert s.close(rid,'finalized')['status']=='finalized'
    s.shutdown()

def test_evidence_engine_captures_claims_and_conflict_signals(tmp_path):
    e=EvidenceResearchEngine(FakeResearch(),str(tmp_path/'e'))
    out=e.research('system throughput migration',2)
    assert len(out['sources'])==2 and out['claims']
    assert out['contradictions']

def test_improvement_lab_requires_pass_before_promotion(tmp_path):
    root=tmp_path/'repo'; root.mkdir(); (root/'a.txt').write_text('old\n')
    lab=ImprovementLab(root,str(tmp_path/'lab'))
    patch='''diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-old
+new
'''
    import subprocess
    subprocess.run(['git','init','-q'],cwd=root,check=True)
    subprocess.run(['git','add','a.txt'],cwd=root,check=True)
    subprocess.run(['git','-c','user.name=T','-c','user.email=t@example.com','commit','-qm','base'],cwd=root,check=True)
    candidate="python -c \"from pathlib import Path; assert Path('a.txt').read_text().strip()=='new'\""
    baseline="python -c \"from pathlib import Path; assert Path('a.txt').read_text().strip()=='old'\""
    m=lab.create('change',patch,candidate,baseline_command=baseline)
    r=lab.run(m['id'])
    assert r['status']=='passed'
    promoted=lab.promote(m['id'])
    assert promoted['status']=='promoted'
    assert (root/'a.txt').read_text().strip()=='new'
