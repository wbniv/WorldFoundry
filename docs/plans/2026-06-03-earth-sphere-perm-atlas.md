# Plan: Earth sphere in PERM atlas + room/prop architecture

## Context

`task build-level -- moon_site01` was failing with:

```
TEXTILE error: couldn't fit texture "earth.tga" in room "Room0"
```

Room0's 1024×1024 atlas page is entirely consumed by `terrain_texture.tga`
(also 1024×1024 — the NAC lunar map at 1 texel/meter over the 1 km play area).
Earth's 128×64 texture had no room.

Root cause is also a design mismatch: the Room atlas is for the **terrain tile
only**; all prop assets (lander, astronaut, Earth sphere, future rovers/habitat)
belong in the **PERM atlas** which is always loaded and has its own 1024×1024
page (currently nearly empty).

## Architecture decision

> **1 room = 1 ground texture tile. All props → PERM.**

- Room0 atlas: `terrain_texture.tga` only
- PERM atlas: player (astronaut) + artemis lander + earth sphere + future surface
  assets (rover, habitat, solar arrays)

This keeps atlas pages predictable: each room page can be sized exactly to its
terrain tile resolution with no spillover from prop counts.

## Fix

Add `wf_Moves Between Rooms = 'True'` to each prop actor in
`wflevels/moon_site01/blender_create_moon.py`. `levcomp-rs` reads this field
(`lvl_writer.rs:568 moves_between_rooms()`) and sets `OADFLAG_PERMANENT_TEXTURE`,
routing the actor to the PERM pool.

Actors changed:
- `_lander` (artemis_lander) — line ~508
- `_earth` (Earth sphere) — line ~532

The terrain actor (`terrain_obj`) stays in Room0 — no change needed.

## Verification

1. `task build-level -- moon_site01` completes without textile error
2. `moon_site01.ini` shows `Room0 = lunar_terrain.iff` and
   `Perm = player.iff,artemis_lander.iff,earth.iff`
3. `task run-moon` — Earth sphere visible in sky with Blue Marble texture;
   lander visible on terrain; no regressions on terrain shading, HUD, minimap

## Follow-on

Apply the same `wf_Moves Between Rooms = True` pattern to all future surface
props (LTV rover, FSH habitat, VSAT solar arrays) as they are added.
