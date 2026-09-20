# Condo 639-project-rm: north wall is telescoping glass doors, not a wall

## Context

The condo level's north wall of `639-project-rm` is currently modeled as mostly solid
wall with a fixed partial-height window, when the real building has floor-to-ceiling
telescoping glass doors there: 3 panels that gather at the room's east end — 1 fixed in
place, 2 movable. User correction, source-of-truth is the user's own knowledge of the
real unit (the source survey `~/docs/aircon/units-639-640.blend` evidently missed this
distinction — surveys commonly capture glazing as a plain window when it's actually an
operable wall).

Verified against the actual geometry (level axes: `+X` north, `+Y` west, per
`site_constants.py`'s header comment) by querying the source `.blend` directly with a
read-only headless Blender script:

- `639-project-rm` room bbox: x 3.8→7.8 (S→N), y −8.0→−2.0 (E→W), z 0→2.7. North wall
  is the x≈7.8 face, 6 m long.
- There *is* a `glass`-material object there already — `639-window-1`, bbox x
  8.04–8.06, y **−6.75→−2.0** (4.75 m of the 6 m wall — 1.25 m nearest the east end,
  y −8.0→−6.75, is unaccounted for by either the window or a found wall object), z
  **0.9–2.3** (a window sill-to-head band, not floor-to-ceiling). This is the object
  that needs replacing/extending, not new-from-nothing geometry.
- The partition wall between the project room and the guest bedroom
  (`639-guest-project-wall`, bbox x 3.75–3.85, y −8.0→−2.0, z 0–2.7) is a distinct,
  correctly-modeled solid wall — **not** the one being corrected here.

User direction on the two open questions this raises:

1. **Default depicted state: open, gathered at the east end** (not closed) — the level
   should show the doors folded near y≈−8.0, with most of the wall an open threshold,
   not a closed glazed wall.
2. **Interactivity: real, not just static geometry.** The 2 movable panels should
   actually be operable at runtime (player can open/close them), not just corrected to
   look right in a screenshot.

## Approach

Confirmed by research: the engine has **no dedicated door/mover/elevator actor**.
`Platform` (`wfsource/source/game/platform.hp/.cc`) exists as an OAD/collision-table
entry described as "moving, animating platform," but `Platform::initPath()` is a stub
(`platform.cc:59-62`, body commented out) — not usable as-is. There's also no Forth
syscall for "move this actor to X over time Y" (`TODO.md:131` names this gap
explicitly). No level in `wflevels/` has ever built an interactive door, gate, or
platform — there's no precedent to copy.

Two real primitives exist and are used elsewhere in this codebase, and either can
deliver "interactive," but they trade off animation smoothness against engine risk:

1. **`Visibility Mailbox` two-state swap (recommended).** A per-mesh-actor OAD field
   (`oas/mesh.inc:10`) already used throughout this level (every statplat actor gets
   one, `docs/plans/2026-09-19-condo-639-640-level.md:104-105`) and already proposed
   for an analogous binary toggle (the not-yet-built "drop-ceiling toggle" TODO item).
   Author two static mesh states — **closed** (3 panels spanning the wall) and **open**
   (1 fixed + 2 folded near the east jamb) — sharing one mailbox index with inverted
   defaults, so exactly one is ever visible. An `ActBox` proximity volume
   (`game/actbox.cc:79-84`) near the doors flips that mailbox on player entry/exit —
   the same "player approaches → level responds" pattern already used for this level's
   POV-camera zones (`add_pov_camera`). No per-tick script, no new engine code, no
   deviation from patterns already shipped in this file.
2. **Rejected for v1: continuous sliding via mailbox-driven position lerp.** A per-tick
   Forth script could write the `X_POS`/`Y_POS`/`Z_POS` local mailboxes (3009-3011,
   `mailbox.inc:218-220`) each frame to interpolate a true slide, following the
   `fsn_flydown()` pattern (`engine/stubs/scripting_zforth.cc:189-201`, which lerps a
   camera over 2.5 s the same way) as a template. Rejected for this pass: it's a
   first-of-its-kind pattern in this codebase (no existing door/platform script to
   crib from), and direct position-mailbox writes are documented to bypass the Jolt
   character-body sync (`docs/plans/2026-05-11-mailbox-pos-write-bypasses-jolt.md`) —
   real collision risk while a solid glass panel is mid-slide. Worth revisiting as a
   follow-up once the two-state swap is proven out; noted under Out of scope.

**Geometry correction**, regardless of which trigger approach: in
`blender_create_condo.py`, post-process the imported `639-window-1` object (same
pattern as `darken_floors()`/`darken_seams()` — transform the appended source mesh,
never touch the read-only source `.blend`) into the two mesh states above, each panel
extended to floor-to-ceiling (z 0→2.7) and covering the full 6 m span (y −8.0→−2.0)
between the two states, split into 3 roughly-equal panels (flagged assumption, see
Mockups). The closed state's 3 panels get normal collision (solid, like any statplat
wall); the open state's folded stack should **not** block the now-open threshold — this
needs confirming whether a hidden (`Visibility Mailbox`-false) actor still collides,
which isn't established by the research above; verify empirically (Verification step 2)
rather than assume either way before building both states.

