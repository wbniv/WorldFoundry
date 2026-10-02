# Lionfish

Build: `bash wflevels/aquarium_lionfish/build.sh`.

Run: `bash wflevels/aquarium_lionfish/run.sh`.

Configuration and exported assets live here; procedural geometry, controls, checks and the isolated five-tank menu preview live in [aquarium_tanks](../aquarium_tanks/README.md).

Feeding: hold DOWN, then newly press A to release one goldfish (maximum three live). A without DOWN starts a single gulp when prey is near the mouth; otherwise it keeps the swim burst. The resident detects visible prey before stalking and eating it. The three reusable goldfish share one animated mesh; both lionfish have articulated mouths. Touch-profile mode switching uses C so feeding stays on A.

Implementation, animation previews and baseline/0/1/3-prey desktop and Chromecast comparisons: [goldfish feeding plan](../../docs/plans/2026-10-02-lionfish-goldfish-feeding.md).
