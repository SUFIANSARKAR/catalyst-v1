from dataclasses import dataclass

@dataclass(frozen=True)
class CapabilityPolicy:
    role:str='creator'
    allow_read:bool=True
    allow_web:bool=True
    allow_write:bool=False
    allow_shell:bool=False
    allow_external:bool=False

ROLE_DEFAULTS={
    'creator': CapabilityPolicy('creator',True,True,False,False,False),
    'developer': CapabilityPolicy('developer',True,True,True,True,False),
    'researcher': CapabilityPolicy('researcher',True,True,False,False,False),
    'analyst': CapabilityPolicy('analyst',True,True,False,False,False),
    'automation': CapabilityPolicy('automation',True,True,True,True,False),
}

def policy_for(role): return ROLE_DEFAULTS.get(role, ROLE_DEFAULTS['creator'])
