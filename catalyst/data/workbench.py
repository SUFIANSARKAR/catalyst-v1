from ..analysis.artifacts import AnalysisArtifactBuilder
import csv, json, statistics
from pathlib import Path

class AnalysisWorkbench:
    def __init__(self, workspace_root, data_root):
        self.workspace=Path(workspace_root).resolve(); self.root=Path(data_root).resolve()/"artifacts"; self.root.mkdir(parents=True,exist_ok=True); self.builder=AnalysisArtifactBuilder(self.root)
    def _safe(self, rel):
        p=(self.workspace/rel).resolve()
        if p!=self.workspace and self.workspace not in p.parents: raise PermissionError('Path escapes workspace')
        if not p.is_file(): raise FileNotFoundError(rel)
        return p
    def analyze_many(self, paths, max_rows=2000):
        report={'files':[],'totals':{'files':0,'bytes':0},'warnings':[]}
        for rel in paths[:100]:
            p=self._safe(rel); info={'path':rel,'bytes':p.stat().st_size,'suffix':p.suffix.lower()}
            try:
                if p.suffix.lower()=='.csv':
                    with p.open('r',encoding='utf-8-sig',newline='') as f:
                        reader=csv.DictReader(f); rows=[]
                        for i,row in enumerate(reader):
                            if i>=max_rows: break
                            rows.append(row)
                        nums={}
                        for k in reader.fieldnames or []:
                            vals=[]
                            for r in rows:
                                try: vals.append(float(r.get(k,'')))
                                except (TypeError,ValueError): pass
                            if vals: nums[k]={'count':len(vals),'mean':statistics.fmean(vals),'min':min(vals),'max':max(vals)}
                        info.update({'type':'csv','columns':reader.fieldnames or [],'sampled_rows':len(rows),'numeric':nums})
                elif p.suffix.lower() in {'.json','.jsonl','.ndjson'}:
                    text=p.read_text(encoding='utf-8',errors='replace')[:10_000_000]
                    if p.suffix.lower()=='.json': obj=json.loads(text); info.update({'type':'json','shape':type(obj).__name__,'keys':list(obj)[:50] if isinstance(obj,dict) else None})
                    else: info.update({'type':'jsonl','sampled_records':len([x for x in text.splitlines() if x.strip()][:max_rows])})
                else:
                    text=p.read_text(encoding='utf-8',errors='replace')[:10_000_000]; lines=text.splitlines(); info.update({'type':'text','lines':len(lines),'nonempty':sum(bool(x.strip()) for x in lines),'preview':'\n'.join(lines[:20])})
            except Exception as e: info['error']=str(e); report['warnings'].append(f'{rel}: {e}')
            report['files'].append(info); report['totals']['files']+=1; report['totals']['bytes']+=info['bytes']
        out=self.root/'analysis_report.json'; out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); report['artifact']=str(out)
        report['artifacts']=self.builder.write_report(report)
        return report
