import json, platform, os
from dataclasses import dataclass
from typing import Any
from .protocol import SUPPORTED_ACTIONS, READ_ONLY_ACTIONS

@dataclass
class ShellBridge:
    registry: Any
    def command(self,device_id:str,action:str,payload:dict|None=None,requires_confirmation:bool=True)->dict:
        if action not in SUPPORTED_ACTIONS: raise ValueError('Unsupported device action')
        device=self.registry.get(device_id)
        if not device: raise ValueError('Unknown device')
        if action not in device.get('capabilities',[]): raise ValueError(f'Device does not advertise capability: {action}')
        if action in READ_ONLY_ACTIONS: requires_confirmation=False
        return {'protocol':'catalyst.device.v1','device_id':device_id,'action':action,'payload':payload or {},'requires_confirmation':requires_confirmation}
    def can(self,device_id:str,capability:str)->bool:
        d=self.registry.get(device_id); return bool(d and capability in d.get('capabilities',[]))
    def validate_result(self,command,result):
        if not isinstance(result,dict): raise ValueError('Device result must be an object')
        return {'command_id':command.get('id'),'device_id':command['device_id'],'action':command['action'],'ok':bool(result.get('ok',False)),'result':result}

def local_system_info():
    return {'platform':platform.system(),'release':platform.release(),'machine':platform.machine(),'python':platform.python_version(),'pid':os.getpid()}
