# Integrating the phase 3 worktree

The source change is isolated on `aquarium/tiger-barbs-phase3`, based on `10310efe`. Main-checkout species movement work began concurrently; its engine/controller/other-tank changes are outside this branch and outside the matched native-library profile set.

Merge the aquarium generator, `tiger_barb.py`, benchmark tooling, tests and plan evidence. If generated asset files conflict, regenerate the first tank with `task --force aquarium-level` from the combined sources, then regenerate `aquarium-menu-cd.iff` using the current seven-tank manifest and the other task’s current standalone levels. Do not overwrite the other tank standalones with this branch’s copies. Rebuild Android against the combined engine if the species work changes deformation syscalls or native rendering.

Phase 2 remains selectable with `AQUARIUM_FOLLOWER_ASSET=barb_mesh`; the normal default is `barb_refined`. Keep five behavior updates and the existing continuity/turn/startle fixes. The model adds no actors, materials, mailbox cells or new native animation code.

The asset-only comparison APKs deliberately reuse the native libraries from the pre-test installed APK. Those profiles isolate the mesh change. They do not measure any concurrent main-checkout engine changes; rerun the relevant comparisons after integration if those changes affect the first tank or renderer.

## Integration completed (2026-10-03)

Merged phase 3 (`24fdef05`), species movement (`f6248fff`), and the upstream diagnostic FPS mailbox changes into `2026-new-level`. Regenerated the seven-entry menu bundle from the combined standalones, preserving all six updated species. Both Android release ABIs built successfully.

Combined APK SHA-256: `02c841541d9bf44ab652d606d559b274cce2ddd81cd40f398cb36bb43830390f`. [Build receipt](integration-device/build.json), [six-species device checks](integration-device/checks.json), and [selector/tiger-barb lifecycle checks](integration-device/lifecycle.json) record the integrated package. Reviewed the tank and returned-selector screenshots: phase 3 barbs render and the seven-entry menu remains correct. Injected device inputs establish movement and navigation; physical remote chord/repeat validation remains pending in the separate controls plan.

Validation: 66 species/menu regressions passed; 70 phase 3/menu/startle checks passed. The package check initially inspected an old debug APK; the tests now allow `WF_TEST_ANDROID_BUILD_TYPE=release` and verify the actual banner bytes despite release resource renaming. All 14 Android checks passed against the rebuilt release.

Schooling optimization is measured separately with the combined native libraries, preserving the 29 followers, five behavior updates per frame and phase 3 geometry.
