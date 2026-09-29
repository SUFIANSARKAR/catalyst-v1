# Catalyst VRM Body Build

## Current implementation

Catalyst now contains a real VRM 1.0 alpha body at `frontend/assets/catalyst/catalyst.vrm`.
The browser runtime uses Three.js + `@pixiv/three-vrm` and keeps the existing 2D references as a fallback.

### Runtime contract

- Model path: `frontend/assets/catalyst/catalyst.vrm`
- Model format: VRM 1.0
- State endpoint: `GET/POST /api/avatar/state`
- Appearance endpoint: `POST /api/avatar/appearance`
- Runtime information: `GET /api/avatar/manifest`
- Renderer: `frontend/catalyst-vrm.js`
- Backend state controller: `catalyst/avatar.py`

## Alpha body capabilities

The current alpha body provides:

1. VRM 1.0 humanoid mappings with core upper/lower-body bones.
2. Named facial parts used by Catalyst's runtime for blink, mouth activity and expression motion.
3. Hair spring-bone data for two hair chains.
4. Four wardrobe profiles represented inside the same model: signature, lounge, focus and night.
5. Runtime appearance switching without replacing Catalyst's identity or session state.
6. A web-optimized, self-contained asset that can be loaded directly by the existing frontend.

## Production refinement still possible

The alpha body is an engineered, low-complexity VRM character built to make the avatar system real and testable.
It is not a photoreal production sculpt. A later art pass can replace the mesh/materials while keeping the same
VRM runtime contract, humanoid naming, expressions and wardrobe interface.

## Installation

The packaged model is already installed at:

`frontend/assets/catalyst/catalyst.vrm`

The frontend automatically attempts to load it. When loaded successfully, the avatar runtime badge changes to
`VRM 1.0 · LIVE`; if loading fails, the existing 2D Catalyst reference image remains available.
