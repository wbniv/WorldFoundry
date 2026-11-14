# One snowgoon in the classic yard — 2026-11-14

Will requested one snowgoon after the one-acre yard installation.

`wflevels/snowgoons-blender/make_snowgoon.py` reuses the original `snowman01.iff`
two-headed model (147 vertices / 200 triangles), centring its horizontal pivot
and putting its base at local Z 0. The source mesh, materials, textures and face
winding are retained. Its generated copy is `snowgoon.iff`.

One actor named `Snowgoon` is appended to the classic `.lev`, preserving existing
actor indices. It uses the existing Enemy class with Physics mobility at
**(5, −3, −0.60)**, beside the player's starting area. It is about **2.20 m tall**.
It stands in place; no movement AI or animation was added. Gravity settles it on
the lawn. The old path-driven enemy is retained.

`task snowgoons-level` regenerates this actor/model along with the yard, and
rebuilds the inner, standalone and CD bundles. A second generation is idempotent.
All **9 asset tests pass** (`tests.txt`), including exactly one embedded copy of
the generated model in each bundle. A 60-frame desktop engine smoke test exits
cleanly; [opening.png](opening.png) shows the placement. No engine source changed.

The rebuilt APK changes only `assets/cd.iff`; native libraries and Java payloads
are unchanged. Its identity is in `build-receipt.json`. The normal Snowgoons
release output has also been updated so future default installs use this level.
The previous base APK is preserved under `build-docker/snowgoon-2026-11-14/`.

Installation hashes are verified on all four devices. The `DEVICE=all` batch
was B‑aca3823da848: cast2, Pixel and tablet installed successfully. Cast1's
background install was refused because Snowgoons was foreground; the normal
coordinator check J‑e24074e8844d then installed and verified it. Pixel's launch
verification was blocked by its lock screen, after its installation succeeded.
See [installation-summary.json](installation-summary.json). The prior arena's performance measurements remain
historical evidence for that earlier scene; no new performance claim is made for
the added actor.


## Pixel unlocked follow-up

After Will unlocked the Pixel, coordinator check J‑ef936d1a750f passed. The
installed APK hash matches the snowgoon build, and the captured frame was
reviewed: the snowgoon is visible on the lawn. The earlier lock-screen
verification block is cleared. The job receipt and APK hash verification are
saved in `pixel-unlocked-check/`; full captures remain in coordinator evidence.
