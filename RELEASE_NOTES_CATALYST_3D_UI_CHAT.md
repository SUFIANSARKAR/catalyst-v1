# Catalyst Major Step — 3D Avatar + Interface + Chat

## Scope

This build is the next working baseline after `Catalyst-Major-Step-Avatar-UI-Chat-v1`.
It adds a real VRM 1.0 alpha body and hardens the avatar, appearance, UI, chat and Live Talk surfaces.

## Delivered

- Real `frontend/assets/catalyst/catalyst.vrm` asset.
- VRM 1.0 humanoid mapping and spring-bone metadata.
- Runtime wardrobe profiles: signature, lounge, focus, night.
- Avatar state bridge for idle/listening/thinking/speaking/success/error/away.
- Blink, gaze, head-motion, mouth-motion and speech-level runtime controls.
- Unified avatar canvas that moves between Chat and Live Talk.
- Reworked Catalyst shell, navigation, chat surface and options/settings flows.
- Appearance picker wired to both 3D wardrobe state and 2D fallback images.
- Robust SSE chat parsing with chunk-boundary buffering.
- Chat streaming now uses a raw streaming `fetch` path instead of consuming the response through the JSON API helper.
- Safe browser-storage wrappers for restricted/private document contexts.
- Recent chats, projects, memory, missions and library surfaces remain connected to existing backend endpoints.

## Verification

- Python test suite: 182 passed, 1 skipped.
- JavaScript syntax checks: pass.
- HTML duplicate-ID audit: 0 duplicates.
- VRM GLB structure: valid glTF 2.0 container.
- `VRMC_vrm` spec version: 1.0.
- `VRMC_springBone` spec version: 1.0.
- Installed body: 109 glTF nodes, 78 meshes, 23 humanoid mappings, 1 weighted skin with 29 joints, plus VRM expression presets/custom expressions.
- Catalyst model metadata name: `Catalyst`.
- Avatar API/asset endpoints: verified with FastAPI test client.
- Inline browser UI harness: Chat, appearance, streaming response, settings, Live Talk navigation and avatar-canvas remount all passed with no page errors.

## Known limitation

The included VRM is a real engineered alpha body rather than a photoreal production sculpt. Its runtime contract is deliberately stable so a later art pass can replace mesh/materials without changing Catalyst's UI/API/avatar-control architecture.

The full Chromium browser could not navigate to the local server in the current execution environment because the environment browser policy blocks that navigation. The inline browser harness therefore validates DOM/UI behavior separately from the live network-serving process.
