# Parsec asset maintenance

Keep only the images listed in [the retention inventory](source/retained-images.v1.json). It records
each PNG and its hash. Runtime atlases and current editable frames are the production authority.
Do not keep generated galleries, screenshots, contact sheets, rejected candidates, or old atlas bundles
in this tree. Review decisions and source hashes remain in the asset register and JSON records.

## Required files

- Root atlas PNGs, coordinates, anchors, manifest, visual-review classifications, and SS13 source records.
- `prepared/parsec-*` and `prepared/ss13-objects`: current editable frames used to rebuild atlases.
- `source/regeneration-20261004`: shared character reference, raw sheets, exact PortalRabbit downloads,
  293 HD frames at 512×512, 293 pixel frames at 480×480, native strips, and a hashed generation manifest.
- `source/touchups/2026-09-09`: historical patches, immutable originals, and legacy-sheet replay input.
- `source/compositions`: selected scratch/yawn inputs retained for historical replay.
- `source/generated`: historical source artwork and the verified generation-reference crops.
- `source/references`: eight reviewed crops and their hash/crop records.
- `source/ss13-objects`, `source/ss13-effects`, and `audio`: accepted game-source extracts and sound cues.

Update the retained-image inventory when deliberately adding or replacing artwork. Preserve original
source hashes and update the patch/outline manifests whenever production pixels change.

Current eye colors are anatomical left yellow `#FBD436`, anatomical right pink `#FF3CC8`.
A left-facing profile shows pink; a right-facing profile shows yellow. Use the current transparent
`source/regeneration-20261004/reference.png` for further generations. PortalRabbit uses Grid Artist,
Ink sampling, 64 colors, and source-color preservation. Pixel masters preserve its native grid at
an exact 3× enlargement; runtime preparation uses a common scale per sequence and retains visible irises.
The 512px limit applies to individual frames, not packed sheets. September patches replay historical
pixels and no longer describe the current prepared frames.

## Temporary review exports

Create exports in a new empty directory outside the asset source tree. For example, replace the
placeholders below with a scratch destination; discard the generated output after review.

```text
python -m tools.parsec_assets.build_motion_review --input webapp/frontend/src/assets/parsec/prepared/parsec-core/core-idle-seated --output <new-empty-review-directory> --durations 2600,800,120,900 --reduced-motion-index 0 --title core-idle-seated
python -m tools.parsec_assets.build_character_reference --input webapp/frontend/src/assets/parsec/prepared --output <new-empty-human-edit-directory> --columns 8
```

Other clips use their authored timing and reduced-motion index from `manifest.v1.ts`. Human-edit exports
include their own cell map for `split_character_reference`; never reuse a map from an older frame set.

Build each atlas from its corresponding `prepared/<atlas>` directory with `tools/parsec_assets/build_atlas.py`.
Keep the SS13 extraction, source-hash, pixel-replay, and production validation checks intact. Verify with
`python -m pytest tools/parsec_assets -q -p no:cacheprovider` after asset changes.
