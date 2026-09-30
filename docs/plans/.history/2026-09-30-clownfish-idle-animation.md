| Date | Change |
|------|--------|
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/2b64afc1) | Add canonical aquarium clownfish with a Forth-driven idle rig |

<!--history-meta v1
2b64afc1	author	Will Norris
2b64afc1	added	357
2b64afc1	deleted	0
2b64afc1	files	1
2b64afc1	body	The clownfish is defined once in wflevels/aquarium/clownfish.py plus\nclownfish_idle.fth: a mockup-accurate flat-shaded model split into five\nparts, Phase 1's measured swim controls, and an authored symmetric\ncollision box. The Player is an invisible Physics hull; the Director\nposes five Mass-0 anchored platforms each tick from Forth (bob, sway,\ntail beat, pectoral flutter, dorsal ripple). It blends with swimming\nthrough a smoothstepped idle weight and phase accumulators. The idle\nnever writes the Player's speed, position or rotation.\n\nFindings recorded in the plan:\n- ROTATION_* writes work on Physics, statplat (Director) and anchored\n  platform actors. A/B only commit on the C write.\n- Every statplat gets a Jolt static body whatever its Mass, so a\n  statplat body part pinned the Player's capsule.\n- The bungee camera aims at its Track Object.\n\nSpike level wflevels/aquarium_idle, IDLE_PROBE=1 rotation probe,\nTaskfile entries, mockup, engine captures and\ntests/test_aquarium_idle.py.\n\nPlan: docs/plans/2026-09-30-clownfish-idle-animation.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
-->
