# Catalyst v4 Monster — Engineering Intelligence

Catalyst v4 is no longer measured primarily by the number of subsystems in the repository. The core objective is reliable completion of real engineering work.

## Control architecture

```text
Objective
  -> Repository reconnaissance
  -> Evidence retrieval
  -> Planning / hypothesis
  -> Tool-driven execution
  -> Sandbox verification
  -> Failure diagnosis
  -> Re-plan / repair
  -> Regression verification
  -> Evidence-backed report
```

The model is the reasoning layer. The engineering toolbox is the grounded action layer. Catalyst policy/approval remains authoritative over mutations and execution.

## Native engineering toolbox

- `repo_map` — repository inventory and test surface
- `list_files` — bounded tree navigation
- `search_code` — literal/regex source search
- `read_file` — bounded line-numbered source inspection
- `git_status` / `git_diff` — version-control evidence
- `create_checkpoint` — reversible pre-change snapshot
- `write_file` / `apply_patch` — controlled mutation
- `run_command` — sandboxed execution
- `run_tests` — test discovery and execution

Read-only tools can be used during investigation. Mutation and command tools require execution approval.

## Model architecture

Catalyst accepts a cloud model through the existing provider gateway and an optional OpenAI-compatible local inference endpoint. The local model is a specialist/fallback, not a hard replacement for stronger cloud reasoning.

This keeps Catalyst provider-agnostic and lets a future machine with stronger local compute be attached without redesigning the agent.

## Completion semantics

Catalyst must not report success solely because a model produced a confident response. A completed engineering mission should include concrete tool evidence, execution/test results when execution was authorized, and a final diff/review story.

## Benchmark direction

The engineering benchmark should evolve toward real repository tasks: bug repair, feature implementation, regression repair, unfamiliar-repository comprehension, and evidence-backed code review. Architecture claims are not substitutes for task results.
