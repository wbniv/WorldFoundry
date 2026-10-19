# Teleport audit integration review — 2026-10-09

Target: remote `2026-new-level` at `5b7404c3`.
Reviewed branch: `teleport-audit` at `cc151d2a`.
Review result: no blocking findings in the supported paths.

## Scope and evidence

- [x] Inspect position mailbox / transform notifications, safe update boundaries,
  inactive-source membership repair, permanent asset binding, camera snap,
  unload ordering and unloaded scale handling.
- [x] Confirm the pending merge's engine, CMake, tests and level fixtures are
  identical to the built and device-verified `teleport-audit` tree.
- [x] Preserve the target branch's classification of the original room-loading
  failure as an unsupported teleport design gap. Resolve the sole conflict in
  `docs/BUGS.md` by retaining that entry and the separate departing-room unbind
  entry, with a link to the subsequently added regression harness.
- [x] Rerun the complete native assertions suite: 24/24 passed for the final
  implementation. [Full test transcript](teleport-merge-tests.log).
- [x] Both Chromecast unloaded-actor jobs passed 117/114 intervals and nine full
  cycles each, including the first never-loaded case; cleanup verified.
- [x] Preserve the main checkout's 129 tracked edited paths and two local-only
  commits. Integration uses a separate checkout, with remote target ancestry.

The final suite uses the existing assertions build in the audit worktree.
Its source and test trees match the pending integration tree exactly; no fresh
integration build is claimed. The corrected Android implementation has already
built and passed all three native teleport regressions, and both device runs.

## Review boundaries

Membership reconciliation coalesces position writes after scripts and outside
actor iteration. It visits inactive source-room lists only for MBR migration,
then binds unbound MBR render actors in active rooms. These actors join physics
and scripts on the next normal frame; inactive actors remain unscheduled.
Permanent allocations are guarded by `AssetsBound`. Camera completion remains
limited to the watched actor, and same-room writes preserve smoothing.

The conditional all-room membership scan is linear in room-list entries per
write boundary. Non-MBR relocation, overlapping / outside-room policies and
same-frame destination physics remain the documented limits. The Android
transform API path is not separately exercised by the scripted device fixture.
None is broadened by this merge.

See [audit](../teleport-audit.md), [unloaded actor fix](unloaded-actor-fix.md),
and [Chromecast review](unloaded-actor-android.md).

The main checkout at `/home/will/WorldFoundry-wbniv` stays on local
`2026-new-level` commit `8da671d1`, with its existing uncommitted work intact.
Its local-only `514e642e` and `8da671d1` are not included in this remote merge.
