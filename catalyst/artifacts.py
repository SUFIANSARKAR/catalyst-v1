from datetime import datetime, timezone
from pathlib import Path
import hashlib, json

class ArtifactStore:
    def __init__(self, root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def _safe(self,name): return Path(name).name
    def write_json(self,name,payload):
        path=self.root/self._safe(name); path.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8'); return self._meta(path,'json')
    def write_text(self,name,text):
        path=self.root/self._safe(name); path.write_text(text,encoding='utf-8'); return self._meta(path,'text')
    def write_bytes(self,name,data,media_type='application/octet-stream'):
        path=self.root/self._safe(name); path.write_bytes(data); return self._meta(path,media_type)
    def _meta(self,path,kind):
        data=path.read_bytes(); return {'name':path.name,'path':str(path),'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'created_at':datetime.now(timezone.utc).isoformat(),'type':kind}
    def delete(self,name):
        path=(self.root/Path(name).name).resolve()
        if self.root.resolve() not in path.parents or not path.exists(): raise FileNotFoundError(name)
        path.unlink(); return {'name':path.name,'deleted':True}
    def list(self,limit=200):
        out=[]
        for p in sorted((x for x in self.root.iterdir() if x.is_file()), key=lambda x:x.stat().st_mtime, reverse=True)[:max(1,min(limit,500))]: out.append(self._meta(p,p.suffix.lower() or 'binary'))
        return out
