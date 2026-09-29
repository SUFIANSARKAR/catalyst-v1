# Catalyst Reasoning v2 — Adaptive Evidence Mind

Catalyst v5.0 replaces keyword-only reasoning selection with a structured reasoning contract.

## Core loop

`classify → assess risk/uncertainty → retrieve → plan → branch/search → act → observe → verify → reflect → replan/report`

## What is now real

- Multi-signal objective classification across engineering, research, data, planning, creative, computer-use and device work.
- Explicit risk and uncertainty estimation.
- Structured plans with bounded depth, verification requirements, recovery-aware steps and parallel lanes.
- Durable reasoning traces in `catalyst_data/reasoning.db`.
- Hypothesis/evidence reconciliation with supporting and contradicting evidence.
- Decision scoring that combines evidence quality, expected value, cost, risk and uncertainty.
- Optional model-assisted plan refinement with strict schema/dependency validation and deterministic fallback.
- Bounded tool/action search through the existing Catalyst-native search primitive.
- Structural claim verification that never upgrades unsupported output into fact.
- Reflection that identifies negative evidence, unresolved hypotheses and replan requirements.

## Trust boundary

Reasoning proposes and evaluates. Mission Control, policy, approvals, execution engines and device control remain authoritative for actual actions.

Catalyst never treats model-generated plans as proof that an action happened.
