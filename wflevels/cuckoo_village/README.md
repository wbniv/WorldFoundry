# Cuckoo Village level (Classic mode, first slice)

Plan: `docs/plans/2026-11-21-cuckoo-village.md` (on branch `2026-new-level`). This branch is cut from `minute-machine`
(7242ba34) because the wall-clock mailboxes `WALL_HOUR/MINUTE/SECOND/DAY/UTC_OFFSET`, `WF_WALL_CLOCK` and the Forth math
words (`cos-rev`, `asin-rev`, `atan2-rev`, ...) exist only there. The tree, house, tower, hands and bird-door models are
reproduced from the asset prototype `wflevels/cuckoo_village_assets/` (another session's files, untracked in the main
checkout); this level builds on its own.

## Files

| File | What |
|---|---|
| `timeline.py` | Reference: every moving pose as a pure function of the clock (dial, quarter solos, hourly parade, bird, windows, camera). |
| `forth.py` | Generates the zForth director from the same formulas. |
| `blender_create_cuckoo_village.py` | Blender (container): village, figures, bird, actors, director script. Writes `cuckoo_village.lev`. |
| `build.sh` | Level build: Blender, then `build_level_binary.sh`. Output `wflevels/cuckoo_village{,-standalone}.iff`. |
| `build_engine_apk.sh` | Gradle: the Minute Machine flavor APK from this branch's engine (needs `android/local.properties`, the Jolt tree; about 10 min). |
| `build_device_apk.sh` | Swaps the level into an APK's `assets/cd.iff`, signs with the debug key. |
| `../../scripts/check-cuckoo-village.py` | Desktop engine check: `--compare` against `timeline.py`, `--capture` PNGs. |

## Verified (2026-11-21)

- `--compare` at 12:00:00, 12:00:12.5 and 18:30:00: all ten animated actors within 0.013 mm and 0.005 degrees, window cells match.
- cast1 (Chromecast HD), Minute Machine flavor APK from this engine with the village level: the director compiles, the
  camera follows its route, the whole village renders.

## Not done

Bavaria mode, December and the other seasonal events, `CuckooVillageSettings`, audio, the dusk lighting blend (the
engine has no runtime light control; windows switch per house), a measured frame rate on cast1, the 10% dial target
in the front view on the device, and the desktop camera mismatch: in the container the engine camera did not follow
the shot position, on the device it did. Cause not found.
