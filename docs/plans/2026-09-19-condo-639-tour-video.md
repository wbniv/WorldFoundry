# 20‑second guided tour video of every room in 205/639

## Context

[`wflevels/condo_639_640`](2026-09-19-condo-639-640-level.md) is walkable and the bridge can
drive the player ([`tests/walk_condo.py`](../../tests/walk_condo.py) injects joystick bits over the
debug port and reads the player's `X/Y/Z_POS` mailboxes). `wf_game -record_video` already writes
`output.mp4` (640 × 480, 30 fps, libx264 via the ffmpeg pipe). The ask: a **≈20 s video that walks
through all rooms of 205/639**, reproducible from the repo, with the room being visited readable on
screen.

**Reachability on foot (from the source model's `DOORS`)** — six of the seven 639 rooms connect:

| Room (`target`) | Reached via | On foot? |
|---|---|---|
| `639-kitchen` | front door, x 3.86…5.46 at y −15.35 | ✓ |
| `639-bath-S` | `bath-S-E-wall` door, y −14.3…−13.5 at x 2.0 | ✓ |
| `639-project-rm` | `kitchen-N-wall` door #2, x 3.95…4.75 at y −8.0 | ✓ |
| `639-guest-bed` | `kitchen-N-wall` door #1, x 2.85…3.65 at y −8.0 | ✓ |
| `639-patio-recessed` | `front-strip-S-wall` door, x 2.85…3.65 at y −2.0 | ✓ |
| `639-patio` | open to patio‑recessed (no partition between x 5.4) | ✓ |
| `639-bath-N` | **no doorway**: closed by `front-strip-S-wall` (south) and `bath-N-E-wall` (east) | ✗ |

`639-bath-N` is sealed in the model (the schematic drew no door). The tour cannot enter it without
a source change — see *Decision needed*.

## Approach

One bridge‑driven script that records, one Taskfile entry, captions burnt in afterwards.

1. **`tests/record_condo_639_tour.py`** — launches `wf_game -L… -record_video --debug-port …`
   (recording starts at frame 0), waits for the player idx, then walks a fixed **waypoint list**
   with `inject_input(joystick1_raw, bits, −1)` per leg, releasing when the watched `X/Y_POS` is
   within 0.15 m of the waypoint (same primitives as `walk_condo.py`). Each room gets a ~1 s hold
   so the caption is readable. On the last waypoint it sends a 0 input, waits 1 s, `SIGTERM`s the
   engine (the recorder finalises the mp4 on exit — the moon/SMB recordings use the same path),
   and renames `output.mp4`.
2. **Room detection = the level's own `target` bboxes.** The script parses `condo_639_640.lev`
   (`lev_name_to_pos` + the `BOX3`) for every `target` whose name starts `639-`, and each tick
   records `(t, room)` for the player position → an `.srt` with one cue per room entry
   (`00:03.4 → 00:06.1  639-kitchen`). No engine change, no ActBox.
3. **Pace and post‑process.** The route below is ≈36 m; at the interactive level's 1.6 m/s that is
   ≈24 s plus holds. `Max Ground Speed` is OAD data (not a mailbox), so the tour uses its own build:
   `CONDO_TOUR=1 blender … blender_create_condo.py` bumps `Max Ground Speed` to 2.0 m/s and spawns
   at the front door `(4.66, −16.0)`, exported as `condo_639_640_tour` (never the interactive
   default). 36 m / 2.0 m/s + 6 × ~0.7 s holds ≈ 22 s; ffmpeg then burns the `.srt` in
   (`subtitles=…:force_style='FontSize=22,Outline=2'`, libass is built in), prepends a 12‑frame
   title card ("205/639 — room tour, 2026‑09‑19") and trims the holds with `setpts` to land at
   20 s ± 1 s.
4. **Route** (waypoints in metres, all inside doorways with ≥ 0.2 m clearance):
   `(4.66,−16.0)` start → `(4.66,−12.0)` kitchen ⏸ → `(2.6,−13.9)` → `(1.0,−13.9)` bath‑S ⏸ →
   `(2.6,−13.9)` → `(4.35,−9.5)` → `(4.35,−5.0)` project‑rm ⏸ → `(4.35,−9.5)` → `(3.25,−9.5)` →
   `(3.25,−5.0)` guest‑bed ⏸ → `(3.25,−1.0)` patio‑recessed ⏸ → `(6.6,−1.0)` patio ⏸ (end).
   Straight legs only (doom‑stick strafes are axis‑aligned), each leg one joystick bit.
5. **`task video-condo-639`** — deps `condo-level`; runs the script, then ffmpeg; writes
   `wflevels/condo_639_640/tour-639.mp4` (+ `tour-639.srt`). Idempotent via `sources:`
   (the standalone `.iff`, the script) / `generates:`.
6. **Verification artefacts**: the mp4, the srt, and three frames grabbed at kitchen / bath‑S /
   patio into `docs/plans/screenshots/`.

### Decision needed — `639-bath-N`

The brief says *all rooms*; the model seals bath‑N. Options, your call:

- **(a) Fix the source** (recommended): add a door to `~/scripts/aircon-blender.py`'s `DOORS["639"]`,
  e.g. `("front-strip-S-wall", 12.0, 24.8)` (guest bedroom → bath‑N, 80 cm at x 0.75…1.55), rerun
  `task aircon-blender`, and the level + tour pick it up automatically (route gains one leg,
  ≈+3 s, absorbed by the speed/trim step).
- **(b) Ship the 6‑room tour** and caption bath‑N as "no door in model" when the player passes its
  wall.

The plan is written for (a); (b) is the fallback if you'd rather not touch the model.

## Mockups

[![Tour storyboard](2026-09-19-condo-639-tour-video/tour-storyboard.png)](2026-09-19-condo-639-tour-video/tour-storyboard.html)

Storyboard of the 20 s cut: the route over the 639 plan with the seven stops, the timeline strip
(who is on screen when), and a mock of the burnt‑in caption on a real engine frame. Toggle the
states to see the *bath‑N unreachable* variant (option b) and the title card.
[Open the interactive mockup](2026-09-19-condo-639-tour-video/tour-storyboard.html).

## Out of scope

- A 640 tour (same script, different waypoints; do it once 639's cut is approved).
- Camera moves other than the doll‑house follow (a fly‑through would need a second CamShot + ActBoxOR switching).
- Higher than 640 × 480: the Linux HAL has no `-width/-height` switch yet (TODO item exists); upscale with ffmpeg if needed.

## Verification

1. **Tour build exists.** `CONDO_TOUR=1` export + build succeeds; `grep "Max Ground Speed"` in the tour `.lev` shows `2.0`.
2. **Script visits every room.** `python3 tests/record_condo_639_tour.py` exits 0 and prints one `ENTER <room> t=…` line for each of the 639 rooms (7 with option a, 6 with b), in route order.
3. **Video length and content.** `ffprobe tour-639.mp4` → duration 19–21 s, 640 × 480, 30 fps; the `.srt` has one cue per room.
4. **Captions readable.** Frames at 3 s / 9 s / 18 s saved to `docs/plans/screenshots/2026-09-19-tour-{kitchen,bath-s,patio}.png` show the room name legibly.
5. **Re‑run is a no‑op.** `task video-condo-639` twice → second run "up to date".
