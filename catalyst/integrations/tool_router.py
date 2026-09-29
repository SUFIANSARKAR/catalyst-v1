from __future__ import annotations
import math, re
from collections import Counter
from typing import Any, Callable, Iterable


class DynamicToolRouter:
    """Catalyst-native top-K tool router.

    ToolBench's useful idea is preserved: build a compact searchable document for
    each tool/API and select only the most relevant candidates before reasoning.
    The default path is dependency-free lexical scoring; callers may inject an
    embedding function that maps text -> vector for semantic retrieval.
    """
    def __init__(self, top_k: int = 8, embedder: Callable[[list[str]], list[list[float]]] | None = None):
        self.top_k = max(1, int(top_k))
        self.embedder = embedder
        self._tools: list[dict[str, Any]] = []
        self._documents: list[str] = []
        self._embeddings: list[list[float]] | None = None

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r'[a-zA-Z0-9_:-]+', text.lower())

    @staticmethod
    def _schema_document(tool: dict[str, Any]) -> str:
        fn = tool.get('function', tool)
        parts = [
            str(fn.get('name', '')),
            str(fn.get('description', '')),
            str(fn.get('category', tool.get('category', ''))),
        ]
        params = fn.get('parameters') or {}
        if isinstance(params, dict):
            props = params.get('properties') or {}
            required = params.get('required') or []
            parts.append('required_params ' + ' '.join(map(str, required)))
            for name, spec in props.items() if isinstance(props, dict) else []:
                parts.append(str(name))
                if isinstance(spec, dict):
                    parts.append(str(spec.get('description', '')))
                    parts.append(str(spec.get('type', '')))
        # Preserve externally supplied ToolBench-style metadata when present.
        for key in ('api_name', 'api_description', 'required_parameters', 'optional_parameters', 'return_schema'):
            if key in tool:
                parts.append(str(tool.get(key, '')))
        return ' '.join(p for p in parts if p).strip()

    def index(self, schemas: Iterable[dict[str, Any]]) -> None:
        self._tools = [dict(s) for s in schemas]
        self._documents = [self._schema_document(s) for s in self._tools]
        self._embeddings = self.embedder(self._documents) if self.embedder and self._documents else None

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    @staticmethod
    def _lexical(query: str, document: str) -> float:
        q = Counter(DynamicToolRouter._tokens(query)); t = Counter(DynamicToolRouter._tokens(document))
        if not q or not t:
            return 0.0
        dot = sum(q[x] * t[x] for x in q)
        nq = math.sqrt(sum(v * v for v in q.values())); nt = math.sqrt(sum(v * v for v in t.values()))
        return dot / (nq * nt) if nq and nt else 0.0

    def rank(self, intent: str, excluded_tools: dict[str, set[str]] | None = None) -> list[dict[str, Any]]:
        excluded_tools = excluded_tools or {}
        query_embedding = None
        if self.embedder:
            try:
                values = self.embedder([intent])
                query_embedding = values[0] if values else None
            except Exception:
                query_embedding = None
        scored: list[tuple[float, dict[str, Any]]] = []
        for i, tool in enumerate(self._tools):
            fn = tool.get('function', tool)
            category = str(fn.get('category', tool.get('category', '')))
            name = str(fn.get('name', tool.get('name', '')))
            if category in excluded_tools and name in excluded_tools[category]:
                continue
            score = self._cosine(query_embedding, self._embeddings[i]) if query_embedding is not None and self._embeddings else self._lexical(intent, self._documents[i])
            scored.append((score, fn))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:self.top_k]]
