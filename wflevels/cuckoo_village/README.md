# Cuckoo Village level (Classic mode, first slice)

Plan: `docs/plans/2026-11-21-cuckoo-village.md` (on branch `2026-new-level`). This branch is cut from `minute-machine`
(7242ba34) because the wall-clock mailboxes `WALL_HOUR/MINUTE/SECOND/DAY/UTC_OFFSET`, `WF_WALL_CLOCK` and the Forth math
words (`cos-rev`, `asin-rev`, `atan2-rev`, ...) exist only there.

**The art is the layout prototype's** (`wflevels/cuckoo_village_layout/`, `wflevels/cuckoo_village_assets/`, imported
unchanged from commit e5054ba2 of `feat/cuckoo-village-layout-tower`): hillside terrain, winding lanes, thirteen cottages,
the carved glockenspiel tower with four pivoted figures and the bird. `blender_create_cuckoo_village.py` runs the layout's
`generate.py` up to its review render, asserts the tower is where `timeline.py` assumes, and adds the director. A change to
the art therefore flows into this level, and a geometry change fails the build loudly instead of posing the wrong place.

## Files

| File | What |
|---|---|
| `timeline.py` | Reference: every moving pose as a pure function of the clock (dial, quarter solos, hourly parade, bird, windows, camera). |
| `forth.py` | Generates the zForth director from the same formulas. |
| `blender_create_cuckoo_village.py` | Blender (container): the layout art plus actor wiring, initial poses, director script. Writes `cuckoo_village.lev`. |
| `build.sh` | Level build: Blender, then `build_level_binary.sh`. Output `wflevels/cuckoo_village{,-standalone}.iff`. |
| `build_engine_apk.sh` | Gradle: the Minute Machine flavor APK from this branch's engine (needs `android/local.properties`, the Jolt tree; about 10 min; its `assets/cd.iff` symlink target is made with `cdpack`). |
| `build_device_apk.sh` | Swaps the level into an APK's `assets/cd.iff`, signs with the debug key. |
| `bavaria.py` | Bavaria mode's geometry (the four figures, the reversed dial's numerals, the chalet trim, the cottages' painting, the dome, the maypole), pure Python. `CUCKOO_REVIEW_RENDER=<dir> [CUCKOO_REVIEW_BAVARIA=1] [CUCKOO_REVIEW_TIME=HH:MM:SS] [CUCKOO_REVIEW_VIEWS=a,b]` makes `blender_create_cuckoo_village.py` render close-ups (Cycles, CPU) as well. |
| `../../scripts/check-cuckoo-village.py` | Desktop engine check: `--compare` against `timeline.py`, `--capture` PNGs (2048 texture slots); `--bavaria` starts the level with Bavaria mode On. |

## Verified (2026-11-21)

- `--compare` on this art at 12:00:00, 12:00:12.5 and 18:30:00: all nine animated actors within 0.009 mm and 0.005 degrees;
  the thirteen window cells and the bird's visibility cell match.
- cast1, on the earlier blockier art: the director compiles with the current engine, the camera follows its route, the
  village renders. That run is not representative of this art.

## Not done

- cast1 with this art: the APK is built but not installed, because cast1 was fenced by another session's failed `clocks`
  cleanup (needs an administrator).
- The bird's door is hidden behind the carved alcove, so the bird is shown and hidden by a visibility mailbox.
- Seasonal events other than the candles, audio, the dusk lighting blend (Bavaria mode is built: see `bavaria.py` and the plan) (the
  engine has no runtime light control; windows switch per cottage), a measured frame rate on cast1 (the tower alone is
  about 21,000 triangles), the 10% dial target on the device, and the desktop camera mismatch: in the container the engine
  camera did not follow the shot position, on the device it did. Cause not found.
