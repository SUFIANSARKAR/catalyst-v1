from __future__ import annotations
import json, time
from pathlib import Path

class WorkingMemory:
    """Durable token-aware-ish working buffer. Uses character approximation until a tokenizer is configured."""
    def __init__(self, path='catalyst_data/working_memory.json', max_chars=24000, keep_recent=10):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.max_chars=max(4000,int(max_chars)); self.keep_recent=max(2,int(keep_recent)); self._load()
    def _load(self):
        try:self.items=json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:self.items=[]
    def _save(self): self.path.write_text(json.dumps(self.items,indent=2,ensure_ascii=False),encoding='utf-8')
    def append(self, role, content, metadata=None):
        self.items.append({'role':role,'content':str(content),'metadata':metadata or {},'ts':time.time()}); self._trim(); self._save()
    def _trim(self):
        total=sum(len(x['content']) for x in self.items)
        if total<=self.max_chars:return
        recent=self.items[-self.keep_recent:]; older=self.items[:-self.keep_recent]
        summary=' '.join(x['content'] for x in older)[-6000:]
        self.items=[{'role':'system','content':'Working-memory summary: '+summary,'metadata':{'compacted':True},'ts':time.time()}]+recent
        while sum(len(x['content']) for x in self.items)>self.max_chars and len(self.items)>2:self.items.pop(1)
    def context(self): return list(self.items)
    def clear(self): self.items=[]; self._save()
