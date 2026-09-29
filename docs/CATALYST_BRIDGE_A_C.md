# Catalyst 3.4.0 — Catalyst Bridge A–C

## Phase A — Perception + Computer Use
- Playwright browser actuator with bounded actions.
- Durable browser-session metadata in `catalyst_data/computer_sessions.db`.
- Screenshot + visible text + links + viewport observations.
- Policy blocks unsupported/destructive actions and enforces navigation allowlists.
- Computer-use execution requires explicit approval by default.
- Model planner emits one structured action at a time.

## Phase B — World Model + Advanced Memory
- Temporal SQLite knowledge graph; relation updates retain historical versions.
- Entity attributes merge instead of overwriting.
- Confidence/provenance attached to relations.
- Knowledge memory indexes into semantic memory when configured.
- Working, durable, semantic, procedural, event and world-memory paths remain separate but coordinated.

## Phase C — Long-Horizon Autonomy
- Mission steps honor declared dependencies.
- Each step records attempts and checkpoints before/after execution.
- Retry loops remain bounded.
- Dependency deadlocks become explicit mission failures instead of silent stalls.
- Long-horizon evaluator persists checkpoints and retry evidence.
- Computer-use can be represented as a mission step, while destructive execution remains approval-gated.

## Preservation rule
This release extends v3.3.0. Existing memory, missions, teams, agents, approvals, provenance, artifacts, research, media, audio, identity and provider abstractions were preserved.
