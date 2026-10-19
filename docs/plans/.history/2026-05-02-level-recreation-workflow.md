| Date | Change |
|------|--------|
| [2026-05-02](https://github.com/wbniv/WorldFoundry/commit/6eab4dfe) | feat: Blender scripts + standalone IFF wrappers for MM Intermediate/Aerial/Silly/Ultimate |
| [2026-05-02](https://github.com/wbniv/WorldFoundry/commit/a32dce6b) | feat: Practice level (mm_practice_rom) — ROM-derived crowned S-curve |

<!--history-meta v1
6eab4dfe	author	Will Norris
6eab4dfe	added	4
6eab4dfe	deleted	4
6eab4dfe	files	1
6eab4dfe	body	Adds blender_mm_{intermediate,aerial,silly,ultimate}.py and matching\n*-standalone.iff.txt wrappers for the four remaining Marble Madness\nlevels; uses the same rom_to_blender.py / build pipeline as Practice.\n\nKey per-level differences: room bbox sized from path+camera extents,\nrespawn Z set above each level's floor height (1–3 m), timers match\narcade originals (40/35/20/55 s). Ultimate seg12 has h_left==h_center\n(open crowned section) — handled by rom_to_blender.py's existing\nwall-skip logic, confirmed by geometry validation.\n\nUpdates plan doc Level Status table.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
a32dce6b	author	Will Norris
a32dce6b	added	178
a32dce6b	deleted	0
a32dce6b	files	1
a32dce6b	body	blender_mm_practice_rom.py builds the Practice level from levels.json:\n- Spawn at seg 0 (crowned ridge, open-sided — player must steer)\n- 60s timer; respawn at (0,0,1) when Z < -2\n- Room bbox expanded for deep fall zone (world Z_min -5.5m)\n- SW isometric camera (-6,-8,+10 offset) with cam-remap\n\nrom_to_blender.py: skip wall faces when h_edge == h_center at either\ncross-section end — prevents zero-area faces on Practice seg 3 (h_L==h_C=28)\nthat crashed Vector3::Normalize() with a zero-length assertion.\n\nmm_practice_rom-standalone.iff.txt: L4 wrapper puts RAM\0 at sector 1\n(offset 2048) matching what game.cc expects from the -L flag load path.\n\ndocs/plans/2026-05-02-level-recreation-workflow.md: full workflow doc\ncovering ROM extraction, converter, build pipeline, standalone IFF gotcha,\nroom sizing rules, and per-level status table.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
