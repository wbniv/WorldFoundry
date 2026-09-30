# Condo 639: motorised zip screen on the back balcony

## Context

The back balcony of 639 is an open opening onto the west (Bangkok afternoon sun, monsoon rain, gusts, 6th floor ≈ 16 m up). Will wants a **motorised outdoor zip screen in a cassette, mounted under the concrete ledge (beam) of the opening**, with the **solar-strip motor option** (battery motor charged by a thin photovoltaic strip — no mains wiring to the balcony).

Measured by Will (2026‑09‑30):

| Item | Value |
|---|---|
| Opening width | 268 cm |
| Opening height (pony-wall cap → beam soffit) | 111 cm |
| Pony wall height | 111 cm |
| Concrete beam / slab face above the opening | 35 cm deep |
| Floor in front of the opening | recessed **7 cm** below the interior floor |

**The level model does not match these numbers today** (queried read-only from `~/docs/aircon/units-639-640.blend`, `unit-639` shell, y = 0 plane):

- The patio rooms are `639-patio-recessed` (x 2.70–5.40) and `639-patio` (x 5.40–7.80), both floored at z = 0, ceilinged at z = 2.70.
- The open edge is a **1.00 m parapet** (x 2.65–5.85, y −0.10…0) with **nothing above it** up to the 2.70 m ceiling, i.e. a 1.70 m opening and no beam. A full-height wall starts at x 6.55.
- A full-height post stands at x 5.70–5.80, so the parapet run is 2.75–5.70 = 2.95 m clear, not 2.68 m.
- Real stack 111 + 111 + 35 = **257 cm**; the model's ceiling is 270 cm.
- The Daikin outdoor unit hangs *outboard* of the parapet at x 2.76–3.56, y 0.19–0.49, z 0.30–0.85; its lineset and drain cross y = 0 at the left end, below the parapet cap.

So the plan has two halves: **(A) the real-world spec** Will can take to a supplier, and **(B) the level model** corrected to the measurements, with the shade built into it and operable.

## Approach

### A. Real-world spec

Product class: **outdoor zip screen, cassette (head box) on the soffit, inside-reveal mount, solar-strip battery motor with RF remote**.

| Parameter | Recommendation | Why |
|---|---|---|
| Order size | ≈ 267 × 111 cm **overall, cassette included** | 268 cm clear less ~5 mm per side; supplier deducts for guides. Measure the clear width at three heights and order to the smallest |
| Cassette | ≈ 10 × 10 cm, aluminium, flush under the soffit | A 111 cm drop rolls to a small diameter; the cassette costs ≈ 10 cm of the opening, so the fabric drops ≈ 98 cm |
| Guides | zip tracks on both reveals, ≈ 5 cm wide each | Keep the fabric taut in gusts; fabric width ≈ 257 cm |
| Bottom bar | ≈ 3 cm, with rubber seal, lands on the pony-wall cap | Cap must be flat and level — a 0–10 mm error shows as a gap along 2.6 m |
| Fabric | 3–5 % openness, light exterior colour | Heat rejection matters more than see-through in Bangkok; darker fabric keeps more view but passes more heat |
| Wind | ask for the supplier's **EN 13561 class** and the **test size**; it must cover 2.67 × 1.11 m | A 6th-floor west face takes squall gusts; do not accept a class without the test size |
| Motor | battery tubular motor, **solar strip** on the cassette's west face, plus a **DC/USB charge port** | Monsoon weeks give little sun; a charge port is the fallback |
| Battery | ask for chemistry and **operating temperature** | The cassette sits in direct afternoon sun at 35 °C+ ambient; a cell that is only rated to 45–60 °C ages fast |
| Control | RF remote + wall/phone bridge; optional wind/sun sensor | Sensors also need power: check they are solar too |

**Solar strip placement.** The balcony faces due west, so a vertical strip on the cassette's outer face sees direct sun only from roughly midday on, and edge-on near solar noon (see the section mockup). Morning charge is diffuse. Ask the supplier for the strip's Wp, the battery's Wh, and the cycles per day it is rated for; a 111 cm drop is a small load, which is why this option is plausible here.

**Anchoring.** Side guides bolt into the concrete reveals; the cassette hangs from the soffit. Both need the wall thickness (see Open questions).

### B. Level model (`blender_create_condo.py`)

The source `.blend` is read-only, so all of this is a new section (**§ 7d**) in `wflevels/condo_639_640/blender_create_condo.py`, following the pattern of § 7c (telescoping glass doors) and gated by `CONDO_SHADE=0` to switch it off.

1. **Pin the opening.** Constants in metres, all derived from Will's numbers: `SHADE_W = 2.68`, `PONY_H = 1.11`, `OPEN_H = 1.11`, `BEAM_H = 0.35`, `FLOOR_RECESS = 0.07`, plus `SHADE_X0` (see Open questions).
2. **Recess the floor 7 cm** across the opening's frontage. The shell floor is a single z = 0 face set inside `unit-639`, so this is a `bmesh` bisect of the top faces over the rectangle, dropping the cut region by 0.07 m and closing it with a step wall on the interior side. The player walks down 7 cm; Jolt's character step handles that.
3. **Rebuild the opening** as solid geometry: parapet raised from 1.00 m to 1.11 m over the shade span; a **beam** over the span with its soffit at the opening head; infill piers where the model's 2.95 m run is wider than 2.68 m.
4. **Build the shade** as separate actors:
   - `639-balcony-shade-cassette` (static box with the solar strip as a second material on its west face, the strip length a placeholder);
   - two static guide boxes on the reveals;
   - the **fabric as N = 8 horizontal slats** (`statplat`, each ≈ 12 cm tall, 3 mm thick, 1 mm apart in Y to avoid coplanar z-fighting) plus the bottom bar riding the last slat.
