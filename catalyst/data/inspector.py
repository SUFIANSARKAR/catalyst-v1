import csv, json, math, statistics
from pathlib import Path

class DatasetInspector:
    """Scalable, model-friendly data inspection. Reads bounded samples, never blindly loads a dataset."""
    def __init__(self, workspace_root: str):
        self.root=Path(workspace_root).resolve()

    def _safe(self, rel: str) -> Path:
        p=(self.root/rel).resolve()
        if p!=self.root and self.root not in p.parents: raise PermissionError("Path escapes workspace")
        if not p.exists() or not p.is_file(): raise FileNotFoundError(rel)
        return p

    def inspect(self, rel: str, sample_rows: int=1000):
        p=self._safe(rel); suffix=p.suffix.lower(); size=p.stat().st_size
        if suffix=='.csv': return self._csv(p, sample_rows, size, rel)
        if suffix=='.json': return self._json(p, sample_rows, size, rel)
        if suffix in {'.jsonl','.ndjson'}: return self._jsonl(p, sample_rows, size, rel)
        text=p.read_text(encoding='utf-8', errors='replace')
        lines=text.splitlines()
        return {"type":"text", "path":rel, "bytes":size, "lines":len(lines), "preview":"\n".join(lines[:100])}

    def _csv(self,p,limit,size,rel):
        rows=[]; fields=[]
        with p.open('r',encoding='utf-8-sig',newline='') as f:
            r=csv.DictReader(f); fields=r.fieldnames or []
            for i,row in enumerate(r):
                if i>=limit: break
                rows.append(row)
        stats={}
        for field in fields:
            vals=[r.get(field) for r in rows if r.get(field) not in (None,'')]
            nums=[float(v) for v in vals if self._num(v)]
            item={"non_empty":len(vals),"numeric":len(nums)}
            if nums:
                item.update(mean=statistics.fmean(nums), min=min(nums), max=max(nums), std=statistics.pstdev(nums) if len(nums)>1 else 0.0)
            stats[field]=item
        return {"type":"csv","path":rel,"bytes":size,"columns":fields,"rows_sampled":len(rows),"sample_rows":rows[:20],"column_stats":stats}

    def _json(self,p,limit,size,rel):
        # JSON can be large; use a size guard and make large-file handling explicit.
        if size>50_000_000: return {"type":"json","path":rel,"bytes":size,"status":"large_file","message":"Use a streaming JSON processor or bounded extraction before model analysis."}
        obj=json.loads(p.read_text(encoding='utf-8'))
        return {"type":"json","path":rel,"bytes":size,"shape":self._shape(obj),"sample":self._sample(obj,limit)}

    def _jsonl(self,p,limit,size,rel):
        rows=[]
        with p.open('r',encoding='utf-8',errors='replace') as f:
            for line in f:
                if len(rows)>=limit: break
                if line.strip():
                    try: rows.append(json.loads(line))
                    except json.JSONDecodeError: pass
        return {"type":"jsonl","path":rel,"bytes":size,"rows_sampled":len(rows),"sample":rows[:20]}

    @staticmethod
    def _num(v):
        try: float(v); return True
        except (TypeError,ValueError): return False
    @staticmethod
    def _shape(obj):
        if isinstance(obj,dict): return {"kind":"object","keys":len(obj),"sample_keys":list(obj)[:30]}
        if isinstance(obj,list): return {"kind":"array","items":len(obj)}
        return {"kind":type(obj).__name__}
    @staticmethod
    def _sample(obj,limit):
        if isinstance(obj,dict): return {k:obj[k] for k in list(obj)[:30]}
        if isinstance(obj,list): return obj[:min(limit,20)]
        return obj
