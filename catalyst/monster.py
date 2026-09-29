from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .engineering.agent import EngineeringAgent
from .engineering.factory import EngineeringProductionFactory
from .providers.local import LocalModelConfig, LocalModelProvider
from .reasoning import ReasoningEngine, ReasoningMemory
from .reasoning.deliberator import ApexDeliberator
from .apex import ApexRuntime, ApexMissionStore

@dataclass
class MonsterConfig:
    local_base_url: str='http://127.0.0.1:11434/v1'
    local_model: str=''
    local_timeout: float=180.0
    max_iterations: int=24
    max_engineering_cycles: int=3
    data_root: str='catalyst_data'
    reasoning_mode: str='auto'
    reasoning_model_calls: int=1

class CatalystMonster:
    """High-level Catalyst v4.5 facade: executive over engineering and production subsystems."""
    protocol='catalyst.monster.v4'
    release_protocol='catalyst.monster.v5.5'
    apex_protocol='catalyst.apex-runtime.v3'
    def __init__(self, workspace_root: str, gateway=None, executor=None, config: MonsterConfig|None=None):
        self.config=config or MonsterConfig(); self.gateway=gateway; self.executor=executor
        self.local=LocalModelProvider(LocalModelConfig(self.config.local_base_url,self.config.local_model,timeout=self.config.local_timeout))
        reasoning_memory=ReasoningMemory(str(__import__('pathlib').Path(self.config.data_root) / 'reasoning.db'))
        self.reasoning=ReasoningEngine(memory=reasoning_memory)
        self.deliberator=ApexDeliberator(self.reasoning, model=self._reasoning_model, mode=self.config.reasoning_mode, max_model_calls=max(0,min(2,int(self.config.reasoning_model_calls))))
        self.apex=ApexRuntime(self.reasoning, deliberator=self.deliberator, store=ApexMissionStore(str(__import__("pathlib").Path(self.config.data_root) / "apex_missions.db")))
        self.engineering=EngineeringAgent(workspace_root, model=self._model, executor=executor, max_iterations=max(12,self.config.max_iterations), data_root=self.config.data_root, specialist_executor=executor)
        self.factory=EngineeringProductionFactory(self.engineering, max_cycles=self.config.max_engineering_cycles)
        self.apex.register_subsystem('engineering', self._apex_engineering_dispatch, label='engineering-production-factory')

    def _apex_engineering_dispatch(self, objective: str, *, mission=None):
        result=self.factory.run(objective, execute=True, approval=True)
        return result.as_dict()

    def _reasoning_model(self, messages, tools=None):
        if self.gateway:
            try:
                return self.gateway.chat(messages, tools=None, temperature=.1, task="planning")
            except Exception:
                pass
        if self.local.configured:
            try:
                return self.local.chat(messages, tools=None, temperature=.1)
            except Exception:
                pass
        return {"content":""}

    def _model(self, messages, tools=None):
        if self.gateway:
            try:
                return self.gateway.chat(messages, tools=tools, temperature=.15, task='coding')
            except Exception:
                pass
        if self.local.configured:
            return self.local.chat(messages, tools=tools, temperature=.15)
        raise RuntimeError('No reasoning provider configured.')

    def status(self) -> dict[str,Any]:
        return {'protocol':self.protocol,'release_protocol':self.release_protocol,'local':self.local.health(),'reasoning':{'protocol':'catalyst.reasoning.v3','recent_traces':len(self.reasoning.memory.recent(20))},'apex':{'protocol':self.apex.protocol,'release':'5.5.0','reasoning_deliberation':True,'durable_missions':True,'registered_execution_adapters':sorted(self.apex.subsystems)},'engineering':{'protocol':self.engineering.protocol,'factory_protocol':self.factory.protocol,'max_iterations':self.engineering.max_iterations,'max_cycles':self.factory.max_cycles,'tool_count':len(self.engineering.toolbox.schemas()),'tools':[x['function']['name'] for x in self.engineering.toolbox.schemas()]},'repository':self.engineering.repository.architecture_snapshot(),'cloud_gateway':bool(self.gateway)}

    def mission(self, objective: str, execute: bool=False, approval: bool=False) -> dict[str,Any]:
        run=self.engineering.run(objective,execute=execute,approval=approval)
        return {'protocol':self.release_protocol,'objective':objective,'status':run.status,'phase':run.phase,'iterations':run.iterations,'plan':run.plan,'evidence':run.evidence}

    def production_mission(self, objective: str, execute: bool=False, approval: bool=False, focus_files: list[str]|None=None) -> dict[str,Any]:
        result=self.factory.run(objective,execute=execute,approval=approval,focus_files=focus_files or [])
        return result.as_dict()

    def apex_plan(self, objective: str) -> dict[str, Any]:
        mission = self.apex.plan(objective, context={"evidence_available": True, "candidate_tools": [x["function"]["name"] for x in self.engineering.toolbox.schemas()]})
        return mission.as_dict()
