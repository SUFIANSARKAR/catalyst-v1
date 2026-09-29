# Catalyst Catalyst Alpha Upgrade

## Upgrade focus

This release moves Catalyst from a capable control plane toward a more coherent Catalyst-style experience. Catalyst remains a **female AI** with her own identity and voice profile.

## Changes in this build

- Added two idempotent, pinned cognitive identity anchors at runtime startup:
  - Catalyst is a female artificial intelligence.
  - Catalyst's long-term mission is to become a Catalyst-level personal AI.
- Added the operating loop to the system constitution:
  - understand intent
  - recall durable context
  - plan
  - request approval when needed
  - act
  - verify
  - report
  - remember the useful outcome
- Applied the identity bootstrap to both the standalone runtime and the FastAPI server runtime.
- Updated the holographic command deck to present Catalyst as a persistent female command intelligence.
- Added an **Anchor identity** quick action for explicitly reinforcing the durable identity goal.
- Updated the memory panel to communicate that permanent cognitive memory survives restarts when `catalyst_data/` is persistent.
- Added regression coverage for identity-anchor persistence across database reopen.

## Verification

- 168 tests passed
- 1 test skipped
- Python compilation passed
- Permanent-memory reopen smoke test passed
- FastAPI import passed with 223 routes

## Persistence requirement

For permanent memory in deployment, persist the `catalyst_data/` directory (or configure `CATALYST_MIND_PATH` and `CATALYST_MEMORY_PATH` to durable storage). Back up this directory before upgrades. Catalyst's explicit forget operation remains available for user control.

## Next Catalyst milestones

- Streaming voice with interruption and wake-word support
- Unified multimodal context from files, screen, browser, and devices
- Proactive suggestions based on deadlines, unfinished missions, and user-approved routines
- Memory correction, conflict resolution, export, and encrypted backups
- Scenario-based Catalyst reliability benchmark with latency and verification metrics
