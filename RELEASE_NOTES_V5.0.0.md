# Catalyst v5.0.0 — Apex Intelligence Arc

Catalyst v5.0 is the next major arc after the v4.5 Monster runtime. The focus is system integration and reasoning quality rather than adding disconnected features.

## Major arc

### Apex Unified Mission Runtime
- Added `catalyst.apex.ApexRuntime` and a top-level mission contract.
- Unifies objective classification, capability selection, bounded planning and governance metadata across Catalyst subsystems.
- Preserves the existing execution boundaries rather than inventing a second executor.

### Reasoning v2 — Adaptive Evidence Mind
- Replaced the old keyword-only router implementation with a structured evidence-aware reasoning engine.
- Added objective classification across engineering, research, data, planning, creative, computer-use, device and general work.
- Added explicit risk and uncertainty estimation.
- Added hypothesis/evidence tracking, contradiction detection and durable reasoning traces.
- Added decision scoring using evidence quality, expected value, cost, risk and uncertainty.
- Added optional model-assisted plan refinement with strict dependency and schema checks plus deterministic fallback.
- Added structural claim verification and reflection/replan analysis.
- Preserved the v4.x `ReasoningRouter.choose()` and `ReasoningPlan.agent` compatibility surface.

### Core Mind Integration
- Every normal response now creates a bounded reasoning trace.
- Tool outcomes become evidence or negative evidence in that trace.
- Final output is checked against available evidence before being marked verified.
- Existing memory, mind, cognitive loop, sessions, tools, approvals and audits remain intact.

### Release Hardening
- Release is packaged without live runtime databases, WAL/SHM files, API keys or `secrets.json`.
- Runtime state remains external and persistent when Catalyst is deployed.

## Verification

- 146 tests passed, 1 skipped
- Python bytecode compilation passed
- release verification passed
- clean source-only archive generated
