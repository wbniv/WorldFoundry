# Plan — levcomp-rs: warn on actor outside room bbox

**Date:** 2026-05-16
**Status:** Complete

## Context

When a level actor's world-space center falls outside every room's bounding box,
`levcomp-rs` silently omits it from all room render-entry lists. The engine never
constructs `RenderActor3DAnimates` for it, so it's invisible in-game with no
build-time feedback. This was the root cause of the qbert_practice curse-bubble
not rendering for an entire session (2026-05-12) until the room bbox was manually
expanded.

## Implementation

### `wftools/levcomp-rs/src/rooms.rs`

After the Pass 2 sort loop, before the fallback-room block, added:

```rust
    if !rooms.is_empty() {
        for (i, obj) in objects.iter().enumerate() {
            if room_of_obj[i] != -2 { continue; }
            let center = obj_center(obj);
            let cx = center[0] as f64 / 65536.0;
            let cy = center[1] as f64 / 65536.0;
            let cz = center[2] as f64 / 65536.0;
            eprintln!(
                "levcomp-rs: WARNING: actor {:?} world-center ({:.2},{:.2},{:.2}) \
                 falls outside every room bbox — it will not render in-game. \
                 Expand the room actor in Blender to contain this actor.",
                obj.name, cx, cy, cz
            );
        }
    }
```

Key choices:
- Guard with `!rooms.is_empty()` — no false positives when the no-rooms fallback applies.
- Fixed-point divided by 65536 gives Blender world-unit floats readable to designers.
- `eprintln!` matches existing levcomp-rs convention (no logging crate, stderr only).
- `room_of_obj[i] == -2` excludes room objects themselves (`-1`) and already-assigned
  objects (`>= 0`).

### `docs/level-design-troubleshooting.md`

New section appended at end of file explaining the warning, its cause, and the fix
(enlarge `RoomMinX/Y/Z` / `RoomMaxX/Y/Z` in the room actor until it contains the
orphaned actor).

## Verification

- `cargo build` on levcomp-rs: clean (only pre-existing `dead_code` warnings).
- `levcomp-rs qbert_practice.lev` → no spurious warnings; all actors contained.
- `levcomp-rs snowgoons.lev` → no spurious warnings.
