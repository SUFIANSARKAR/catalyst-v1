# Catalyst 3D Avatar — Alpha 1

This build contains the first real Catalyst 3D body in VRM 1.0 form at `frontend/assets/catalyst/catalyst.vrm`.

## What is included

- A custom procedural 3D Catalyst body with face, hair, hands, arms, legs and shoes.
- A humanoid bone hierarchy mapped to the required VRM 1.0 humanoid bones.
- Current asset footprint: 109 glTF nodes, 78 meshes, 23 humanoid mappings, with spring-bone metadata for three hair chains.
- Separate 3D wardrobe geometry for Signature, Lounge, Focus and Night appearances.
- Eye, iris, pupil, brow and mouth nodes named for the Catalyst runtime.
- Hair root/tip bones with a `VRMC_springBone` definition.
- VRM metadata identifying the body as Catalyst Alpha 3D 1.0.
- Browser runtime support for gaze, blinking, speech mouth movement and wardrobe switching.

## Design intent

The 3D body is an engineered alpha asset, not a claim that the current geometry has the same photoreal fidelity as the reference renders. The reference images remain the appearance target for later mesh/material refinement. The important milestone here is that Catalyst now has an actual VRM body that can be loaded and animated by the application rather than a PNG-only placeholder.

## Runtime contract

The frontend loads `/assets/catalyst/catalyst.vrm` with `@pixiv/three-vrm` and uses the backend avatar state API to drive the visible state. The same canvas is moved between the main Chat presence area and Live Talk so the user sees one continuous Catalyst identity instead of two independent avatars.
