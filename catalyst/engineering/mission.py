from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .intelligence import EngineeringIntelligence

@dataclass
class EngineeringMission:
    objective: str
    stages: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    status: str = 'planned'
    def as_dict(self):
        return {'protocol':'catalyst.engineering-mission.v1','objective':self.objective,'stages':self.stages,'evidence':self.evidence[-100:],'status':self.status}

class EngineeringMissionController:
    def __init__(self, repository, test_strategy): self.intelligence=EngineeringIntelligence(repository,test_strategy)
    def prepare(self, objective, focus_files=None):
        objective=str(objective).strip()
        if not objective: raise ValueError('objective is required')
        pack=self.intelligence.context_pack(objective, focus_files=focus_files or [])
        m=EngineeringMission(objective,evidence=[{'event':'context_pack','candidate_files':pack.get('candidate_files',[]),'test_strategy':pack.get('test_strategy',{})}])
        m.stages=[
          {'id':'understand','kind':'recon','approval':False}, {'id':'design','kind':'plan','approval':False},
          {'id':'implement','kind':'mutation','approval':True,'isolation':'git-worktree'},
          {'id':'verify','kind':'tests','approval':False,'required':True}, {'id':'impact','kind':'dependency-review','approval':False,'required':True},
          {'id':'review','kind':'diff-review','approval':False,'required':True}, {'id':'recover','kind':'bounded-repair','approval':True,'conditional':True}]
        return m
    def reconcile(self, mission, changed_files, test_results, diff):
        impact=self.intelligence.impact_analysis(changed_files); review=self.intelligence.review_report(diff,changed_files,test_results)
        failures=[x for x in test_results if isinstance(x,dict) and x.get('returncode') not in (0,None)]
        mission.evidence += [{'event':'impact',**impact},{'event':'review',**review}]
        mission.status='completed' if review.get('ready_for_completion') and not failures else 'needs_recovery'
        return {'mission':mission.as_dict(),'impact':impact,'review':review,'needs_recovery':mission.status!='completed'}
