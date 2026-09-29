from datetime import datetime,timezone
class HealthRegistry:
 def __init__(self):self._checks={}
 def set(self,name,status,detail=None,latency_ms=None):self._checks[name]={'name':name,'status':status,'detail':detail,'latency_ms':latency_ms,'updated_at':datetime.now(timezone.utc).isoformat()}
 def report(self):
  vals=list(self._checks.values());overall='ok' if vals and all(x['status']=='ok' for x in vals) else ('degraded' if any(x['status']=='ok' for x in vals) else 'down');return {'status':overall,'checks':vals}
