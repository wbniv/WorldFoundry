# Integrating the phase 3 worktree

The source change is isolated on `aquarium/tiger-barbs-phase3`, based on `10310efe`. Main-checkout species movement work began concurrently; its engine/controller/other-tank changes are outside this branch and outside the matched native-library profile set.

Merge the aquarium generator, `tiger_barb.py`, benchmark tooling, tests and plan evidence. If generated asset files conflict, regenerate the first tank with `task --force aquarium-level` from the combined sources, then regenerate `aquarium-menu-cd.iff` using the current seven-tank manifest and the other task’s current standalone levels. Do not overwrite the other tank standalones with this branch’s copies. Rebuild Android against the combined engine if the species work changes deformation syscalls or native rendering.

Phase 2 remains selectable with `AQUARIUM_FOLLOWER_ASSET=barb_mesh`; the normal default is `barb_refined`. Keep five behavior updates and the existing continuity/turn/startle fixes. The model adds no actors, materials, mailbox cells or new native animation code.

The asset-only comparison APKs deliberately reuse the native libraries from the pre-test installed APK. Those profiles isolate the mesh change. They do not measure any concurrent main-checkout engine changes; rerun the relevant comparisons after integration if those changes affect the first tank or renderer.
