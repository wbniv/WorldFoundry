# Calm Betta

Build: `bash wflevels/aquarium_betta/build.sh`.

Run: `bash wflevels/aquarium_betta/run.sh`.

Configuration and exported assets live here; procedural geometry, controls, checks and the isolated menu preview live in [aquarium_tanks](../aquarium_tanks/README.md).

The detailed opaque betta has a body and seven independently deforming fin meshes. UV coordinates encode fin roots and free edges; bounded zForth clocks drive cached native bending, curl and damped spread. Existing movement bindings remain, with a restrained 1.15-unit/s action pulse. Back returns to the tank selector; Back on that selector exits.

[Implementation, actual motion capture and measurements](../../docs/plans/2026-10-02-betta-poster-and-flowing-fins.md). `BETTA_FINS=0` builds the original four-part model for isolated comparison.
