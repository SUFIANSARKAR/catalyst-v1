# Catalyst v3.5.0 — Catalyst Bridge D–F

## Phase D — realtime voice transport
- Added bounded realtime audio sessions with WebSocket chunk transport.
- Finalization sends the assembled recording through the existing provider-backed transcription engine.
- Provider metadata/health supports optional provider-specific realtime endpoint configuration without assuming undocumented vendor message formats.

## Phase E — evidence-first research
- Added evidence reports with source hashes, query-relevant snippets, claim records and conservative conflict signals.
- Reuses the existing public-web safety/SSRF checks and source collector.
- Does not claim semantic contradiction resolution; signals are heuristic and are evidence for later model reasoning.

## Phase F — safe self-improvement lab
- Added isolated experiments created from a clean source snapshot.
- Optional unified patches are applied only inside the sandbox.
- Benchmarks/tests run before promotion.
- Production promotion and rollback are explicit creator/admin actions with a confirmation gate and backup.
- No automatic self-overwrite is permitted.

## Scope boundary
External realtime vendors still require real provider credentials/endpoints. D provides a real transport/session path and provider-backed finalization, not a fabricated universal vendor protocol.
