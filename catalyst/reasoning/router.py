from __future__ import annotations

from .engine import ReasoningEngine, ReasoningMemory, ReasoningPlan


class ReasoningRouter:
    """Compatibility facade over the new evidence-aware ReasoningEngine."""

    def __init__(self, memory: ReasoningMemory | None = None, model=None):
        self.engine = ReasoningEngine(memory=memory, model=model)

    def choose(self, task: str) -> ReasoningPlan:
        return self.engine.choose(task)

    def analyze(self, task: str, context=None):
        return self.engine.start(task, context=context)

    def recent(self, limit: int = 20):
        return self.engine.memory.recent(limit)


__all__ = ["ReasoningRouter", "ReasoningPlan"]
