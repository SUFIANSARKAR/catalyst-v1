import httpx
class EmbeddingProvider:
    def __init__(self, base_url, api_key, model, timeout=120):
        self.base_url=base_url.rstrip('/'); self.api_key=api_key; self.model=model; self.timeout=timeout
    def embed(self, texts):
        if not self.api_key or not self.model: raise RuntimeError('Embedding provider is not configured')
        payload={"model":self.model,"input":texts}
        with httpx.Client(timeout=self.timeout) as client:
            r=client.post(f"{self.base_url}/embeddings",headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},json=payload); r.raise_for_status(); data=r.json()['data']; data.sort(key=lambda x:x['index']); return [x['embedding'] for x in data]
