| Date | Change |
|------|--------|
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/be6694e9) | codemagic: aquarium Metal-vs-GL frame parity step (informational), Linux reference, static test |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/819f6a9a) | Save the aquarium Phase 4 motion demo in tests/recordings |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/2a9f1868) | aquarium plan: Phase 4 verification (steps 16-20), re-runs of 12-15, verdict, tables, controls |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/8a48df87) | Aquarium Phase 3: canonical clownfish, swim/dart controls, camshot B, touch profile |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/68499439) | Aquarium Phase 2: tank, sand, rock, anemone, lighting, fog (static scene, placeholder fish) |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/52a5bfe6) | Aquarium plan: Player is an invisible collision hull; visible clownfish is five Director-posed parts |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/6d902226) | Run aquarium Phase 1 swim-and-scale spike: gravity-free fish works at x10 |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/2b485281) | Aquarium: idle-spike clownfish becomes the canonical model; commit mockup generator |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/4e5ce347) | Aquarium: go with Plan B (no front pane); file translucent-texture shader fix as its own TODO |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/1aa8e779) | Run aquarium Phase 0 translucency spike: pane is opaque, fall back to Plan B |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/f964a400) | Plan aquarium level (55 gal acrylic, clownfish, anemone) and correct condo alpha note |

<!--history-meta v1
be6694e9	author	Will Norris
be6694e9	added	51
be6694e9	deleted	0
be6694e9	files	1
be6694e9	body	macos-desktop-debug gains "Compare aquarium capture with Linux reference\n(informational)": the snowgoons method (30 steps, 1 cycle, -rate20, frame 20,\n--tolerance 3) on wflevels/aquarium-standalone.iff. It never fails the build;\nit prints AQUARIUM PARITY: MATCH/DIFFERS with the differing-pixel count and the\nmaximum channel delta so a tolerance can be chosen from real numbers.\n\ntests/fixtures/renderer/aquarium-linux-frame20.png is the Linux GL capture,\nbyte-identical across three runs. tests/test_codemagic_aquarium_parity.py pins\nthe yaml, the referenced files, the artifacts and the verdict block (driven with\na stub wf_game). Plan step 21 records the Linux half; the macOS half is pending\nthe first Codemagic run.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
819f6a9a	author	Will Norris
819f6a9a	added	3
819f6a9a	deleted	3
819f6a9a	files	1
819f6a9a	body	The steer-and-swim demo (33.9 s, 640x480, real time, CLEAN run) only lived in\n~/tmp, which disk-hygiene ages out after 14 days. Commit it with its .srt and\nsegment list, and correct the "not committed" wording in the recorder, the\nlevel notes and the plan. The recorder still writes to ~/tmp by default.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
2a9f1868	author	Will Norris
2a9f1868	added	483
2a9f1868	deleted	18
2a9f1868	files	1
2a9f1868	body	Steps 16 (sway), 17 (hosting/containment on the 18-tentacle crown), 18 (cost: 14.3 -> 11.1 ms vs\nPhase 3's 9.7, cause located with one-change variants), 19 (frames vs mockups, differences listed)\nand 20 (steer-and-swim traces, motion strips), all from CLEAN paused/stepped injected-input runs.\nSteps 12, 13 and 15 point at the step-17 re-run; step 14 re-run on steer and swim. Phase 4 verdict\nwith tuning maths, sources opened vs not, adopted/rejected constants, deviations and residuals;\nfiles/actors tables, section 4 controls, sections 5-7 as built, regression guard, sway risk row.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
8a48df87	author	Will Norris
8a48df87	added	298
8a48df87	deleted	14
8a48df87	files	1
8a48df87	body	Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 3 verdict; steps 12, 13, 15 PASS,\nstep 14 logic-verified, hardware unverified).\n\n- blender_create_aquarium.py: the placeholder fish is gone; the Player is the canonical\n  clownfish's invisible Physics hull, followed by the five Mass-0 anchored platform parts\n  posed by the Director (fish-rig-tick). Camshot B (cs_anemone) aims at LookB, which the\n  Director leans toward the fish; zone switch with hysteresis (in 2.2 m, out 2.5 m).\n  AQUARIUM_PROFILE=keyboard|touch. Infrastructure actors are Mass 0.\n- aquarium_swim.fth (new): swim controller with the Phase 1 values, the dart, clamps from\n  extents() (±1 mm tolerance: 16.16 read-back), a floor clamp with 0.15 m ground clearance,\n  and no uncommanded acceleration (Jolt's walker stair-stepped the fish off the rock at 7 m/s).\n- Anemone split: the body collides, and anemone-tentacles is a non-colliding platform, so the\n  fish can host from any depth.\n- clownfish.py takes WORLD_SCALE and FISH_LEN from aquarium_constants.py (single source);\n  player_script/director_script take defs=/entry= (zForth runs only the text after the last\n  `;` each tick). The idle spike was rebuilt.\n- run_aquarium_checks.py: paused, per-tick stepping with sticky injected input (hermetic),\n  steps 11-15 plus --profile touch and --trace-sand.\n- tests/test_aquarium_level.py: 19 tests (Player first, parts, camshots, zone, clamps,\n  constants agree, no placeholder).\n- Taskfile: aquarium-touch-level; aquarium-level/aquarium-idle-level track the new sources.\n- docs/level-building.md: script compile semantics, fixed-point clamps, gravity-free\n  CharacterVirtual, camera bbox vs Mass > 0 actors in bungee mode.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
68499439	author	Will Norris
68499439	added	180
68499439	deleted	20
68499439	files	1
68499439	body	New level wflevels/aquarium/ at WORLD_SCALE 10, Plan B (no front pane, nothing translucent):\none-piece tank-shell with water/water-line/air inner faces, invisible front collider, chamfered\nrim, faceted sand, low-poly rock, static bubble-tip anemone with back/front tentacle sets\n(+-0.36 m gap, verified the fish passes between them untouched), anemone-zone target, stand and\nbackdrop, Directional + cool Ambient, teal fog 6->40 m, locked camshot A at y -11 m.\nPlaceholder Player (Phase 1 fish, recentred, authored symmetric bbox, X/Z clamps) marked\n"# PHASE 3: replace with wflevels/aquarium/clownfish.py".\n\nAdds aquarium_constants.py, aquarium.md, run_aquarium_checks.py (frame A + walls over the\nbridge, reusing the swim spike's Session, flags desktop-input contamination), Taskfile\naquarium-level / run-aquarium, tests/test_aquarium_level.py (regression guard, Plan B form).\nPlan: verification steps 9, 10, 11, 13 recorded (all PASS), Phase 2 verdict, actor/files tables.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
52a5bfe6	author	Will Norris
52a5bfe6	added	20
52a5bfe6	deleted	8
52a5bfe6	files	1
52a5bfe6	body	Adopts the idle spike's design (merged): anchored platform parts posed by\nfish-rig-tick, no ROTATION_C writes on the Player, statplat parts forbidden\n(every statplat gets a Jolt body), mailboxes 600-627 reserved for the fish.\nUpdates the actor table, section 4 and verification step 15. Also refreshes the\naquarium TODO entry's agent stamp.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
6d902226	author	Will Norris
6d902226	added	233
6d902226	deleted	9
6d902226	files	1
6d902226	body	A Physics fish with Falling Acceleration 0 holds altitude exactly for 10 s, rises\nand stops on a Forth Z clamp under the water line, stops on the sand and at every\nwall (including an invisible front collider for Plan B), and turns visibly when\nthe script writes ROTATION_C (in revolutions). Driven over the debug bridge with\nframe-exact held buttons by wflevels/aquarium_swim_spike/run_swim_spike.py.\n\nx1 is rejected on fixed constants: a smooth 9 cm mesh trips the minimum-triangle\nassert, levcomp raises every collision span under 0.25 m to 0.25 m (the fish\nbecomes a 25 cm ball), and the near plane is fixed at 1 m. WORLD_SCALE = 10.\n\nRecords steps 5-8, the Phase 1 verdict, the working control values and which of\nthem depend on the real clownfish's bounding box.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
2b485281	author	Will Norris
2b485281	added	17
2b485281	deleted	3
2b485281	files	1
2b485281	body	The clownfish built by the idle-animation spike is the real model; Phase 3\nconsumes it from wflevels/aquarium/clownfish.py rather than drawing its own, and\nre-validates the Phase 1 controls on it (new step 15). Phase 0/1 fish are\nthrowaway placeholders.\n\nAlso commits the mockup generator (was only in a session scratchpad); it now\ntargets Plan B and regenerates the committed pages byte-for-byte.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
4e5ce347	author	Will Norris
4e5ce347	added	3
4e5ce347	deleted	3
4e5ce347	files	1
4e5ce347	body	Will chose Plan B after the Phase 0 spike showed the GL/Metal fragment shader\ndiscards texture alpha. Mockups updated to drop the translucent pane. Plan A\nbecomes a separate T4 item (restore alpha in both backends + capture sweep).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
1aa8e779	author	Will Norris
1aa8e779	added	188
1aa8e779	deleted	4
1aa8e779	files	1
1aa8e779	body	The test card (wflevels/aquarium_spike/) builds and the bit-15 pane texels reach the\nGPU with alpha 128, but backend_modern.cc's fragment shader writes alpha 1.0 for every\nfragment (since 23e632ec), so the pane renders opaque and hides the far fish in either\nactor order. Hot-swapping a shader that keeps texture alpha over the debug bridge\n(no engine file touched) shows the rest of the chain works: with the pane created last\nin actor order the blend is exact (max |delta| 1 per channel); created earlier, anything\nbehind it and drawn after it vanishes, because depth writes are always on.\n\nRecords steps 1-4 and the verdict in the plan, corrects the condo glass note, and\ncorrects level-building.md: bungee cameras aim at Target - Follow + Track Object.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
f964a400	author	Will Norris
f964a400	added	243
f964a400	deleted	0
f964a400	files	1
f964a400	body	Plan + three 1440x900 mockups (tank dimensions, gameplay states, pane\nfallbacks / Phase 0 test card). Nothing is built; Phase 0 is a runtime spike\non translucent draw order.\n\nAlso corrects condo_639_640.md: "MATL has no alpha" is true for flat-colour\nmaterials, but textured materials support ~50% translucency via texel bit 15\n(pixelmap.cc:190 -> material.cc:124 -> GL_BLEND). Read from code, not yet run.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
-->
