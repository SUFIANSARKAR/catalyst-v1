# Catalyst v4 Monster Arc — Engineering Intelligence Phase 2

This phase moves Catalyst from a capability collection toward a serious software-engineering agent.

## Major capabilities

- **Repository Intelligence:** deterministic architecture snapshots, dependency/coupling graph, symbol lookup, repository/test inventory.
- **Isolated Coding:** Git worktree creation/list/removal for mission branches instead of forcing complex edits into the primary working tree.
- **Engineering Test Strategy:** automatic framework detection and focused-plus-regression test planning.
- **Durable Engineering Runs:** SQLite-backed run records and evidence events for inspection and later recovery tooling.
- **Specialist Delegation:** the engineering executive can delegate bounded subtasks to registered Catalyst specialists through the existing agent manager.
- **Verification Gate:** an execution mission cannot be marked complete merely because a model produced a final message; deterministic verification evidence is required.
- **Unified Tool Plane:** all of these functions are exposed through the same governed engineering toolbox, preserving workspace boundaries and approval requirements.

## Operating loop

```text
Objective
  -> Recon / Architecture
  -> Locate evidence
  -> Plan
  -> Isolate worktree (when appropriate)
  -> Checkpoint
  -> Implement
  -> Execute / Test
  -> Inspect failure
  -> Repair / Replan
  -> Verify
  -> Final evidence
```

## Deliberate boundaries

Catalyst remains the executive/orchestrator. Existing external agent implementations remain specialists/providers, not duplicated monoliths. Mutating operations and commands remain approval-gated. The local model remains a replaceable specialist rather than a hard dependency.

## Quality bar

The primary benchmark is not module count. A serious mission should produce concrete evidence: changed files, relevant diff, deterministic test/build output, and unresolved risk notes when verification is incomplete.
