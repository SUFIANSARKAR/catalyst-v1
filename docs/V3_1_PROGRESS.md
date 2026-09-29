# Catalyst v3.2.0 — Remaining platform work

Catalyst v3.1 focuses on the last high-value platform gaps: durable memory quality, governed autonomy, provider flexibility, and operator control.

## Completed in this increment

| Area | Upgrade |
| --- | --- |
| Memory | Importance weighting, recency-aware recall, duplicate consolidation, archive/get APIs |
| Autonomy | Pause/cancel/resume mission lifecycle and bounded mission plans |
| Reliability | Persisted mission state is checked between steps so control changes take effect before the next action |
| Provider architecture | Provider-specific `options` now survive profile save/load and API updates |
| UX | Mission controls and memory consolidation controls added to the product cockpit |

## New environment controls

```text
CATALYST_MEMORY_AUTO_CONSOLIDATE=false
CATALYST_MEMORY_CONSOLIDATE_THRESHOLD=500
CATALYST_MISSION_MAX_STEPS=24
```

## Remaining frontier work

The next highest-value work is deeper multimodal/audio support, stronger semantic memory consolidation, external identity/SSO, and higher-order reliability evaluation across long autonomous runs. These should be added as explicit provider-backed capabilities rather than mocked into the core.
