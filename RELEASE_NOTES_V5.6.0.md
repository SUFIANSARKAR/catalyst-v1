# Catalyst v5.6.0 — Holographic Command Deck

## Intelligence upgrades

- Provider profile options now safely pass supported model controls such as `reasoning_effort`, `top_p`, `response_format`, and `seed` without allowing a profile to override runtime messages, tools, model selection, or streaming mode.
- Added the read-only `/api/cognition/pulse` endpoint for low-cost command-deck polling. It composes the current provider, mind, cognitive objectives, reasoning history, Apex missions, and situational signals without invoking a model or dispatching work.
- Fixed the chat and streaming handlers so request-scoped auth and admin state are correctly passed into the orchestrator.

## Product upgrades

- Replaced the violet shell with a dark-blue holographic command deck: neural-core orb, orbital rings, scan-grid backdrop, intelligence rail, mission pulse, memory resonance search, model grid, and bounded reasoning brief controls.
- Added responsive mobile navigation, reduced-motion support, keyboard-friendly controls, PWA cache invalidation, and high-contrast focus states.
- Added a ready-to-open GitHub Codespaces configuration with Python 3.12, dependency bootstrap, forwarded port 8000, and VS Code Python tooling.

## Boundaries

Catalyst remains provider-agnostic. External API keys, devices, and model execution are still deployment-time configuration. The holographic UI is an interface treatment, not a claim of literal holographic hardware.
