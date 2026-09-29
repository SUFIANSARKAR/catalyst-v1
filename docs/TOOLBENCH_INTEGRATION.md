# ToolBench Integration — v3.17.0

## What was taken from ToolBench

ToolBench is retained as a research source, not as Catalyst's runtime architecture. The useful mechanisms found in the supplied `ToolBench-master.zip` are:

1. **Semantic tool/API retrieval** — build a compact searchable representation from tool category, name, API name, description, parameters, and return schema, then retrieve only the top candidates relevant to the current intent.
2. **Depth-first tree search / DFSDT pattern** — explore alternative multi-step action chains, validate outcomes, and backtrack when a branch cannot reach a valid result.
3. **Tool-use evaluation traces** — preserve search/branch outcomes as structured evidence that can later feed Catalyst's evaluation and learning systems.

## Native Catalyst implementation

### `catalyst.integrations.tool_router.DynamicToolRouter`

The existing dependency-free lexical router now supports:

- schema-aware indexing of function metadata and parameter descriptions;
- optional injected embedding functions for semantic vector retrieval;
- cached corpus embeddings;
- cosine ranking when embeddings are available;
- lexical fallback when an embedding provider is unavailable;
- exclusion filters for tool/category combinations.

This keeps provider choice outside the Catalyst core. An embedding service can be attached later without importing ToolBench or SentenceTransformers into the main runtime.

### `catalyst.reasoning.tool_search.BoundedToolSearch`

A Catalyst-native DFSDT-inspired search primitive provides:

- bounded maximum depth;
- bounded total node expansion;
- bounded branching factor;
- candidate priority ordering;
- explicit state transition callback;
- explicit validation callback;
- optional scoring callback;
- structured expand/backtrack/terminal trace.

The component **does not execute tools**. Mission Control, policy, approvals, and the existing execution plane remain authoritative.

## What was deliberately not imported

- ToolBench's full model-training stack;
- ToolLLaMA weights or training runtime;
- the historical RapidAPI corpus as a production dependency;
- ToolBench's custom research environment abstractions;
- unrestricted remote API execution;
- heavyweight embedding/training dependencies in Catalyst core.

The supplied research source archive is preserved at `vendor/sources/ToolBench-master.zip` for provenance and future selective extraction.

## Security constraints

Tool descriptions and tool output remain **data**, not instructions. Retrieval cannot grant a tool permission. Selection is advisory until the selected action passes Catalyst policy, approval, capability, execution, and verification boundaries.

Search depth, branch count, and total nodes are bounded to prevent unbounded recursive exploration.

## Verification

New tests in `tests/test_v317_toolbench_fusion.py` cover:

- optional embedding-backed tool retrieval;
- bounded DFS-style branch backtracking;
- node-expansion limits.

The full Catalyst test suite must still pass before promoting this release.
