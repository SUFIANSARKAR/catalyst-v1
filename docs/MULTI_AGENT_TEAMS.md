# Catalyst Multi-Agent Teams

Catalyst v3.2.4 adds a dependency-free multi-agent coordination layer inspired by useful AutoGen AgentChat mechanisms.

## Modes
- `selector`: chooses the least-used/relevant member and keeps a bounded team loop.
- `round_robin`: deterministic sequential rotation.
- `swarm`: explicit `HANDOFF:<member>` delegation.
- `graph`: directed edges with optional content conditions.

Catalyst remains the authority for model routing, memory, tools, policy, approvals, provenance, and execution. AutoGen is used as an architectural reference; it is not bundled wholesale.

API: `POST /api/teams/run` with `{objective, mode, members, max_turns, edges}`.