5. **Motion.** Slat *i* is baked at the *closed* position; at closedness *c* the Director writes `INDEXOF_Z_POS` = `(1 − c) × (i + 1) × slat_h` upward, so at *c* = 0 all slats collapse into the cassette (hidden inside its closed box) and at *c* = 1 they tile the drop. This avoids per-vertex scale, which the engine does not support for a Jolt-backed mesh. It reuses the § 7c machinery: a closedness mailbox integrated by `DELTA_TIME`, a target toggled by **B / keyboard 2** when the player is within reach of the opening, `write-actor-mailbox` for each slat, and runtime actor indices resolved in § 9c the same way as the door panels (`DOOR_ACTOR_IDX_BIAS`).
6. **Collision.** Slats are ordinary statplats; the pony wall already blocks the player, so their collision is harmless. No engine change.
7. **Camera.** `BALCONY_CAM` sits 1.5 m ahead of the player at 1.7 m; with the parapet at 1.11 m and the shade closed the balcony POV is partly blocked, so the shot is checked closed and open (Verification 6).

Rejected: a two-state visibility swap (open/closed with no travel) — cheap but it cannot show the roll, and the door interaction already proves a continuous version works.

## Mockups

[![Elevation from inside](2026-09-30-condo-balcony-shade/elevation.png)](2026-09-30-condo-balcony-shade/elevation.html)

**Elevation** — the 268 × 111 cm opening with cassette, zip guides, solar strip, fabric and bottom bar; buttons switch open / half / closed. [Open the interactive mockup](2026-09-30-condo-balcony-shade/elevation.html).

[![Section through the opening](2026-09-30-condo-balcony-shade/section.png)](2026-09-30-condo-balcony-shade/section.html)

**Section** — the 7 cm floor step, pony wall, cassette under the soffit, beam, and a sun-altitude slider to judge what the west-facing strip sees. [Open the interactive mockup](2026-09-30-condo-balcony-shade/section.html).

The in-engine states (open, half, closed, seen from the balcony POV and from the doll-house camera) are captured during Verification and appended here.

## Open questions

Each has a default that the build uses until Will corrects it; all are constants at the top of § 7d.

1. **Datum for 111 / 111 / 35.** Default: measured from the **recessed** balcony floor, so the cap is 1.04 m and the soffit 2.15 m above the *interior* floor. If measured from the interior floor, both move up 7 cm.
2. **Ceiling.** 257 cm from the balcony floor is 250 cm above the interior floor, but the model's patio ceiling is 270 cm. Default: the beam is modelled from the true soffit (2.15) up to the model ceiling (2.70), i.e. taller than 35 cm, so the level stays watertight; the 20 cm is a model artefact, not a claim about the building.
3. **Where the 268 cm sits.** The model's parapet run is 2.95 m (x 2.75–5.70). Default: centred, x 2.891–5.559, with 14 cm piers each side. Lineset and drain cross below the cap at the left end, so none of the choices collide with the shade.
4. **Wall / beam thickness.** The model has 10 cm; unmeasured. It decides whether the 10 cm cassette sits inside the wall's thickness or is surface-mounted, and which face the screen closes on.
5. **Reveal condition.** Are the two side reveals flat, plumb concrete/plaster? Guides need ≈ 5 cm of flat face each side.

## Out of scope

- Choosing a supplier or price; this plan fixes the spec, not the purchase.
- Shading the *interior* side or the other patio room (x 5.40–7.80, full-height wall).
- Weather in the level (rain, wind on the fabric).
- Adding the balcony's real slab thickness, drainage falls or waterproofing lip under the 7 cm recess.
- A solar-yield model tied to `SUN_ALT_DEG` / `SUN_AZ_DEG`; the existing sun-position item ([plan](2026-09-20-condo-sun-solar-position.md)) is the prerequisite.

## Verification

1. `CONDO_SHADE=1 task condo-level` completes and prints a `[condo] balcony shade:` line giving the span, cassette, slat count and mailboxes.
2. A headless read of the built `wflevels/condo_639_640/condo_639_640.blend` reports: floor z = −0.07 over the frontage, pony-wall cap z = 1.04, soffit z = 2.15, clear opening width 2.680 m, and 8 fabric slats plus the bar.
3. `CONDO_SHADE=0 task condo-level` reproduces today's level (same parapet, no beam, floor at 0).
4. `task run-condo`, spawn on the balcony (`CONDO_SPAWN`): stepping down onto the balcony works, and the player cannot walk through the pony wall or the guides.
5. In-engine capture at closedness 0, ~0.5 and 1.0 (`-rate20 --capture-frame`): slats tile without gaps or z-fighting at 1.0 and vanish into the cassette at 0.
6. Balcony POV shot (`cs_balcony`) and the doll-house shot are captured with the shade open and closed; the view is not blocked when open.
7. Pressing B (keyboard 2) within reach toggles the shade over about 2 s; a second press mid-travel reverses it smoothly; out of reach does nothing.
8. **On site, before ordering:** measure the clear width at top, middle and bottom, the pony-wall cap level along its length, the wall thickness, and the datum for the three heights (Open questions 1–5); update the constants.
