from dataclasses import dataclass,asdict
from typing import Any
@dataclass
class AgentTask:
 protocol:str='catalyst.agent.v1';task_id:str='';agent:str='';task:str='';cwd:str='.';context:dict[str,Any]|None=None;constraints:dict[str,Any]|None=None
@dataclass
class AgentResult:
 protocol:str='catalyst.agent.v1';status:str='completed';agent:str='';task_id:str='';summary:str='';artifacts:list[dict[str,Any]]|None=None;tests:list[dict[str,Any]]|None=None;commits:list[str]|None=None;evidence:list[dict[str,Any]]|None=None;error:str|None=None
def normalize_result(raw,agent,task_id=''):
 base=asdict(AgentResult(agent=agent,task_id=task_id));base.update({k:v for k,v in raw.items() if k not in {'stdout','stderr','agent'}});return base
