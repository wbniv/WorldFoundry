# 20‑second guided tour video of every blue (205/639‑owned) room

## Context

[`wflevels/condo_639_640`](2026-09-19-condo-639-640-level.md) is walkable and the bridge can
drive the player ([`tests/walk_condo.py`](../../tests/walk_condo.py) injects joystick bits over the
debug port and reads the player's `X/Y/Z_POS` mailboxes). `wf_game -record_video` already writes
`output.mp4` (640 × 480, 30 fps, libx264 via the ffmpeg pipe). The ask: a **≈20 s video that walks through every blue area** — 205/639's own seven rooms *and* the
parts of 205/640 that belong to 639 (painted with the `unit-639` material in the model: the
master‑bedroom suite north of y −6.75 — bedroom, closet, bath — and `640-room-2.9x3.3`, which the
party‑wall connector opens into) — reproducible from the repo, with the room being visited readable
on screen.

**Reachability on foot (from the source model's `DOORS`/`HOLES`)** — all eleven blue rooms connect:

| Room (`target`) | Reached via | On foot? |
|---|---|---|
| `639-kitchen` | front door, x 3.86…5.46 at y −15.35 | ✓ |
| `639-bath-S` | `bath-S-E-wall` door, y −14.3…−13.5 at x 2.0 | ✓ |
| `639-project-rm` | `kitchen-N-wall` door #2, x 3.95…4.75 at y −8.0 | ✓ |
| `639-guest-bed` | `kitchen-N-wall` door #1, x 2.85…3.65 at y −8.0 | ✓ |
| `639-bath-N` | ~~no doorway~~ → **door added 2026‑09‑19** (`front-strip-S-wall`, x 0.30…1.10 at y −2.0, from the guest bedroom; clear of the Daikin head at x 1.43…2.33) | ✓ |
| `639-patio-recessed` | `front-strip-S-wall` door, x 2.85…3.65 at y −2.0 | ✓ |
| `639-patio` | open to patio‑recessed (no partition at x 5.4) | ✓ |
| `640-room-2.9x3.3` | party‑wall connector, y −9.55…−8.60 at x 0 (from 639's kitchen) | ✓ |
| `640-master-bed` | `master-bed-S` door, x −2.45…−0.70 at y −6.75 | ✓ |
| `640-closet` | `bath-closet-S-wall` door #1, x −4.73…−3.93 at y −2.0 | ✓ |
| `640-bath` | `bath-closet-S-wall` door #2, x −1.15…−0.35 at y −2.0 | ✓ |

`639-bath-N` was sealed in the model (the schematic drew no door); decision taken → the door was added to
the source (`DOORS["639"]` in `~/scripts/aircon-blender.py`, 80 cm, SVG 4.8…17.6) and the level rebuilt.
The master bedroom and closet had no outline object in the source either (walls and doors were there,
just no name), so `ROOMS["640"]` gained `master-bed` (x −7.9…0, y −6.75…−2.0) and `closet`
(x −7.9…−3.75, y −2.0…0); they become `640-master-bed` / `640-closet` targets like every other room.

## Approach

One bridge‑driven script that records, one Taskfile entry, captions burnt in afterwards.

1. **Author the path once, replay it exactly.** Two phases, one script
   (`tests/record_condo_639_tour.py`):
   - **`--author`** (run once, or when geometry/pace changes): launches the tour build with the
     bridge, walks the waypoint list below with `inject_input(joystick1_raw, bits, −1)` per leg,
     polling `X/Y_POS` until the waypoint is within 0.15 m, and records how many *engine frames* each
     leg took (the bridge reports the frame counter; fall back to 60 × wall‑seconds). Output:
     `wflevels/condo_639_640/tour-639.path.json` — an ordered list of `{bits, frames, label}` legs
     plus the spawn and the accel it was authored at — **committed**, so nobody re‑walks the floor.
   - **`--record`** (the default; what `task video-condo-639` runs): launches the tour build with
     `-record_video` and the bridge, then queues the legs back‑to‑back as
     `inject_input(bits, duration_frames=N)`. Frame counts are consumed by the engine itself, so the
     replay is deterministic regardless of wall‑clock jitter and every take produces the same frames.
     No position polling during the take; a post‑take sanity check reads the final `X/Y_POS` and
     fails loudly (exit 1, no mp4 renamed) if it is > 0.5 m from the path's last waypoint — the
     signal that the path is stale and `--author` must run again.
   - Holds are legs with `bits=0`; the room label on each leg feeds the captions directly (no
     runtime room detection needed, but the bbox check in 2 stays as a cross‑check).
   On the last leg it sends `0`, waits 1 s, `SIGTERM`s the engine (the recorder finalises the mp4
   on exit — the moon/SMB recordings use the same path), and renames `output.mp4`.
2. **Captions from the path + a bbox cross‑check.** Cue times come straight from the path file
   (cumulative frames ÷ 30 fps per labelled leg) → an `.srt` with one cue per room
   (`00:03.4 → 00:06.1  639-kitchen`). During `--author` the script also parses the level's own
   `target` bboxes from `condo_639_640.lev` and asserts the player really is inside the named room
   at each hold — so a label can't lie. No engine change, no ActBox.
3. **Pace and post‑process.** The 11‑room route below is ≈76 m; at the interactive level's 1.6 m/s
   that is ≈48 s. Ground speed is OAD data (the terminal velocity of `Running Acceleration` vs `Running
   Deceleration`; calibrated 2026‑09‑19: accel 40 ≈ 1.55 m/s, ≈ accel/26), not a mailbox, so the
   tour uses its own build: `CONDO_ACCEL=105 blender … blender_create_condo.py` gives ≈4.0 m/s (a
   brisk jog — the camera follows, walls still block) and spawns at the front door `(4.66, −16.0)`,
   exported as `condo_639_640_tour` (never the interactive default). 76 m / 4.0 m/s + 11 × ~0.4 s
   holds ≈ 23 s; ffmpeg then burns the `.srt` in (`subtitles=…:force_style='FontSize=22,Outline=2'`,
   libass is built in), prepends a 12‑frame title card ("205/639 — room tour, 2026‑09‑19") and
   applies `setpts` (≈1.15×) to land at 20 s ± 1 s. `TOUR_SECONDS=30` on the task relaxes both
   (`CONDO_ACCEL=65` ≈ 2.5 m/s, no `setpts`) for a walking‑pace cut.
4. **Route** (waypoints in metres, all inside doorways with ≥ 0.2 m clearance):
   `(4.66,−16.0)` start → `(4.66,−12.0)` kitchen ⏸ → `(2.6,−13.9)` → `(1.0,−13.9)` bath‑S ⏸ →
   `(2.6,−13.9)` → `(4.35,−9.5)` → `(4.35,−5.0)` project‑rm ⏸ → `(4.35,−9.5)` → `(3.25,−9.5)` →
   `(3.25,−5.0)` guest‑bed ⏸ → `(0.7,−5.0)` → `(0.7,−1.0)` bath‑N ⏸ → `(0.7,−5.0)` → `(3.25,−5.0)` →
   `(3.25,−1.0)` patio‑recessed ⏸ → `(6.6,−1.0)` patio ⏸ → `(3.25,−1.0)` → `(3.25,−9.1)` →
   `(0.6,−9.1)` → `(−1.5,−9.1)` 640‑room‑2.9x3.3 ⏸ → `(−1.5,−5.0)` 640‑master‑bed ⏸ →
   `(−4.3,−5.0)` → `(−4.3,−1.0)` 640‑closet ⏸ → `(−4.3,−5.0)` → `(−0.75,−5.0)` → `(−0.75,−1.0)`
   640‑bath ⏸ (end).
   Straight legs only (doom‑stick strafes are axis‑aligned), each leg one joystick bit.
5. **Tasks.** `task tour-path-condo-639` (author: rebuilds the tour level, walks it, writes the
   path file) and `task video-condo-639` (deps `condo-level`; replays the path with recording, then
   ffmpeg; writes `wflevels/condo_639_640/tour-639.mp4` + `tour-639.srt`). Both idempotent via
   `sources:` (the tour standalone `.iff`, the script, the path file) / `generates:`.
6. **Verification artefacts**: the mp4, the srt, and three frames grabbed at kitchen / bath‑S /
   patio into `docs/plans/screenshots/`.

### Decision — `639-bath-N` (taken 2026‑09‑19: option a)

The brief says *all rooms*; the model sealed bath‑N. **Chosen: fix the source.** `DOORS["639"]` in
`~/scripts/aircon-blender.py` gains `("front-strip-S-wall", 4.8, 17.6)` — an 80 cm doorway from the
guest bedroom at x 0.30…1.10 m, 25 cm off the party‑wall corner and clear of the Daikin head that
hangs on that wall at x 1.43…2.33 — then `cd ~ && task aircon-blender` regenerates the `.blend` and
`task condo-level` rebuilds the level (the walls split into `…-jamb0/1/2` + two `…-door-header`
pieces automatically). The rejected fallback was a 6‑room tour with a "no door in model" caption.

## Mockups

[![Tour storyboard](2026-09-19-condo-639-tour-video/tour-storyboard.png)](2026-09-19-condo-639-tour-video/tour-storyboard.html)

Storyboard of the 20 s cut (drawn before the scope grew to the 640 blue rooms — the 639 half of the route is as shown; the 640 legs continue through the connector): the route over the 639 plan with the stops, the timeline strip
(who is on screen when), and a mock of the burnt‑in caption on a real engine frame. Toggle the
states to see the *bath‑N unreachable* variant (option b, rejected) and the title card.
[Open the interactive mockup](2026-09-19-condo-639-tour-video/tour-storyboard.html).

## Out of scope

- A tour of 640's *own* (ochre) rooms — same script, different waypoints.
- Camera moves other than the doll‑house follow (a fly‑through would need a second CamShot + ActBoxOR switching).
- Higher than 640 × 480: the Linux HAL has no `-width/-height` switch yet (TODO item exists); upscale with ffmpeg if needed.

## Verification

1. **Tour build exists.** `CONDO_ACCEL=105 CONDO_SPAWN=4.66,-16,0.3` export + build succeeds; `grep "Running Acceleration"` in the tour `.lev` shows `105`.
2. **Path authored and every room visited.** `python3 tests/record_condo_639_tour.py --author` exits 0, writes `tour-639.path.json`, and prints one `HOLD <room> frames=…` line for each of the 11 blue rooms, in route order, each with the bbox cross‑check `inside=True`.
2b. **Replay is exact.** Two consecutive `--record` runs end within 0.05 m of each other (final `X/Y_POS` printed by the sanity check) and the two `.srt` files are byte‑identical.
3. **Video length and content.** `ffprobe tour-639.mp4` → duration 19–21 s, 640 × 480, 30 fps; the `.srt` has one cue per room.
4. **Captions readable.** Frames at 3 s / 9 s / 18 s saved to `docs/plans/screenshots/2026-09-19-tour-{kitchen,bath-s,patio}.png` show the room name legibly.
5. **Re‑run is a no‑op.** `task video-condo-639` twice → second run "up to date".
