from dataclasses import dataclass
from typing import Any, Callable
from .adapters import default_adapters, AgentAdapter

@dataclass
class AgentSpec:
    name: str
    description: str
    handler: Callable[[str], Any] | None = None
    adapter: AgentAdapter | None = None
    capabilities: tuple[str, ...] = ()
    max_turns: int = 12

class AgentRegistry:
    def __init__(self):
        self._agents = {}
        for a in default_adapters():
            caps = {
                'tc_engineering_ai': ('engineering','coding','verification'),
                'full_self_coding': ('repo-analysis','parallel-coding','testing'),
                'openhands': ('coding','terminal','browser'),
            }.get(a.name, ('general',))
            self.register(AgentSpec(a.name, a.description, adapter=a, capabilities=caps))
        self.register(AgentSpec('general','Catalyst general-purpose reasoning worker',capabilities=('reasoning','planning'),max_turns=8))
        self.register(AgentSpec('research','Research and evidence specialist',capabilities=('research','sources'),max_turns=10))
        self.register(AgentSpec('analyst','Data and quantitative analysis specialist',capabilities=('data','statistics'),max_turns=10))

    def register(self, spec): self._agents[spec.name] = spec
    def get(self, name): return self._agents.get(name)
    def names(self): return sorted(self._agents)
    def describe(self):
        return [{'name':x.name,'description':x.description,'available':bool(x.handler or (x.adapter and x.adapter.available())),'capabilities':list(x.capabilities),'max_turns':x.max_turns} for x in self._agents.values()]
    def choose(self, task: str) -> str:
        t = task.lower()
        if any(k in t for k in ('repository','repo','code','coding','bug','debug','implement','test','software')):
            for name in ('tc_engineering_ai','openhands','full_self_coding'):
                s=self._agents.get(name)
                if s and s.adapter and s.adapter.available(): return name
            return 'general'
        if any(k in t for k in ('research','compare','sources','latest','investigate','paper')): return 'research'
        if any(k in t for k in ('dataset','csv','json','statistics','analyze','analysis')): return 'analyst'
        return 'general'
