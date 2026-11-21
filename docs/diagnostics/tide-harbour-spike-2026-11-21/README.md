# Tide Harbour Phase 0 spike, desktop half — 2026‑11‑21

Plan: [Tide Harbour](../../plans/2026-11-21-tide-harbour-clock.md), Phase 0 (a) and (b). Sources: [`wflevels/tide_spike/`](../../../wflevels/tide_spike/spike.py). Rebuild with `bash wflevels/tide_spike/build.sh`; run with `wflevels/tide_spike/run_desktop.py` (the Linux container engine, under xvfb).

**What this is, and is not.** Four throwaway levels run in the Debug-and-ASan engine in the container, drawn by Mesa's software GL. **It is not a Chromecast measurement.** Absolute frame times mean nothing here; only the *relative* cost of one variant against another and the *look* do. The cast1 half (the real frame rate and whether the water bars band on the TV) has not been run: it needs an APK.

## The four variants

| Variant | Posed actors | What it tests | Median frame, ms | 90th percentile, ms |
|---|---|---|---|---|
| a | 46 | 36 water bars, 3 boats, hands, sun, moon, a few fillers | 20.6 | 31.4 |
| b | 100 | the same, with more fillers | 23.5 | 30.6 |
| c | 150 | the plan's actor budget (D7) | 35.6 | 48.4 |
| d | 150 | variant c on a fast day (240 s), with day-to-night veils and glow overlays | 33.6 | 42.9 |

Raw results are in [`desktop-runs.json`](desktop-runs.json). Every run had `director_running`, `bar_18_z_moved` true (the director's pose reaches the engine), and no engine log problems. The cost rises with the number of posed actors; variant d, with a translucent full-screen veil, is no slower than c in software GL, which says nothing about a Chromecast.

## Finding 1: day to night with no light control works

![The harbour at seven hours of the fast day: 06:00, 12:00, 17:00, 18:15, 19:30, 23:00 and 05:00](day-fast-clock.png)

Nine translucent veils (three warm, six night blue, each a box of fixed opacity in front of the camera) and one director that shows exactly one at a time through its visibility mailbox turn the scene from day to dusk, night and pre-dawn in clean steps. Lit windows and lantern glows, drawn in front of the veils, stay bright. The director's cells matched the code at each photographed hour (18:15: darkness 0.50, veil 5; 19:30: darkness 1.0, veil 9; 05:00: darkness 0.80, veil 7).

What the captures also show, for the plan:

- the tower **dial is dimmed** at night and its hands are hard to read; it needs the same drawn-in-front treatment as the glows;
- the **moon is dimmed** too, for the same reason;
- the warm sunset veils (1 to 3) were not photographed: at 17:00 the scene is still full day and at 18:15 it is already veil 5; and there is no warm glow along the horizon, which a veil cannot give;
- **faint horizontal lines** show across the daytime water. That is the banding the spike was meant to look for; software GL at 1280 × 720 is not the TV.

## Finding 2: the guide's lighting recipe has the wrong sign

[`lighting-sweep.json`](lighting-sweep.json), from [`measure_lighting.py`](../../../wflevels/tide_spike/measure_lighting.py). Five sun settings (the pale-blue sky box and ambient 0.5 are the same in all); each number is how lit a face of known normal is (rendered colour ÷ authored colour; 0.50 is ambient alone):

| Euler B, C (degrees) | pier top (+z) | pier front (−y) | tower left (−x) |
|---|---|---|---|
| −50, −70 (what `docs/level-building.md` said) | 0.50 | 0.50 | 0.68 |
| +40, +90 | 1.00 | 1.10 | 0.52 |
| −50, +110 | 0.50 | 0.97 | 0.52 |
| +50, −70 | 1.10 | 0.50 | 0.68 |
| +50, +110 | 1.10 | 0.97 | 0.52 |

All fifteen readings agree with one rule: a face is lit when its normal opposes the vector (cos B·cos C, cos B·sin C, −sin B). So **B = +alt tilts the light down**, the reverse of the sign in the guide. The guide's text was measured on 2026‑09‑20 and the engine's face-normal hand was reversed on 2026‑10‑16; that is the likely cause and was not tested. [`level-building.md`](../../level-building.md#lighting--every-level-needs-directional-and-ambient) and the [troubleshooting guide](../../level-design-troubleshooting.md) are corrected.

An earlier version of this sweep gave identical results for every setting, because the knob never reached the Blender container (the build forwards only `TANK_*`, `AQUARIUM_*`, `LIONFISH_*`, `BETTA_*`, `PLANTED_*` and `SHRIMP_*`). That is now a troubleshooting entry too.

## What was not found or not measured

- cast1: real frame rate for 46, 100 and 150 posed actors, the cost of a full-screen translucent veil, and banding on the TV.
- Whether a zero-thickness quad is invisible (the troubleshooting guide says a thin object can be). The spike used boxes of real depth and never tested the quad.
- Which near plane rules: `display.cc` passes 1.0, the baseline authors a CamShot `Hither` of 0.1.
- Anything at the real 1080p resolution.
