from ..artifacts import ArtifactStore
import csv,json,html,hashlib
from pathlib import Path
from datetime import datetime,timezone

class AnalysisArtifactBuilder:
    def __init__(self, root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def write_report(self, report, name='analysis-report'):
        ts=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        json_path=self.root/f'{name}-{ts}.json'; html_path=self.root/f'{name}-{ts}.html'
        json_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        body='<h1>Catalyst Analysis Report</h1><pre>'+html.escape(json.dumps(report,indent=2,ensure_ascii=False))+'</pre>'
        html_path.write_text('<!doctype html><html><meta charset="utf-8"><title>Catalyst Analysis</title><body>'+body+'</body></html>',encoding='utf-8')
        return [self._meta(json_path,'application/json'),self._meta(html_path,'text/html')]
    def _meta(self,p,kind):
        b=p.read_bytes();return {'name':p.name,'path':str(p),'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'type':kind}
