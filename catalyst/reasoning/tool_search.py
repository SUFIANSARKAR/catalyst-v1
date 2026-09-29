from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class ToolSearchNode:
    """One bounded candidate in the tool/action search tree."""
    actions: list[dict[str, Any]] = field(default_factory=list)
    state: Any = None
    score: float = 0.0
    terminal: bool = False
    valid: bool = False
    reason: str = ''


class BoundedToolSearch:
    """Catalyst-native DFSDT-inspired search for multi-step tool plans.

    This deliberately does not execute tools. The caller supplies candidate
    generation, state transition and validation callbacks. Catalyst's Mission
    Control / policy layer remains the authoritative executor.
    """
    def __init__(self, max_depth: int = 6, max_nodes: int = 64, branch_limit: int = 3):
        self.max_depth = max(1, min(int(max_depth), 32))
        self.max_nodes = max(1, min(int(max_nodes), 512))
        self.branch_limit = max(1, min(int(branch_limit), 16))
        self.nodes_expanded = 0
        self.trace: list[dict[str, Any]] = []

    def search(
        self,
        initial_state: Any,
        candidates: Callable[[Any, int], Iterable[dict[str, Any]]],
        transition: Callable[[Any, dict[str, Any]], Any],
        validate: Callable[[Any, list[dict[str, Any]]], bool],
        score: Callable[[Any, list[dict[str, Any]]], float] | None = None,
    ) -> ToolSearchNode | None:
        self.nodes_expanded = 0
        self.trace = []
        best: ToolSearchNode | None = None

        def dfs(state: Any, actions: list[dict[str, Any]], depth: int) -> ToolSearchNode | None:
            nonlocal best
            if self.nodes_expanded >= self.max_nodes:
                return None
            self.nodes_expanded += 1
            current_score = float(score(state, actions) if score else len(actions))
            if best is None or current_score > best.score:
                best = ToolSearchNode(list(actions), state, current_score)
            if validate(state, actions):
                node = ToolSearchNode(list(actions), state, current_score, terminal=True, valid=True, reason='validated')
                self.trace.append({'event': 'terminal', 'depth': depth, 'score': current_score, 'actions': list(actions)})
                return node
            if depth >= self.max_depth:
                self.trace.append({'event': 'depth_limit', 'depth': depth, 'actions': list(actions)})
                return None

            raw = list(candidates(state, depth))[:self.branch_limit]
            # Prefer higher candidate priority without imposing a model/runtime.
            raw.sort(key=lambda x: float(x.get('priority', 0.0)), reverse=True)
            for candidate in raw:
                try:
                    next_state = transition(state, candidate)
                except Exception as exc:
                    self.trace.append({'event': 'transition_error', 'depth': depth, 'error': str(exc), 'candidate': candidate})
                    continue
                self.trace.append({'event': 'expand', 'depth': depth, 'candidate': candidate})
                result = dfs(next_state, actions + [candidate], depth + 1)
                if result and result.valid:
                    return result
            self.trace.append({'event': 'backtrack', 'depth': depth, 'actions': list(actions)})
            return None

        result = dfs(initial_state, [], 0)
        return result or best
