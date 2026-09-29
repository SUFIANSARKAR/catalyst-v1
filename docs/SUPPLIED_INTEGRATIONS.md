# Supplied integration sources used by Catalyst 3.2.0

This document records what Catalyst harvested from the three supplied repositories and what was deliberately not copied.

## TC ENGINEERING AI Phase 7
Used from the supplied Phase-7 source:
- HTTP task creation at `/v1/tasks`.
- Persisted task status and task event history.
- SSE event stream shape.
- Approval endpoints `/approve` and `/reject` with an owner token and nonce.
- Health endpoint.

Catalyst implements an independent HTTP client around these contracts; it does not vendor the TC source tree.

## Full Self Coding
Used from the supplied source:
- Bun CLI entry point.
- `run --config` workflow.
- Repository analysis → task generation → parallel Docker task solving.
- Task reports and git-diff/report flow.
- Configurable Claude Code, Gemini CLI, Codex and Cursor paths.

Catalyst invokes the CLI through a controlled wrapper and normalizes its final result.

## OpenHands Cloud 0.55.0
The supplied repository identifies itself as the OpenHands Cloud deployment/Helm layer. It exposes deployment settings for the application, runtime API, object storage, integrations, Kubernetes and security configuration, but not the core OpenHands task API implementation.

Catalyst therefore uses deployment-aware configuration and health checks rather than fabricating an undocumented task protocol. A core-runtime repository can be integrated later without changing the Catalyst integration contract.
