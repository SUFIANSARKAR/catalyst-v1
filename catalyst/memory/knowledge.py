from __future__ import annotations
import json

class KnowledgeMemory:
    """Coordinator for durable, semantic, procedural, and temporal world memory."""
    def __init__(self,memory_store,world_model=None,semantic=None): self.memory=memory_store;self.world_model=world_model;self.semantic=semantic
    def remember(self,text,kind='note',metadata=None,importance=.5):
        mid=self.memory.add(text,kind,metadata,importance)
        if self.semantic:
            try:self.semantic.upsert_memory(mid)
            except Exception:pass
        if self.world_model:
            try:self.world_model.ingest_memory(text,metadata,confidence=importance,source=f'memory:{kind}')
            except Exception:pass
        return mid
    def remember_procedure(self,name,steps,success_rate=1.0,source='experience',metadata=None):
        payload=json.dumps({'name':name,'steps':steps,'success_rate':success_rate},ensure_ascii=False)
        meta={'procedure_name':name,'source':source};meta.update(metadata or {})
        return self.remember(payload,'procedure',meta,.85)
    def record_event(self,event_type,summary,metadata=None,importance=.7):
        meta={'event_type':event_type};meta.update(metadata or {});return self.remember(summary,'event',meta,importance)
    def recall(self,query,limit=12):
        lexical=self.memory.search(query,limit)
        semantic=[]
        if self.semantic:
            try:semantic=self.semantic.search(query,limit)
            except Exception:pass
        merged={str(x['id']):x for x in lexical}
        for x in semantic: merged.setdefault(str(x['id']),x)
        return list(merged.values())[:limit]
