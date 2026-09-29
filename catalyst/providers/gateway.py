from .openai_compatible import OpenAICompatibleProvider
from .embeddings import EmbeddingProvider
from ..config import ProviderProfile

class ModelGateway:
    def __init__(self, settings, observability=None):
        self.settings=settings; self.observability=observability
        self.profiles=settings.load_profiles(); saved=getattr(settings,'_active_profile',''); self.active_name=saved if saved in self.profiles else ('default' if 'default' in self.profiles else next(iter(self.profiles),''))
        self._providers={}; self._refresh_all()
    def _refresh_all(self):
        self._providers={p.name:OpenAICompatibleProvider(
            p.base_url, p.api_key, p.model, self.settings.request_timeout,
            self.settings.max_tokens, settings=self.settings, options=p.options
        ) for p in self.profiles.values()}
    @property
    def active_profile(self): return self.profiles.get(self.active_name)
    def list_profiles(self):
        return [{**{k:getattr(p,k) for k in ('name','base_url','model','kind')}, 'configured':p.configured,'api_key_set':bool(p.api_key),'active':p.name==self.active_name,'capabilities':list(getattr(p,'capabilities',()) or ()),'role':getattr(p,'role','general')} for p in self.profiles.values()]
    def upsert_profile(self,p):
        self.settings.save_profile(p); self.profiles[p.name]=p; self.active_name=self.active_name or p.name; self._refresh_all()
    def activate(self,name):
        if name not in self.profiles: raise KeyError(name)
        self.active_name=name
        self.settings.save_active_profile(name)
    def health(self):
        p=self.active_profile
        return {'configured':bool(p and p.configured),'provider':p.name if p else None,'model':p.model if p else None,'base_url':p.base_url if p else None,'profiles':len(self.profiles)}
    def _ordered_names(self, task='general'):
        active=self.active_name
        prefs=getattr(self.settings,'model_routes',{}) or {}
        desired=prefs.get(task) or prefs.get('default')
        names=[]
        if desired and desired in self.profiles: names.append(desired)
        if active and active not in names: names.append(active)
        for name,p in self.profiles.items():
            if p.configured and name not in names: names.append(name)
        return names
    def select_profile(self, task='general', require_capabilities=()):
        for name in self._ordered_names(task):
            p=self.profiles.get(name)
            if not p or not p.configured: continue
            caps=set(getattr(p,'capabilities',()) or ())
            if all(c in caps for c in require_capabilities): return p
        return None
    def chat(self,messages,tools=None,temperature=.2,task='general',require_capabilities=()):
        names=[n for n in self._ordered_names(task) if all(c in set(getattr(self.profiles[n],'capabilities',()) or ()) for c in require_capabilities) or not require_capabilities]
        last=None
        if not names: raise RuntimeError('No model provider configured. Open Settings and add a provider profile.')
        for name in names:
            p=self.profiles[name]
            if not p.configured: continue
            provider=self._providers[name]
            span=self.observability.start_span('provider.chat',metadata={'profile':name,'model':p.model,'task':task}) if self.observability else None
            try:
                result=provider.chat(messages,tools,temperature)
                if self.observability: self.observability.end_span(span,'ok'); self.observability.incr('provider.chat.success')
                return result
            except Exception as exc:
                last=exc
                if self.observability: self.observability.end_span(span,'error',str(exc)); self.observability.incr('provider.chat.error')
        raise RuntimeError(f'All configured providers failed: {last}')
    def stream(self,messages,tools=None,temperature=.2,task='general',require_capabilities=()):
        names=[n for n in self._ordered_names(task) if all(c in set(getattr(self.profiles[n],'capabilities',()) or ()) for c in require_capabilities) or not require_capabilities]
        if not names: raise RuntimeError('No model provider configured')
        for name in names:
            p=self.profiles[name]
            if not p.configured: continue
            provider=self._providers[name]
            span=self.observability.start_span('provider.stream',metadata={'profile':name,'model':p.model,'task':task}) if self.observability else None
            try:
                for item in provider.stream(messages,tools,temperature): yield item
                if self.observability: self.observability.end_span(span,'ok'); self.observability.incr('provider.stream.success')
                return
            except Exception as exc:
                if self.observability: self.observability.end_span(span,'error',str(exc)); self.observability.incr('provider.stream.error')
                last=exc
                continue
        raise RuntimeError(f'All configured providers failed: {last}')
    def embeddings(self,texts,model=None):
        p=self.active_profile
        if not p: raise RuntimeError('No model provider configured')
        ep=EmbeddingProvider(p.base_url,p.api_key,model or getattr(self.settings,'embedding_model',''))
        return ep.embed(texts)
