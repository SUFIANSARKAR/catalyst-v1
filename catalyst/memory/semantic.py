from ..providers.embeddings import EmbeddingProvider
from ..embeddings.index import EmbeddingIndex

class SemanticMemoryBridge:
    """Optional semantic layer over the durable MemoryStore; lexical memory remains the fallback."""
    def __init__(self, memory, gateway, settings):
        self.memory=memory; self.gateway=gateway; self.settings=settings
        self.index=EmbeddingIndex('catalyst_data/memory_embeddings.db')
    def _provider(self):
        p=self.gateway.select_profile('embedding', ('embeddings',))
        if not p: return None
        return EmbeddingProvider(p.base_url,p.api_key,p.options.get('embedding_model') or self.settings.embedding_model or p.model,self.settings.request_timeout)
    def index_memories(self, limit=1000):
        p=self._provider()
        if not p: return {'status':'unavailable','indexed':0,'reason':'No embeddings-capable provider'}
        rows=self.memory.recent_active(limit)
        if not rows:return {'status':'ok','indexed':0}
        vecs=p.embed([r['text'] for r in rows])
        for row,vec in zip(rows,vecs):self.index.upsert('memory',str(row['id']),row['text'],vec)
        return {'status':'ok','indexed':len(rows),'total':self.index.count('memory')}
    def upsert_memory(self, memory_id):
        p=self._provider()
        row=self.memory.get(int(memory_id))
        if not p or not row or row.get('archived'): return {'status':'skipped','memory_id':memory_id}
        vec=p.embed([row['text']])[0]
        self.index.upsert('memory',str(row['id']),row['text'],vec)
        return {'status':'ok','memory_id':row['id']}

    def search(self, query, limit=12):
        p=self._provider()
        if not p:return []
        vec=p.embed([query])[0]; hits=self.index.search('memory',vec,limit)
        by_id={str(x['id']):x for x in self.memory.recent_active(5000)}
        out=[]
        for h in hits:
            row=by_id.get(str(h['ref']))
            if row: row=dict(row); row['semantic_score']=h['score']; out.append(row)
        return out
    def close(self):self.index.close()
