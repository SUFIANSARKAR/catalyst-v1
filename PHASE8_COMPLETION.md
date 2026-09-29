# Catalyst Phase 8 — Avatar + Presence + Interface Completion

This build consolidates the eight requested phases into one working baseline.

## Phase 1 — Avatar visual foundation
- `frontend/assets/catalyst/catalyst.vrm` is installed as the runtime body.
- VRM 1.0 metadata and material palette were refined to the Catalyst visual direction.
- The body is a segmented weighted-skin humanoid alpha with 23 humanoid bone mappings and a VRM 1.0 skin.
- Current VRM asset validation: 109 glTF nodes, 78 meshes, 1 skin, 29 skin joints, VRMC_vrm 1.0 + VRMC_springBone 1.0.
- Four wardrobe profiles are supported: Signature, Lounge, Focus, Night.

## Phase 2 — Expressive avatar director
- `frontend/catalyst-vrm.js` now owns state-to-body behavior.
- Idle breathing, gaze, blinking, head movement, shoulder/arm gestures and speaking motion are driven from Catalyst state.
- Expressions include neutral, warm/happy, curious, thinking, focused/serious, surprised, concerned, playful and sad.
- Speech audio energy drives runtime mouth movement.
- VRM expression presets now include blink/viseme/emotion bindings; custom Catalyst semantic expressions are registered for runtime control.
- Reduced-motion mode is supported.

## Phase 3 — Live Talk
- Continuous browser speech recognition remains available as the primary browser path.
- Voice playback interrupts and resumes listening cleanly.
- Stop-voice control is available.
- Realtime audio session/WebSocket authorization now uses the normal `voice` capability instead of requiring the privileged `audio` capability.
- Backend avatar state moves through listening/thinking/speaking states for realtime operations.

## Phase 4 — Chat experience
- Streaming SSE is handled with persistent chunk buffering.
- High-level activity labels are shown without exposing hidden chain-of-thought.
- Session restoration uses persistent session IDs.
- Attachments remain connected to the outgoing chat request.
- Voice playback, clear/new chat and keyboard shortcuts are integrated.

## Phase 5 — Appearance system
- Appearance changes control actual 3D wardrobe geometry when the VRM is live.
- Reference images remain a visual fallback only.
- Appearance is persisted through the UI preference store.
- Catalyst identity is intentionally separated from wardrobe selection.

## Phase 6 — Avatar Studio
- New Avatar Studio modal controls:
  - wardrobe
  - facial expression
  - motion level
  - gesture style
  - reset/restore behavior
- Chat and Live Talk use the same underlying avatar runtime.

## Phase 7 — Continuity/UI polish
- Persistent UI preferences are stored atomically in `catalyst_data/ui_preferences.json`.
- Options cover voice, continuity, memory preference, activity visibility, action confirmations, theme, motion and compact layout.
- Projects, Memory, Missions and Library retain connected Catalyst surfaces.
- Service-worker cache version was bumped to prevent stale UI assets after deployment.

## Phase 8 — Verification and hardening
- Added `/api/avatar/health`, `/api/avatar/profiles`, `/api/preferences` and `/api/avatar/motion`.
- Added regression tests for the VRM body contract, avatar state, appearance profiles, preference persistence, node naming and wardrobe compatibility.
- Verified model integrity as a valid GLB carrying `VRMC_vrm` 1.0 and `VRMC_springBone`.
- The browser UI still keeps a reference fallback if the remote Three/VRM runtime cannot be loaded.

## Known boundary
The installed Catalyst body is a real VRM 1.0 weighted-skin humanoid alpha. It is intentionally lightweight and segmented rather than a dense production-grade character sculpt. The runtime, UI, Chat and Live Talk layers are now compatible with a higher-fidelity replacement model without changing their public APIs.
