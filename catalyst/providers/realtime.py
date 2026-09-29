from __future__ import annotations
import json
import httpx

class RealtimeProviderBridge:
    """Optional provider metadata/health bridge. Does not assume a vendor-specific realtime protocol."""
    def __init__(self, gateway): self.gateway=gateway
    def profiles(self):
        out=[]
        for p in self.gateway.profiles.values():
            opts=p.options or {}; rt=opts.get('realtime',{}) or {}
            out.append({'name':p.name,'configured':p.configured,'realtime_enabled':bool(rt.get('enabled')),'transport':rt.get('transport','websocket'),'endpoint':bool(rt.get('endpoint')),'model':rt.get('model')})
        return out
    def health(self, name=None):
        p=self.gateway.profiles.get(name or self.gateway.active_name) if (name or self.gateway.active_name) else None
        if not p: return {'configured':False,'error':'No provider profile'}
        rt=(p.options or {}).get('realtime',{}) or {}; endpoint=rt.get('endpoint')
        if not endpoint: return {'configured':p.configured,'realtime_enabled':False,'provider':p.name}
        try:
            with httpx.Client(timeout=5) as c: r=c.get(endpoint,headers={'Authorization':f'Bearer {p.api_key}'})
            return {'configured':p.configured,'realtime_enabled':True,'provider':p.name,'status_code':r.status_code}
        except Exception as e: return {'configured':p.configured,'realtime_enabled':True,'provider':p.name,'error':str(e)}
