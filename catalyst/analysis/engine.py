import csv,hashlib,json,math,re,statistics
from pathlib import Path
from typing import Any
from .index import ChunkIndex
from ..embeddings.index import EmbeddingIndex

TEXT_EXTENSIONS={".py",".js",".ts",".tsx",".jsx",".md",".txt",".json",".yaml",".yml",".toml",".sql",".sh",".rs",".go",".java",".cpp",".c",".html",".css",".xml",".csv",".log"}
IGNORE_DIRS={".git",".venv","node_modules","__pycache__",".pytest_cache","dist","build",".next"}

class DataAnalysisEngine:
    def __init__(self,workspace_root:str,data_root:str):
        self.workspace=Path(workspace_root).resolve();self.data_root=Path(data_root).resolve();self.data_root.mkdir(parents=True,exist_ok=True)
        self.index_path=self.data_root/"project_index.json"; self.chunks=ChunkIndex(str(self.data_root/"chunks.db")); self.embeddings=EmbeddingIndex(str(self.data_root/"embeddings.db"))
    def _files(self):
        for p in self.workspace.rglob('*'):
            if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS and not any(part in IGNORE_DIRS for part in p.parts): yield p
    def index_project(self):
        records=[]; chunk_sources=[];total=0
        for p in self._files():
            try: data=p.read_bytes(); stat=p.stat()
            except OSError: continue
            digest=hashlib.sha256(data).hexdigest();total+=len(data);rel=str(p.relative_to(self.workspace));records.append({"path":rel,"bytes":len(data),"sha256":digest,"suffix":p.suffix.lower(),"mtime":stat.st_mtime})
            if len(data)<=5_000_000: chunk_sources.append((rel,data.decode("utf-8","replace"),digest))
        chunks=self.chunks.rebuild(chunk_sources)
        payload={"workspace":str(self.workspace),"files":records,"total_files":len(records),"total_bytes":total,"chunks":chunks}
        self.index_path.write_text(json.dumps(payload,indent=2),encoding='utf-8');return payload
    def search(self,query,limit=12,semantic_vector=None):
        lexical=self.chunks.search(query,limit*2)
        if not semantic_vector: return lexical[:limit]
        vec_hits=self.embeddings.search('project',semantic_vector,limit*2)
        by_key={f"{x['path']}#{x['chunk']}":x for x in lexical}
        merged=[]
        for v in vec_hits:
            ref=v['ref']; item=by_key.get(ref)
            if item: merged.append({**item,'score':round(0.55*item['score']+0.45*v['score'],6)})
            else:
                if '#' in ref:
                    path,chunk=ref.rsplit('#',1); merged.append({'path':path,'chunk':int(chunk),'content':v['text'],'score':round(v['score'],6)})
        for x in lexical:
            if not any(y['path']==x['path'] and y['chunk']==x['chunk'] for y in merged): merged.append(x)
        merged.sort(key=lambda x:x['score'],reverse=True); return merged[:limit]
    def build_embeddings(self, embed_fn, batch_size=32):
        rows=[]
        cur=self.chunks.db.execute('SELECT path,chunk_no,content FROM chunks ORDER BY id')
        for r in cur: rows.append((f"{r['path']}#{r['chunk_no']}",r['content']))
        for i in range(0,len(rows),batch_size):
            batch=rows[i:i+batch_size]; vectors=embed_fn([x[1] for x in batch])
            for (ref,text),vec in zip(batch,vectors): self.embeddings.upsert('project',ref,text,vec)
        return {'embedded':len(rows)}
    def analyze_file(self,relative_path,max_rows=1000):
        p=(self.workspace/relative_path).resolve()
        if p!=self.workspace and self.workspace not in p.parents: raise PermissionError("Path escapes workspace")
        if not p.exists() or not p.is_file(): raise FileNotFoundError(relative_path)
        suffix=p.suffix.lower()
        if suffix=='.csv':
            with p.open('r',encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f);rows=[]
                for i,row in enumerate(reader):
                    if i>=max_rows:break
                    rows.append(row)
            fields=reader.fieldnames or [];stats={}
            for field in fields:
                vals=[r.get(field) for r in rows];numeric=[float(v) for v in vals if v not in (None,'') and _is_number(v)];stats[field]={"non_empty":sum(v not in (None,'') for v in vals),"numeric":len(numeric),"min":min(numeric) if numeric else None,"max":max(numeric) if numeric else None,"mean":statistics.fmean(numeric) if numeric else None}
            return {"type":"csv","path":relative_path,"sample_rows":rows[:20],"rows_sampled":len(rows),"columns":fields,"column_stats":stats}
        if suffix=='.json':
            obj=json.loads(p.read_text(encoding='utf-8'));return {"type":"json","path":relative_path,"shape":_shape(obj),"sample":_sample(obj)}
        text=p.read_text(encoding='utf-8',errors='replace');lines=text.splitlines();
        return {"type":"text","path":relative_path,"bytes":len(text.encode()),"lines":len(lines),"non_empty_lines":sum(bool(x.strip()) for x in lines),"preview":"\n".join(lines[:80])}
    def profile_dataset(self,relative_path,max_rows=100000):
        result=self.analyze_file(relative_path,max_rows);return result

def _is_number(v):
    try: float(v);return True
    except (TypeError,ValueError):return False

def _shape(obj):
    if isinstance(obj,dict): return {"kind":"object","keys":len(obj),"sample_keys":list(obj)[:20]}
    if isinstance(obj,list): return {"kind":"array","items":len(obj)}
    return {"kind":type(obj).__name__}

def _sample(obj):
    if isinstance(obj,dict): return {k:obj[k] for k in list(obj)[:20]}
    if isinstance(obj,list): return obj[:10]
    return obj
