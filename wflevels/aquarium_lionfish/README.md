# Lionfish

Build: `bash wflevels/aquarium_lionfish/build.sh`.

Run: `bash wflevels/aquarium_lionfish/run.sh`.

Configuration and exported assets live here; procedural geometry, controls, checks and the isolated five-tank menu preview live in [aquarium_tanks](../aquarium_tanks/README.md).

Feeding: when the tank has no live goldfish, the Director releases one by itself after a fresh 45‑60&nbsp;s countdown (each countdown draws a new interval; the clock is held at 0 while any goldfish is live, and a hitch counts as at most 0.2&nbsp;s). Build with `LIONFISH_AUTO_GOLDFISH=0` to turn this off; the interval constants are in `aquarium_tanks/goldfish.py` ([plan](../../docs/plans/2026-11-01-lionfish-auto-goldfish.md)). You can also hold DOWN, then newly press A to release one goldfish at once (maximum three live). A without DOWN starts a single gulp when prey is near the mouth; otherwise it keeps the swim burst. The resident detects visible prey before stalking and eating it. The three reusable goldfish share one animated mesh; both lionfish have articulated mouths. Touch-profile mode switching uses C so feeding stays on A.

Implementation, animation previews and baseline/0/1/3-prey desktop and Chromecast comparisons: [goldfish feeding plan](../../docs/plans/2026-10-02-lionfish-goldfish-feeding.md).
