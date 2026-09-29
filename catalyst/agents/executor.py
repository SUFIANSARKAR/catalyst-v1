from concurrent.futures import ThreadPoolExecutor, as_completed
from ..execution import SandboxRunner
from .adapters import AgentAdapter

class AgentExecutionManager:
    def __init__(self, agents, workspace, data_root, audit=None, settings=None, provider=None, integrations=None):
        self.agents=agents; self.audit=audit; self.settings=settings; self.provider=provider; self.integrations=integrations
        self.sandbox=SandboxRunner(
            workspace,
            data_root,
            getattr(settings,'sandbox_mode','auto'),
            getattr(settings,'docker_image','python:3.12-slim'),
            getattr(settings,'sandbox_timeout',120),
            getattr(settings,'sandbox_memory_mb',2048),
            getattr(settings,'sandbox_cpus',2.0),
            getattr(settings,'sandbox_pids',256),
        )
    def run(self, tasks, max_workers=None, synthesize=True):
        if not tasks: return {'results':[], 'synthesis':None}
        limit=max_workers or getattr(self.settings,'max_parallel_agents',4); limit=max(1,min(limit,16)); results=[]
        with ThreadPoolExecutor(max_workers=min(limit,len(tasks))) as pool:
            futs=[pool.submit(self._run_one,t) for t in tasks]
            for fut in as_completed(futs):
                try: results.append(fut.result())
                except Exception as exc: results.append({'status':'failed','error':str(exc)})
        synthesis=self.synthesize(results) if synthesize else None
        return {'results':results,'synthesis':synthesis}
    def _run_one(self, task):
        spec=self.agents.get(task.get('agent',''))
        if not spec:
            return {'task_id':task.get('id'),'status':'unconfigured','agent':task.get('agent')}
        description=task.get('description') or task.get('title','')
        agent_name=spec.name
        if self.integrations and task.get('native', True):
            try:
                if agent_name == 'tc_engineering_ai' and self.integrations.tc.configured:
                    result=self.integrations.tc.submit(description, wait=bool(task.get('wait', True))).as_dict()
                elif agent_name == 'full_self_coding' and self.integrations.fsc.configured and task.get('native_mode') == 'fsc':
                    result=self.integrations.fsc.run(task.get('cwd') or '.', task.get('config') or {}, timeout=task.get('timeout')) .as_dict()
                else:
                    result=spec.adapter.run(description, task.get('cwd') or '.', task.get('id'))
            except Exception as exc:
                result={'status':'failed','agent':agent_name,'error':str(exc)}
        else:
            result=spec.adapter.run(description, task.get('cwd') or '.', task.get('id'))
        result['task_id']=task.get('id')
        if self.audit: self.audit.log('agent.completed',details=result)
        return result
    def synthesize(self, results):
        if not self.provider or not any(r.get('status') in {'completed','failed','unconfigured'} for r in results):
            return None
        payload='\n\n'.join(
            f"TASK {r.get('task_id')}: status={r.get('status')} agent={r.get('agent','')}\n"
            f"stdout={str(r.get('stdout',''))[-12000:]}\nerror={str(r.get('stderr',r.get('error','')))[-6000:]}"
            for r in results
        )
        try:
            msg=self.provider.chat([
                {'role':'system','content':'You are Catalyst\'s result synthesizer. Compare specialist results, surface conflicts, distinguish evidence from claims, and recommend the next concrete action. Do not invent missing evidence.'},
                {'role':'user','content':'Synthesize these specialist execution results:\n'+payload}
            ],None,0.1)
            return (msg.get('content') or '').strip() or None
        except Exception as exc:
            return f'Synthesis unavailable: {exc}'
