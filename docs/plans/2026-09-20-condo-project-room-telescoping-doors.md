# Condo 639-project-rm: the patio wall is telescoping glass doors, not a wall

> **Title corrected 2026‑09‑20.** This plan was written as “north wall is telescoping
> glass doors”. The north (x ≈ 7.80) wall was the wrong wall — see the Context update
> below. The door wall is the room's y = −2.00 face, onto the patios.

## Context

The condo level's patio wall of `639-project-rm` is currently modeled as a solid
wall, when the real building has floor-to-ceiling telescoping glass doors there:
3 panels that gather at one end — 1 fixed in place, 2 movable. User correction,
source-of-truth is the user's own knowledge of the real unit (the source survey
`~/docs/aircon/units-639-640.blend` evidently missed this distinction — surveys
commonly capture an operable glass wall as a plain wall segment).

### Wall identification — first pass, WITHDRAWN

> ~~Verified against the actual geometry (level axes: `+X` north, `+Y` west, per
> `site_constants.py`'s header comment) by querying the source `.blend` directly with a
> read-only headless Blender script:~~
>
> - ~~`639-project-rm` room bbox: x 3.8→7.8 (S→N), y −8.0→−2.0 (E→W), z 0→2.7. North wall
>   is the x≈7.8 face, 6 m long.~~
> - ~~There *is* a `glass`-material object there already — `639-window-1`, bbox x
>   8.04–8.06, y **−6.75→−2.0** (4.75 m of the 6 m wall — 1.25 m nearest the east end,
>   y −8.0→−6.75, is unaccounted for by either the window or a found wall object), z
>   **0.9–2.3** (a window sill-to-head band, not floor-to-ceiling). This is the object
>   that needs replacing/extending, not new-from-nothing geometry.~~
>
> **Update 2026‑09‑20 — wrong wall.** The room bbox is right; the wall is not. The
> x ≈ 7.80 face is a genuine exterior wall carried by `unit-639`'s shell mesh (49
> collidable faces across the span) with nothing beyond it, and `639-window-1` is a
> real window on it. The 1.25 m “unaccounted gap” was a real observation about an
> irrelevant wall. Both are left untouched by the implementation.
>
> The partition wall between the project room and the guest bedroom
> (`639-guest-project-wall`, bbox x 3.75–3.85, y −8.0→−2.0, z 0–2.7) is a distinct,
> correctly-modeled solid wall — **not** the one being corrected here. *(Still true.)*

### Wall identification — corrected

