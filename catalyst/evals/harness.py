import json,time
from pathlib import Path

class EvaluationHarness:
    """Deterministic smoke/evaluation harness for Catalyst releases."""
    def __init__(self, root='catalyst_data/evals'):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def run(self, tests, runner):
        out=[]
        for t in tests:
            started=time.perf_counter()
            try:
                value=runner(t); status='passed'; error=None
            except Exception as exc:
                value=None; status='failed'; error=str(exc)
            out.append({'id':t.get('id'), 'status':status, 'duration_ms':round((time.perf_counter()-started)*1000,3), 'result':value, 'error':error})
        report={'passed':sum(x['status']=='passed' for x in out),'failed':sum(x['status']=='failed' for x in out),'tests':out}
        path=self.root/f'eval-{int(time.time())}.json';path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');report['artifact']=str(path);return report
