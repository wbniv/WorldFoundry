# `wf-rooms-counters` cleanup investigation

**Inspected and removed:** 2026-10-30. **Former checkout:** `/home/will/wf-rooms-counters` (2.5 GB, detached at `7eb19401a7ce2f2d109af8ed9882fd817653e758`). The inventory below records its state before removal.

## Finding

The detached commit is not an ancestor of `2026-new-level`, but its **exact patch is already on that branch** as `d2985149` (same seven files, same stable patch ID `95987c2702771433485727005a3f7334098ac72c`; `d2985149` is an ancestor of current `HEAD`). The original is also referenced by `origin/e3-phase0-counters`. There is no engine change in this worktree that needs porting before cleanup.

The commit adds `--frame-profile` upload/cull counters and one-time mesh and room statistics. It does not contain a measurement run. The worktree has no modified tracked files and no untracked diagnostic directory or profile result.

## Worktree-only inventory

| Item | Size | Evidence or reuse value | Cleanup disposition |
| --- | ---: | --- | --- |
| `build-rel/build.log` | 336 KB | Only worktree-local build record. Ends with `Built target wf_game` and `exit=0`; no `mesh-stats`, `room-stats`, or frame-profile measurements. SHA-256 `0c3e557ced818870bda67965f7fe622d596d8af26dff0bfe7cefbb02fe40f529`. | **Optional archive** if the exact October 8 compiler transcript matters. This report preserves its result; it is not needed to retain the code or reproduce a build. |
| `build-rel/` | 167 MB | CMake cache, objects, static libraries, Rust build intermediates, and the log above. Generated from the detached source. | Discard after deciding whether to archive `build.log`. |
| `engine/wf_game` | 9.8 MB | Built executable, SHA-256 `0916ff13af2ccb11f56730ec6049aae6371bf00d7cbb8cea07e835f2a674a918`. No captured run accompanies it. | Discard; rebuild from the integrated commit when needed. |
| `wftools/prep/prep` | 144 KB | Generated tool executable. | Discard; rebuildable. |
| `engine/vendor/jolt-physics-5.5.0/` | 36 MB | Ignored vendored dependency tree, not an experiment result. | Discard with the worktree; reacquire through the normal build setup if needed. |
| Seven untracked `wfsource/source/oas/*.ht` files: `font`, `init`, `meter`, `movie`, `pole`, `template`, `test` | 28 KB total | Byte-for-byte identical to the seven files currently present in the main checkout (`cmp` passed for each). | Discard; no unique source or diagnostic data. |

Git reports 1,973 ignored files: 851 under `build-rel`, 1,121 under `engine`, and one under `wftools`. The ignored items above account for those groups. The rest of the 2.5 GB is the ordinary tracked checkout.

## Diagnostics decision

**Nothing from this detached worktree must be retained before cleanup.** Its `docs/diagnostics/` contains no files created after the October 8 checkout and no untracked outputs. No experiment-specific room/counter captures or runtime profile logs were found there or in `build-rel/build.log`. Existing tracked diagnostics remain in Git independently of this worktree.

If a before/after performance claim is wanted, run and save a new `--frame-profile` session from the current branch; this checkout supplied code and a successful compile, not measured counter values.

## Cleanup result

Will approved removal without archiving the optional build log. `git worktree remove --force /home/will/wf-rooms-counters` completed successfully. A subsequent check found the path absent and no `wf-rooms-counters` entry in `git worktree list --porcelain`. The main checkout's unrelated working-tree changes were left untouched. The integrated `d2985149` commit remains on `2026-new-level`.
