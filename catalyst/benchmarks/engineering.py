from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable
import time

@dataclass(frozen=True)
class EngineeringCase:
    id: str
    objective: str
    expected_signals: tuple[str,...] = ()

class EngineeringBenchmark:
    """Capability benchmark: measures evidence, not marketing claims."""
    CASES=(
        EngineeringCase('recon','Map an unfamiliar repository and identify its test surface',('repo_map','tests')),
        EngineeringCase('plan','Create a testable implementation plan for a code change',('steps','verification')),
        EngineeringCase('repair','Diagnose a failing test and propose a bounded repair loop',('failure','replan')),
        EngineeringCase('verify','Review a proposed patch and demand execution evidence',('evidence','verification')),
    )
    def run(self, handler: Callable[[EngineeringCase],dict]) -> dict:
        results=[]; started=time.time()
        for case in self.CASES:
            try:
                out=handler(case) or {}; text=str(out).lower()
                hits=sum(1 for s in case.expected_signals if s.lower() in text)
                results.append({'id':case.id,'passed':hits==len(case.expected_signals),'signals_hit':hits,'signals_expected':len(case.expected_signals),'output':out})
            except Exception as exc: results.append({'id':case.id,'passed':False,'error':str(exc)})
        passed=sum(bool(r.get('passed')) for r in results)
        return {'protocol':'catalyst.engineering-benchmark.v1','passed':passed,'total':len(results),'score':passed/len(results) if results else 0.0,'duration_s':round(time.time()-started,3),'results':results}
