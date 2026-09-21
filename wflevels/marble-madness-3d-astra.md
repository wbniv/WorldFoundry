# Astra Marble Madness — bundled Practice course

Astra is **level 6** in `wfsource/source/game/cd.iff`. From this checkout, launch it with `task run-marble-3d-astra` or `task run -- 6`. Arrows accelerate; countersteer to brake; Space restarts the race.

`marble-madness-3d-astra-standalone.iff` is the bundle input. It is the verified Practice build from the independent `marble-madness-3d-astra` branch, originally committed in `13c96e2e`. Authoring sources, source provenance, geometry/runtime checks and fidelity notes are under `wflevels/marble-madness-3d/` on that branch. This specifically identifies the Astra attempt; it does not incorporate the separate Claude/Fable attempt.

The packaged static collision surface is derived from the arcade terrain sampler. Artwork, perspective camera, motion tuning, score, respawn and frozen dynamic terrain remain approximations. The other five arcade courses are not included.

Run `task build-cd-iff` to repack the checked-in level inputs. The six existing indices and SMB's default boot are retained. To refresh this input after authoring changes, rebuild the standalone in the Astra worktree, copy it to this checkout as `wflevels/marble-madness-3d-astra-standalone.iff`, and repack.

[Integration verification and captures](../docs/plans/2026-09-21-add-marble-astra-to-cd-iff.md).
