# Catalyst Phase 8 Release Notes

## Major step
Catalyst's avatar, interface, chat and voice surfaces were consolidated into one baseline.

### Avatar
- Real `catalyst.vrm` is installed in the application.
- VRM 1.0 body metadata, humanoid mappings and spring-bone data are validated.
- Runtime body control now includes expressions, blink, gaze, breathing, gestures, speech movement and wardrobe switching.

### Interface
- Presence-first chat layout.
- Live Talk page with continuous voice flow.
- Avatar Studio for look/expression/motion/gesture control.
- Options panel now covers voice, continuity, memory display, activity and action confirmation.
- Persistent UI preferences.

### Voice
- Normal chat voice playback and Live Talk share the same avatar state system.
- Realtime audio session endpoints use the non-privileged `voice` capability.
- Stop-voice/interrupt behavior is exposed in the UI.

### Hardening
- Chat SSE chunk buffering.
- Fallback-safe 3D loader with CDN timeout/fallback sources.
- Service-worker cache version bump.
- New Phase 8 regression tests.
