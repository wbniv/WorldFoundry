# Discus palette selector

Add a **Palette** choice to the Discus level settings, with Wild Brown as the default and the twelve existing brown-family creative colorways as named choices. The choice applies to the whole school, including the player. For now it lasts only while the level is loaded, by design; saving it across launches and sharing it with the screensaver is a separate TODO. These are artistic colorways, not claims of distinct biological strains. Spotted and turquoise patterns are separate photographs and are not included in this palette-only selector.

## Implementation and engine boundary

1. Prepare one indexed fish image and twelve 256-entry color lookup tables reproducibly from the credited brown source and `wflevels/discus_asset/palettes.json`. Keep geometry, UVs and pixel indices invariant; retain attribution. Inspect a contact sheet before cooking them. The current Discus asset is cooked as 15-bit direct color; the indexed path must be verified through the actual textile, asset loader and target renderers.
2. Use a Discus-specific settings object with a live enumerated Palette field, default Wild Brown, alongside the existing global framerate setting. Its field is read by the level controller; the same schema and initial value must be present in the screensaver variant and both APK bundles.
3. Preserve indexed data through the cook and loading path. `textile-rs` currently converts normal PNG input to RGBA and then 16-bit direct color; simply passing it the indexed PNG loses the indices. Choose and document a representation that retains all 256 indices and associates the correct lookup tables with the fish material.
4. Add true lookup-table selection to the GL/GLES and Metal render paths, exposing the selection to the Discus controller. The existing two-color `TEXTURE_PALETTE` mode is a dark/light remap, not a 256-entry lookup. Keep the index data and mesh fixed when selecting a table; do not substitute RGB texture variants or duplicate fish actors. Will approved the indexed-palette and settings engine work on 2026‑11‑23.

The asset spike encodes each index across two channels of a single RGB555 atlas image (five high bits in red and three low bits in green; blue stays nonzero for the existing black-transparency rule). A test sends all 256 values through the actual textile PNG loader and recovers each one. Renderer integration must select nearest sampling for the encoded indices and apply the palette lookup before any desired color filtering; ordinary linear interpolation of encoded indices would select unrelated colors. The twelve RGB lookup tables are separate from this one invariant image. Confirm the complete packing, UV, backend and device paths before treating the encoding as final.

## Verification

- Confirm the cooked selector names and defaults, asset attribution, shared geometry and exact palette-index invariance. Test each selection, repeated changes and switching back; verify no pop, lost fish or orphaned actors.
- Run the cooked playable level and the screensaver on desktop before device installation. Verify held and released controls and the settings UI, including the choice after reopening it while the level is loaded.
- Rebuild the manifest-ordered menu and screensaver bundles and a matching two-ABI release APK. Verify bundle order, selection and default; freeze and hash the APK.
- Through the coordinator, test the phone and both Chromecasts where available, including the TV remote, phone touch, screensaver and steady-state memory/frame time. Compare each against the ten-fish baseline and report actual figures and any unavailable device; do not reduce art or population silently to meet an assumed budget.

## Status, 2026-11-23

The indexed image, twelve lookup tables, in-level selector and GL renderer are implemented. Desktop tests exercised the cooked playable level, changed Wild Brown to Warm Brown and back through its settings form, and ran the screensaver level with all nine resident fish moving. The release APK contains the rebuilt menu and screensaver bundles and both Android ABIs. The automated palette, asset, texture-loader and Metal shader-shape checks pass.

By design for now, the in-game choice lasts only while that level remains loaded, and the screensaver starts with Wild Brown; persistence and sharing are tracked in TODO. Desktop screenshots are in `docs/diagnostics/aquarium-discus-2026-11-22/palette-*.png` in the Discus worktree.

Android checks on 2026‑11‑23: cast1 job J‑d849223d631e opened Discus settings with the remote, selected Warm Brown and returned to the tank; Pixel job J‑f2f69372845c selected and applied Warm Brown through touch. Both logs report `INDEXED_PALETTE selection=1`. Cast2 readd J‑a701feba5742 failed because wireless debugging was not advertising, so its gameplay and held/released input remain unverified. Screensaver behavior on devices and steady-state performance comparisons also remain open.

Apple verification: Codemagic [macOS Metal build](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6b03d49b3bbd0ae5ae5fbc6b) passed, including rendered frames at palette indices 0 and 1. Codemagic [iOS simulator build](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6b0401c00350b71e602729a2) passed on iPhone 17 Pro and iPad Pro 13-inch (M5) simulators, launching the Discus level with palette 1, checking the selection in each log and capturing the running scene after background/resume. The simulator bundle includes the Aquarium's `wf_args.txt` VRAM dimensions. Captures and logs are alongside the desktop evidence. These are simulator tests, not physical iPhone or iPad tests. The isolated CI branch `ci/discus-indexed-metal` contains the test-specific workflow changes.