**What's beyond the north wall when open** is still unmapped (the source model has no
geometry past x=7.8 for this room) — unresolved, see Mockups' flagged assumptions.

## Mockups

[![639-project-rm north wall: current partial window vs. corrected closed/open telescoping-door states, top-down](2026-09-20-condo-project-room-telescoping-doors/floorplan-correction.png)](2026-09-20-condo-project-room-telescoping-doors/floorplan-correction.html)

Three top-down states, drawn to the real measured coordinates above: **current**
(the existing partial window, 4.75 m of 6 m, sill-to-head only), **corrected/closed**
(3 floor-to-ceiling panels spanning the full wall — shown for reference, not the
default), and **corrected/open** (the depicted default — panels gathered near the east
end, most of the wall an open threshold). [Open the interactive
mockup](2026-09-20-condo-project-room-telescoping-doors/floorplan-correction.html) —
it also marks, in amber, the two dimensions that are assumptions rather than measured
facts and need your confirmation before implementation:

- Equal ~2.0 m panel widths (no source data on the real panel split).
- Gathered/open stack depth ≈1.3 m (typical bi-fold/telescoping hardware compresses to
  roughly 1–1.5 panel-widths — not a measured value for this door).

## Out of scope

- Resolving what's beyond the north wall when open (balcony? patio? open air 6 stories
  up?) — the source model has nothing mapped there; needs the user's knowledge of the
  real building before any geometry is added past x=7.8, and is a bigger addition than
  the doors themselves (would need its own floor/railing/safety geometry, akin to the
  existing `CORRIDOR`/`PARAPET_H` balcony treatment elsewhere in this file).
- True continuous sliding animation (mailbox-driven per-tick position lerp, the
  `fsn_flydown()` pattern) — rejected for v1 as a first-of-its-kind, Jolt-sync-risk
  pattern with no precedent in this codebase; the two-state `Visibility Mailbox` swap
  ships first. Revisit once that's proven and if the instant-swap look isn't good
  enough.
- A generic "mover/door" actor class or Forth "move actor over time" syscall — the real
  engine gap this surfaced (`TODO.md:131`, `docs/investigations/2026-05-26-spawn-template-forth-primitive.md`).
  Worth its own engine-level investigation if more than one level ever wants true
  sliding actors; not attempted here.
- Extending this telescoping-door pattern to any other wall/unit — 639-project-rm only.
- Real-world-accurate door hardware/track visuals (rollers, header track, handles) —
  glass panels + a plausible frame, not a hardware-accurate model.

## Verification

1. Rebuild the condo Blender scene headless
   (`blender --background --python wflevels/condo_639_640/blender_create_condo.py`)
   and confirm the `[condo] ...` stdout reports the two new door mesh states (closed:
   3 panels: open: 1 fixed + 2 folded) replacing `639-window-1`, with correct
   floor-to-ceiling / full-6m-span dimensions.
2. Load the level (`task run-condo` or equivalent) and empirically confirm: (a) in the
   default (open) state, the player can walk through the threshold where the wall used
   to be — no leftover collision from the hidden closed-state panels; (b) walking away
   and the `ActBox` firing the closed state re-blocks the opening with real collision.
   This resolves the open "does a hidden Visibility-Mailbox actor still collide"
   question empirically rather than by assumption.
3. Confirm the `ActBox` trigger correctly flips the shared mailbox on player entry/exit
   without affecting any other zone/trigger in the level (this level already has
   several `ActBox`-driven POV-camera zones — check for mailbox-index collisions).
4. Capture a screenshot of both states (closed and open) from the dollhouse camera and
   save into this plan's bundle, confirming the corrected geometry visually matches the
   Mockups' corrected/closed and corrected/open diagrams (panel positions, east/west
   orientation).
5. Rebuild `condo_639_640_tour` and confirm no regression — the tour's waypoint path
   already routes through `639-project-rm` (`tour-639.path.json:54`); confirm it still
   walks the room correctly with the doors in whatever state the tour's script leaves
   them (likely open, matching the default).

<!--
When the work lands, this section becomes the permanent record:

1. **Step as originally written.**

```
$ the exact command
raw output, unedited
```

**PASS** — one line on what the output proves.

An item stays `[verify T<n>]` in TODO.md until every step here has recorded output.
-->
