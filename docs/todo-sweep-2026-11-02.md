# TODO Open-items staleness sweep, 2026-11-02

Will asked for a staleness sweep of the Open items (2026‑11‑02: "staleness sweep next") and said to go with the recommendation. `origin/2026-new-level` held 83 Open items. Checks per item: do the files it names still exist; does a commit subject or a Done line match its title; does its own plan say it is done; then a read of the plausible candidates against the code. The blame dates are mostly 2026‑09‑21, from an earlier bulk sweep, so they say nothing about age.

## Changed

| Item | Outcome | Evidence |
| --- | --- | --- |
| Chromecast/Google TV Phase 2 (`[T5]`) | Retired | Its plan ([chromecast-googletv-port](plans/2026-04-23-chromecast-googletv-port.md)) says Phase 2 "needs Android phone hardware"; a Pixel 8 Pro and two Chromecasts are now enrolled in the coordinator and used for verification daily. The plan's Phase 2 steps were not individually confirmed, so reopen this if a step is missing. |
| Condo wall shading is flat (`[T3]`) | Reworded | The plan says the second fill light "is shipped gated off behind `CONDO_FILL_INTENSITY=0`", and the seam-darkening pass landed in `39e5310d` (2026‑09‑20). What remains is the decision to enable it. |

Retired item, verbatim:

> - [T5] **Chromecast/Google TV Phase 2** — on-device verification on physical hardware + CI (banner image already shipped). [plan](docs/plans/2026-04-23-chromecast-googletv-port.md)

Reworded item, before:

> - [T3] **Condo wall shading is flat — walls/corners/ceiling seams unreadable.** Floor darkening (shipped) only separates floor from wall; wall-to-wall corners and the wall/ceiling line are still one flat colour because the scene uses only 1 of the engine's 3 directional light slots and the engine has no shadows/AO. Add a 2nd fill directional light + generalize `darken_floors()` into a seam-shade pass + small ambient trim, all in `blender_create_condo.py`. [plan](docs/plans/2026-09-20-condo-wall-shading-definition.md)

## Checked and still valid

Tech debt `__LINUX__` guards (88 occurrences in 35 files); `long` to `int32` in `gfx/gl/wfprim.h` (`Point3D` still has `long x,y,z`); stale OAD generation in `wflevels/oad` (24 of 27 `.oad` files differ from `wfsource/source/oas`); OAD fixtures in the test path (`blender_create_qbert.py` lines 46 to 47); stale `cd_full.iff.txt`; aquarium schooling (plan `proposed`, Phase 1 only); macOS `-fullscreen` (needs a person on a Mac); snowgoons arena `[verify T1]` (one Codemagic run left, Mac-minute cap 400 a month).

## Not examined by hand

About 55 items (condo, filesystem visualization, editor, physics, game ideas and others). Their named files exist and no commit or Done line matches them. That is weak evidence of being alive, not proof, and the title match is loose.