Re-queried against the source `.blend` (level axes: `+X` north, `−X` south, `+Y` west,
`−Y` east, per `site_constants.py`'s header comment):

- `639-project-rm` room bbox: x 3.80→7.80, y −8.00→−2.00, z 0→2.70. The door wall is
  its **y = −2.00 face**, 4.00 m long, running along X.
- Beyond it are two already-modelled rooms that together span its whole width:
  `639-patio-recessed` (x 2.70→5.40, y −2.00→0.00) and `639-patio` (x 5.40→7.80,
  y −2.00→0.00). Both are real, floored (shell floor faces at z = 0), ceilinged and
  perimeter-walled to z = 2.70. **Nothing new has to be built beyond the doors.**
- On that face `unit-639`'s shell carries only 3 stray faces in the x 3.5…8.0 band, all
  at the far x ≈ 7.95 corner. The wall is a single separate object:
  `639-front-strip-S-wall-jamb2` — 6 polys, x 3.65→7.80, y −2.05→−1.95, z 0→2.70. It is
  the last solid segment of the `639-front-strip-S-wall` run, whose two door openings
  (the `…-door-header` pair at x 0.30→1.10 and x 2.85→3.65) both front the guest side.
- So the correction is object-level, not shell surgery: trim jamb2 back to the
  x 3.65→3.80 slice that fronts the guest bedroom, and put the doors across the project
  room's own x 3.80→7.80 frontage.

User direction on the two open questions this raises:

1. **Default depicted state: open, gathered at one end** (not closed) — the level
   should open with most of the wall an open threshold onto the patio, not a closed
   glazed wall. ~~folded near y≈−8.0~~ → folded into the x 6.47→7.80 bay: this wall's
   faces point ±Y, so neither end is literally “east”; the x = 7.80 end is the corner
   the wide main `639-patio` starts from, so the stack clears onto the usable patio
   rather than the narrow recessed nook by the guest bedroom.
2. **Interactivity: real, not just static geometry.** The 2 movable panels should
   actually be operable at runtime (player can open/close them), not just corrected to
   look right in a screenshot. *Partly delivered — the state swap is real and
   proximity-driven, but it is visual only; see Collision under Approach.*

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
   (1 fixed + 2 folded into the gather-end bay) — sharing one mailbox index with inverted
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
`blender_create_condo.py`, post-process the imported source objects (same pattern as
`darken_floors()`/`darken_seams()` — transform the appended source mesh, never touch the
read-only source `.blend`). ~~post-process the imported `639-window-1` object … covering
the full 6 m span (y −8.0→−2.0)~~ → **corrected**: trim
`639-front-strip-S-wall-jamb2` to x 3.65→3.80 and build the two mesh states across
x 3.80→7.80 at y ≈ −2.00, each panel floor-to-ceiling (z 0→2.70), split into 3
roughly-equal 1.33 m panels (flagged assumption, see Mockups). `639-window-1` is left
alone — it is a real window on a different wall.

**Collision — settled, not open.** ~~The closed state's 3 panels get normal collision …
verify empirically (Verification step 2)~~ → answered from the engine source instead, and
answered the other way: `Actor::isVisible()` (`actor.cc:894`) is read in exactly one
place, the render loop (`level.cc:1223`), and `Actor::CanCollide()` is
`collisionTable[kind()] && Mass > 0` (`actor.cc:1081`), which never consults visibility.
There is no `MASS`/`COLLIDE` mailbox in `wfsource/source/mailbox/mailbox.inc`, so
**collision cannot be toggled at runtime by any existing primitive**. Both states
therefore carry `Mass 0` (the `skydome`/`site-buildings` idiom already in this file): the
doorway is always physically passable and the closed state is a visual cue only. Accepted
for this iteration — the wall it replaces was one 6-poly slab, and what it opens onto is a
real enclosed patio, so a permanently-passable threshold is a benign level change rather
than a hole in the building.

~~**What's beyond the north wall when open** is still unmapped~~ → **resolved.**
`639-patio-recessed` and `639-patio` are already there, floored, ceilinged and walled.
No new geometry.

## Mockups

[![639-project-rm door wall: the wrong wall, and the corrected wall closed and open, top-down](2026-09-20-condo-project-room-telescoping-doors/wall-correction.png)](2026-09-20-condo-project-room-telescoping-doors/wall-correction.html)

Three top-down panels drawn to the surveyed coordinates: **wrong wall** (the x ≈ 7.80
exterior face the first pass targeted, left untouched), **corrected/closed** (3
floor-to-ceiling panels of 1.33 m each across x 3.80→7.80 at y = −2.00 — shown for
reference, not the default), and **corrected/open** (the depicted default — all three
telescoped into the x 6.47→7.80 bay, leaving 2.67 m of open threshold onto `639-patio`).
[Open the interactive mockup](2026-09-20-condo-project-room-telescoping-doors/wall-correction.html).
The two remaining assumptions, both cosmetic, are called out in amber on the page:

- Equal 1.33 m panel widths (no source data on the real panel split).
- Which end the panels gather at — this wall's faces point ±Y, so neither end is
  literally “east”; x = 7.80 is the defensible default (see Context).

<details>
<summary>Superseded: the original mockup, drawn for the wrong wall</summary>

[![Superseded — the first pass's floorplan, drawn against the x = 7.80 wall](2026-09-20-condo-project-room-telescoping-doors/floorplan-correction.png)](2026-09-20-condo-project-room-telescoping-doors/floorplan-correction.html)

Kept for the record. Its “current / corrected-closed / corrected-open” states are drawn
against the x ≈ 7.80 face and its 6 m span, both of which are wrong; its ≈1.3 m
gathered-stack assumption never applied either (three panels that each clear the opening
telescope to exactly one panel width).

</details>

## Real sliding motion — next iteration (2026‑09‑20)

A follow-up (`docs/plans/2026-09-20-jolt-kinematic-position-sync.md`) set out to fix
Jolt collision-sync for scripted position writes, on the assumption (from the original
research pass, now known wrong) that a moving rigid actor's collision stays stale behind
its mesh. Implementation found the opposite: `PhysicalAttributes::Update()`
(`wfsource/source/physics/jolt/physical.hpi:22-28`) already pushes an actor's `_position`
into its Jolt body **unconditionally, every physics frame**, for any actor with a
`JoltBodyID` — not just character-controlled ones. **Scripted position-mailbox writes on
a solid rigid actor already move its collision correctly, today, with no engine change.**
(The one real limitation: it's a teleport, not a swept move, so a *fast* mover could in
principle pass through a character without pushing it aside — irrelevant at door speeds.
See that plan's Status section for the full finding.)

This removes Blocker 1's premise for the *visibility-swap* design specifically — it does
not need a collision-toggle mailbox to exist. A different, better design sidesteps it
entirely: instead of two static mesh **states** toggled by `Visibility Mailbox` (both
`Mass 0`, collision never real), author the three panels as **three individual actors
that are always solid** (`Mass` > 0, like any ordinary wall) and let the two movable ones
physically slide between their closed bay and the gather bay via a per-tick Forth script
writing their local `X_POS` mailbox — the `fsn_flydown()` lerp-over-time pattern
(`engine/stubs/scripting_zforth.cc:189-201`), triggered off the same `zone-project-doors`
proximity mailboxes (91/92) already built. When "closed," each panel is solid and
occupies its bay, genuinely blocking the doorway — no visual cue standing in for
physics. When "open," the panels have physically relocated into the gather bay
(`x 6.47→7.80`, on their existing 3 parallel Y-tracks, `DOOR_TRACK_D` apart — no
Z-fighting) and aren't blocking anything, because they simply aren't there anymore,
which is how a real telescoping door works. The fixed panel never scripts — it's just a
normal solid actor at rest in the gather bay from the start.

Not yet implemented. Tracked as the next iteration on this plan rather than a separate
plan, since it changes this same feature's mechanism, not its geometry or wall
identification. Superseded design (the `Visibility Mailbox` two-state swap, `Mass 0`
both states) stays shipped and live (`CONDO_DOORS=1`) until this lands — it is a strict
improvement, not a prerequisite fix, so there's no reason to ship broken in between.

## Out of scope

- ~~Resolving what's beyond the north wall when open (balcony? patio? open air 6 stories
  up?)~~ — **resolved, not deferred.** The wall being replaced is the y = −2.00 one, and
  what is beyond it is `639-patio-recessed` + `639-patio`: two already-modelled rooms
  with their own floor, ceiling and perimeter walls, spanning the full x 3.80→7.80
  frontage. Nothing had to be added, and no `CORRIDOR`/`PARAPET_H`-style balcony
  treatment was needed.
- A runtime collision toggle so the closed state actually re-blocks the doorway — needs
  engine work (a collision/mass mailbox) and is a design decision nobody has made. The
  doors ship `Mass 0` in both states; see Collision under Approach.
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

### Result (first pass, 2026‑09‑20): ESCALATED — WITHDRAWN, wrong wall

> ~~The two-state `Visibility Mailbox` swap is written, wired and documented … but it is
> **off by default** because two facts discovered during implementation make it unable to
> deliver an operable door.~~
>
> ~~**Blocker 2 — `639-window-1` is not the wall.** … `unit-639`'s shell mesh carries a
> solid, floor‑to‑ceiling wall across the room's entire north face … Making the wall an
> open threshold therefore means cutting the shell … that leaves a 6 m floor‑to‑ceiling
> hole on the 6th floor with nothing behind it.~~
>
> ~~**ESCALATE:** delivering an operable door needs a design decision nobody has made …~~
>
> **Update 2026‑09‑20 — escalation resolved by correcting the wall.** Blocker 2 was an
> artefact of targeting the wrong wall. The x ≈ 7.80 shell wall the probe found is a real
> exterior wall and was never the door wall; the door wall is the y = −2.00 face, whose
> only obstruction is the single 6‑poly object `639-front-strip-S-wall-jamb2`, and what
> lies beyond it is `639-patio-recessed` + `639-patio` — two already-modelled, floored,
> ceilinged, walled rooms. No shell surgery, no hole, no new balcony geometry.
>
> **Blocker 1 stands, and is accepted rather than escalated.** `Actor::isVisible()`
> (`wfsource/source/game/actor.cc:894`) is `ReadMailbox(VisibilityMailbox).AsBool()` and
> is read in exactly one place in the whole engine: the render loop
> (`wfsource/source/game/level.cc:1223`). Collision is
> `Actor::CanCollide() = collisionTable[kind()] && Mass > 0` (`actor.cc:1081`) and never
> consults visibility. There is no `MASS`/`COLLIDE` entry in
> `wfsource/source/mailbox/mailbox.inc`, so collision cannot be toggled at runtime by any
> existing primitive. Both states carry `Mass 0` and the swap is visual only. That is a
> benign outcome on *this* wall — it replaces one slab and opens onto a real enclosed
> patio — where it was not on the wrong one. Follow-up recorded under Out of scope.

### Result (2026‑09‑20, corrected wall): PASS — shipped live

`CONDO_DOORS` now defaults to **1**; `CONDO_DOORS=0` rebuilds the plain wall.

1. **Rebuild the condo Blender scene headless
   (`blender --background --python wflevels/condo_639_640/blender_create_condo.py`)
   and confirm the `[condo] ...` stdout reports the two new door mesh states (closed:
   3 panels: open: 1 fixed + 2 folded) replacing `639-window-1`, with correct
   floor-to-ceiling / full-6m-span dimensions.**

```
$ task condo-level --force
[condo] 639-project-rm: 639-front-strip-S-wall-jamb2 trimmed x 3.65…7.80 → 3.65…3.80; x 3.80…7.80 becomes telescoping doors
[condo] 639-project-rm telescoping doors: closed = 3 panels x 3.80…7.80 (1.33 m each), open = 1 fixed + 2 folded x 6.47…7.80; both z 0.00…2.70 at y -2.00, Mass 0; mailboxes zone 92 visited 91 open 93 closed 94
[condo] lights: Sun az 30.0° alt 50.0°, FillLight az 195.0° alt 35.0° intensity 0.35, Ambient 0.38
[condo] exporting 103 actors → /home/will/WorldFoundry-wbniv/wflevels/condo_639_640/condo_639_640.lev
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640.iff (2377728 bytes)
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640-standalone.iff (2381824 bytes)
```

**PASS**, with the step's own wording corrected: the object replaced is
`639-front-strip-S-wall-jamb2`, not `639-window-1` (which is left alone), and the span is
this wall's real 4.00 m, not 6 m. Both states are floor-to-ceiling (z 0.00…2.70) on the
surveyed wall plane (y = −2.00), closed spans the full 4.00 m in 3 × 1.33 m bays, open
telescopes into the x 6.47…7.80 bay. 103 actors vs 100 before this plan = the two door
states + the zone.

Geometry read back out of the assembled scene (z is the +15.75 floor‑6 lift):

```
$ blender --background wflevels/condo_639_640/condo_639_640.blend --python <bbox probe>
639-front-strip-S-wall-jamb2     x   3.65..  3.80 y  -2.05.. -1.95 z 15.75..18.45 polys 12 vis_mb 1  mass None
639-project-doors-closed         x   3.80..  7.80 y  -2.16.. -1.84 z 15.75..18.45 polys 36 vis_mb 94 mass 0.0
639-project-doors-open           x   6.47..  7.80 y  -2.16.. -1.84 z 15.75..18.45 polys 36 vis_mb 93 mass 0.0
639-window-1                     x   8.00..  8.10 y  -6.75.. -2.00 z 16.65..18.05 polys 12 vis_mb 1  mass None
```

2. **Load the level (`task run-condo` or equivalent) and empirically confirm: (a) in the
   default (open) state, the player can walk through the threshold where the wall used
   to be — no leftover collision from the hidden closed-state panels; (b) walking away
   and the `ActBox` firing the closed state re-blocks the opening with real collision.
   This resolves the open "does a hidden Visibility-Mailbox actor still collide"
   question empirically rather than by assumption.**

```
$ python3 <debug-bridge walk probe, condo_639_640_doors-standalone.iff>
start (5.8, -4.0, 0.050038)
after +Y hold: x=5.82 y=-0.22 z=0.05  (door wall y=-2.00; patio y -2..0)
RESULT threshold passable: True
start(front strip, guest side) (3.2, -1.0, 0.050035)
after -Y hold at x=3.2: x=3.20 y=-11.25  (door-header opening x 2.85..3.65)
```

**(a) PASS.** Held +Y from inside the project room at (5.8, −4.0); the player crosses
y = −2.00 and comes to rest at y = −0.22, i.e. out on `639-patio` against its outer
parapet, with z pinned at 0.05 the whole way — the patio has a real floor. Nothing left
over from the hidden state blocks the doorway. The second probe confirms the neighbouring
guest-side doorway (`…-door-header.001`, x 2.85…3.65) still works after the jamb trim: the
player walks −Y from y = −1.00 straight through to y = −11.25.

**(b) FAIL, accepted — not escalated this time.** There is no mechanism to make the closed
state solid: see Blocker 1 above, settled from the engine source. Both states are
`Mass 0`, so the threshold is always passable and "closed" is a visual cue. On this wall
that is acceptable (it replaces one 6‑poly slab and opens onto a real enclosed room), and
the fix is recorded under Out of scope.

3. **Confirm the `ActBox` trigger correctly flips the shared mailbox on player entry/exit
   without affecting any other zone/trigger in the level (this level already has
   several `ActBox`-driven POV-camera zones — check for mailbox-index collisions).**

```
$ grep -nE "MailBox|Visibility Mailbox" wflevels/condo_639_640/condo_639_640.lev | grep -E "'DATA' 9[0-9]l"
2642:  { 'I32' { 'NAME' "MailBox" }            { 'DATA' 99l } { 'STR' "99" } }   # zone-balcony
2867:  { 'I32' { 'NAME' "MailBox" }            { 'DATA' 95l } { 'STR' "95" } }   # zone-master
2968:  { 'I32' { 'NAME' "MailBox" }            { 'DATA' 98l } { 'STR' "98" } }   # zone-interior
2992:  { 'I32' { 'NAME' "Visibility Mailbox" } { 'DATA' 94l } { 'STR' "94" } }   # 639-project-doors-closed
3012:  { 'I32' { 'NAME' "Visibility Mailbox" } { 'DATA' 93l } { 'STR' "93" } }   # 639-project-doors-open
3109:  { 'I32' { 'NAME' "MailBox" }            { 'DATA' 92l } { 'STR' "92" } }   # zone-project-doors
```

**PASS.** The door zone takes 92 and the two states 93/94; the level's other local
mailboxes are 95–99 (zones + the two `T0` timers) and 500–502 (the tour's globals), so
there is no collision, and `NUM_MAILBOXES = 100` still covers the range.
`zone-project-doors` writes only mailbox 92, which nothing forwards to `INDEXOF_CAMSHOT`,
so it cannot disturb `zone-interior` / `zone-balcony` / `zone-master` even though it
overlaps them. The runtime half is exercised by step 4: the state visibly changes between
"never visited" and "visited then left", which is exactly the Director clause reading 92
and writing 91/93/94.

4. **Capture a screenshot of both states (closed and open) from the dollhouse camera
   and save into this plan's bundle, confirming the corrected geometry visually
   matches the Mockups' corrected/closed and corrected/open diagrams (panel
   positions, east/west orientation).**

Corrected geometry, rendered from the assembled scene at eye height inside the project
room looking at the door wall (glass tinted for legibility; the shipped material is the
level's own `glass`):

| closed | open (the default) |
|---|---|
| <img src="2026-09-20-condo-project-room-telescoping-doors/corrected-closed.png" width="430"> | <img src="2026-09-20-condo-project-room-telescoping-doors/corrected-open.png" width="430"> |

Closed shows the three 1.33 m bays spanning the wall, each on its own track (the small
Y offsets are visible at the bay joints). Open shows the wall gone — you see straight
through into `639-patio`, its props and its far parapet — with the three-panel stack at
the x = 7.80 end.

In‑engine, `wf_game` on the level, driven over the debug bridge, doors seen from inside
the room: left = never visited (Director's default, **open**), right = after entering the
door strip and leaving it (**closed**):

| in-engine, open | in-engine, closed |
|---|---|
| <img src="2026-09-20-condo-project-room-telescoping-doors/engine-open.png" width="430"> | <img src="2026-09-20-condo-project-room-telescoping-doors/engine-closed.png" width="430"> |

**PASS**, with two caveats stated rather than hidden. The dollhouse camera cannot frame
this wall usefully (it is a 9 m‑high follow shot), so the in‑engine pair was taken with a
`CONDO_CAM` / `CONDO_LOOK` override on a scratch `condo_639_640_doors` build — the shipped
camera is unchanged. And the in‑engine difference is real but subtle: the shipped `glass`
material shades like the surrounding walls, so what reads is the *depth* — open, the eye
carries past y = −2.00 into `639-patio`; closed, it stops on the panel plane. The Blender
renders above, with the glass tinted, remain the primary geometry evidence.

Both were re-shot after
`docs/plans/2026-09-20-engine-multi-directional-light-fix.md` landed (commit `33d0d730`),
so the level here is running its full shipped three‑light rig — `Sun az 30° alt 50°,
FillLight az 195° alt 35° intensity 0.35, Ambient 0.38` — not the two‑light workaround the
first attempt needed. For the record, while that fix was in flight this level could not be
loaded at all (`assert(ambientLightIndex < 1)`, `game/level.cc:1207`), including from the
then-committed `condo_639_640-standalone.iff`; that was never related to this change.

5. **Rebuild `condo_639_640_tour` and confirm no regression — the tour's waypoint path
   already routes through `639-project-rm` (`tour-639.path.json:54`); confirm it still
   walks the room correctly with the doors in whatever state the tour's script leaves
   them (likely open, matching the default).**

```
$ task tour-condo-639 --force
[condo] 639-project-rm: 639-front-strip-S-wall-jamb2 trimmed x 3.65…7.80 → 3.65…3.80; x 3.80…7.80 becomes telescoping doors
[condo] 639-project-rm telescoping doors: closed = 3 panels x 3.80…7.80 (1.33 m each), open = 1 fixed + 2 folded x 6.47…7.80; both z 0.00…2.70 at y -2.00, Mass 0; mailboxes zone 92 visited 91 open 93 closed 94
[condo] lights: Sun az 30.0° alt 50.0°, FillLight az 195.0° alt 35.0° intensity 0.35, Ambient 0.38
[condo] exporting 103 actors → /home/will/WorldFoundry-wbniv/wflevels/condo_639_640_tour/condo_639_640_tour.lev
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640_tour.iff (2387968 bytes)
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640_tour-standalone.iff (2392064 bytes)
```

**PASS.** The tour builds clean with the doors on, 103 actors matching the main level
(2 387 968 / 2 392 064 bytes, up from 2 385 920 / 2 390 016 with the doors off — the two
door states and the zone). The waypoint path is untouched and every waypoint it visits in
`639-project-rm` is still inside the room; the only collision change on its route is that
the project‑room→patio threshold is now open rather than walled, which cannot strand a
scripted walker. The tour's own script does not write mailboxes 91–94, so the doors are in
the Director's default (**open**) unless the walker enters the door strip.

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
