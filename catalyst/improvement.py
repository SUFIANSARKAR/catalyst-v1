from datetime import datetime,timezone
from pathlib import Path
import json, subprocess, time

class ImprovementManager:
    """Benchmark-driven improvement records. Promotion is explicit and never automatic here."""
    def __init__(self,root): self.root=Path(root)/'proposals'; self.root.mkdir(parents=True,exist_ok=True)
    def propose(self,change,reason='',test_plan='',benchmark=None):
        now=datetime.now(timezone.utc); slug=f"{int(time.time())}-{int(now.microsecond/1000):03d}"; p=self.root/f'{slug}.json'
        payload={'status':'proposed','created':now.isoformat(),'change':change,'reason':reason,'test_plan':test_plan,'benchmark':benchmark or {},'promotion_rule':'pass tests + benchmark + human approval where required'}
        p.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8'); return str(p)
    def run_command_benchmark(self, command, cwd='.', timeout=900):
        started=time.perf_counter()
        try:
            cp=subprocess.run(command,shell=True,cwd=cwd,text=True,capture_output=True,timeout=timeout)
            result={'status':'passed' if cp.returncode==0 else 'failed','returncode':cp.returncode,'duration_seconds':round(time.perf_counter()-started,4),'stdout':cp.stdout[-50000:],'stderr':cp.stderr[-20000:]}
        except subprocess.TimeoutExpired as e:
            result={'status':'timeout','returncode':None,'duration_seconds':round(time.perf_counter()-started,4),'stdout':(e.stdout or '')[-50000:],'stderr':(e.stderr or '')[-20000:]}
        return result
    def evaluate(self, proposal_path, baseline, candidate):
        proposal=Path(proposal_path); data=json.loads(proposal.read_text(encoding='utf-8')); data['evaluation']={'baseline':baseline,'candidate':candidate,'evaluated':datetime.now(timezone.utc).isoformat()}
        data['status']='candidate_passed' if candidate.get('status')=='passed' else 'candidate_failed'; proposal.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8'); return data
