# Catalyst v4 — Monster Arc

Catalyst v4 is a **complete high-level engineering intelligence layer**, not a single feature release.

## Mission

Turn Catalyst from a capability collection into a personal engineering executive that can understand repositories, choose models/specialists, plan work, use tools, execute inside governed sandboxes, verify results, recover from failure, and remember engineering evidence.

## Architecture

`User objective → Unified Mind → Engineering Executive → Model Council → Repository Intelligence → Tool/Agent Router → Execution Fabric → Verification → Replan/Recover → Evidence → Persistent Mind`

### Model Council

- Frontier/cloud models for difficult reasoning.
- Optional local 7B–8B-class quantized model through an OpenAI-compatible local endpoint.
- Coding specialists: SWE-agent, OpenHands, Full Self Coding, TC Engineering AI.
- Reviewer/verifier roles remain separate from the primary executor where useful.

### Engineering Intelligence

v4 adds deterministic repository reconnaissance (`CodebaseIntelligence`) and a governed coding-agent executive (`EngineeringAgent`). The system creates evidence-backed plans before edits and keeps execution separate from planning.

### Heavy tools

MCP, Browser Use, E2B, Docker, ToolBench patterns, PhysicsNeMo, PyVista, research, device bridges, and specialist agents remain modular capabilities behind Catalyst's routing/policy plane.

### Safety / control

No external repository is allowed to become Catalyst's authority. Edits and consequential execution remain approval/policy controlled. Self-improvement remains proposal → isolated snapshot → tests → evaluation → promotion/rollback.

## Codespaces profile

For a 4-core / 16 GB RAM / 32 GB storage development VM, use a small quantized local model as a **fast local specialist**, not the sole brain. Keep frontier reasoning and heavyweight specialist execution provider-configurable.

## Benchmark

`catalyst.benchmarks.EngineeringBenchmark` exists to measure actual engineering evidence rather than number of modules or routes.
