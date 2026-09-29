from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Principal:
    subject: str = 'creator'
    role: str = 'creator'

class PolicyEngine:
    """Capability policy layer. Authentication can be layered outside it; this stays deterministic."""
    ROLE_CAPS={
        'creator': {'read','write','shell','delegate','automation','approval','model','admin','audio','voice','improvement','device','perception'},
        'developer': {'read','write','shell','delegate','approval','model','audio','voice','improvement','device','perception'},
        'researcher': {'read','web','research','delegate','voice'},
        'analyst': {'read','analysis','research','voice'},
        'automation': {'read','write','delegate','research','analysis','device','perception','voice'},
        'guest': {'read','research'},
    }
    def __init__(self, default_role='creator'): self.default_role=default_role
    def allowed(self, principal:Principal, capability:str)->bool:
        return capability in self.ROLE_CAPS.get(principal.role,set())
    def require(self, principal, capability):
        if not self.allowed(principal,capability): raise PermissionError(f'Role {principal.role} lacks capability {capability}')
    def describe(self): return {k:sorted(v) for k,v in self.ROLE_CAPS.items()}
