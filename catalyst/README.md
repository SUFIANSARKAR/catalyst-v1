# Catalyst Avatar Reference Pack

## Upload this folder to the repository

Recommended destination:

`public/assets/catalyst/`

The most important file is:

`avatar_01.png`

Use it as the canonical visual identity reference.

Also keep:

- `catalyst_character_sheet.png`
- `catalyst_avatar_manifest.json`
- `avatar_02.png` through `avatar_08.png`
- `expression_*.png`

## Important architecture rule

The eight avatar images are NOT eight different Catalyst characters.

They are reference examples showing that Catalyst can have:

- different clothes
- different poses
- different environments
- different expressions

Catalyst should have one persistent identity while her appearance can change.

The final implementation should eventually support:

AI state -> pose/expression -> wardrobe/environment -> renderer

and:

TTS -> audio analysis/visemes -> mouth animation

The current PNGs are references. They should not be treated as the final animation technology.
