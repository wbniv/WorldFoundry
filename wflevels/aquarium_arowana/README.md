# Asian Arowana

One opaque green/gold Asian arowana, ten anatomical rig groups and roughly 6,200 triangles, in a bare 4 × 3 × 1.2 m tank at ×10 world scale. Nose-to-tail length is 65 cm; barbels extend the clearance envelope. Dimensions, spawn and cameras are in `config.py`; geometry and rig generation are in `../aquarium_tanks/arowana.py`, with the species controller in `../aquarium_tanks/arowana_motion.fth`.

Build: `bash wflevels/aquarium_arowana/build.sh`. Run: `bash wflevels/aquarium_arowana/run.sh`. The default remote profile uses directions to steer, OK for a brief burst, and hold Up then press OK to switch Side/Depth mode. Switching requires neutral/repress. Holding OK cannot stack bursts. `TANK_PROFILE=touch` uses A=Mode/B=burst; `TANK_PROFILE=keyboard` is also available. Desktop depth keys remain usable in the remote profile.

Motion stays along current facing. Cruise turns have a length-dependent radius, reversals brake into an inward turn, and predictive braking reserves room for the complete animated silhouette. Pitch and bank are bounded. Every appendage shares the body's rest frame and posterior wave; fin edges add independent root-weighted flex through the generic `swim-deform` renderer operation. Existing fish and Betta deformation operations remain available.

Verification: `python3 -m pytest tests/test_arowana_motion.py tests/test_swim_deform.py tests/test_aquarium_arowana.py -q` (11 passed). The shared workspace also passed existing fish/Betta deformation regressions (19 tests including Arowana). `python3 scripts/check-arowana.py --video` captures the real desktop engine: six directions, reversal, release, corners, burst recovery and mode switching. Its 194 sampled poses passed facing, curvature, attachment and full rotated-envelope clearance checks, with minimum measured clearance 0.344 world units. Analytical mesh tests bound all permitted wave/fin phases and orientations. The capture is a sampled motion review, not a hardware performance measurement.

The shared seven-tank selector places Asian Arowana at index 6 and retains indices 0–5. Menu packaging remains with the other pending level work; this standalone rebuilds independently using its own generator. A rebuilt engine is required for the additive deformation primitive.

Physical remote behavior, lifecycle/device profiling and Chromecast deployment remain pending. [Implementation and evidence](../../docs/plans/2026-10-02-asian-arowana.md) · [Shared controls plan](../../docs/plans/2026-10-02-aquarium-movement-and-controls.md).
