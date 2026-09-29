from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from .sandbox import SandboxRunner

@dataclass
class ExecutionPlan:
    task_id:str; agent:str; command:str; cwd:str='.'

class ParallelExecutor:
    def __init__(self, sandbox:SandboxRunner, agents, audit=None, max_workers=4):
        self.sandbox=sandbox; self.agents=agents; self.audit=audit; self.max_workers=max(1,min(int(max_workers),16))
    def run_commands(self, plans:list[ExecutionPlan]):
        results=[]
        with ThreadPoolExecutor(max_workers=min(self.max_workers,len(plans) or 1)) as pool:
            futs={pool.submit(self._one,p):p for p in plans}
            for f in as_completed(futs): results.append(f.result())
        return results
    def _one(self, p):
        result=self.sandbox.run(p.command,p.cwd)
        payload={'task_id':p.task_id,'agent':p.agent,'status':result.status,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'mode':result.mode}
        if self.audit: self.audit.log('execution.completed',details=payload)
        return payload
