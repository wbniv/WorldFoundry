| Date | Change |
|------|--------|
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/177e51f6) | Seahorse device variants; record verification steps 8 and 10 |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/dfc13252) | Record seahorse Phase 2: as-built notes, steps 6-7 PASS, TODO done |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/0a128929) | Add seahorse phases, deformer follow-ons and Blender-in-container to TODO |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/c8a226cc) | Record seahorse Phase 1 verification and the texture-overflow fix |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/e941e460) | Record two pre-existing faults found during seahorse Phase 1 |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/02e18dbc) | Add seahorse research and A3 biomechanics poster (Phase 0) |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/f394d62f) | Document stale face normals under deformation; DFRM updates them |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/01d360f3) | Record seahorse plan decisions D2, D4, D6 and index the plan |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/623a8ca3) | Plan saltwater seahorses with 35-joint tails and a generic deformer |

<!--history-meta v1
177e51f6	author	Will Norris
177e51f6	added	42
177e51f6	deleted	0
177e51f6	files	1
177e51f6	body	scripts/build-planted-seahorse-variants.py cooks the planted tank's settings\n(saltwater + None / 1 pair / 2 pairs, or freshwater; seed 713, age 150, growth\npaused) into a built aquarium APK's selector bundle and re-signs it, keeping\nthe native libraries and wf_args.txt. Step 10 and Phase 4 reuse it.\n\nPlan: step 8 PASS (max_limit_use 0.959, frame_flips 0, wrap centre error\n0.257 mm). Step 10 NOT RUN: Chromecast 1 dropped off the network as job\nJ-0369f7a26e23 connected; nothing was installed; the coordinator's automatic\nretry was cancelled. The desktop settings and behaviour montages are attached.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
dfc13252	author	Will Norris
dfc13252	added	34
dfc13252	deleted	1
dfc13252	files	1
dfc13252	body	Phase 2 merged as 7b0662c4: 1,101 triangles per seahorse, 693 clip\nframes within 0.005 deg, slotted-action exporter fix, PERM pool 1->3 MB,\nmenu bundle left for a later rebuild. Content tests 75 passed in the\ncontainer; actor map names 21 seahorse entries.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
0a128929	author	Will Norris
0a128929	added	1
0a128929	deleted	3
0a128929	files	1
0a128929	body	Seahorses Phase 2 (wip, dispatched), 3 and 4 under Level / Gameplay;\nDeformer phase 2 and the joint-rig spike parked until the seahorses ship;\n"Run Blender asset generation in a container" under Tools & Pipeline (Will,\n2026-10-16). Also the texture-slot-overflow Done line and the seahorse\nplan's captured deferrals. The plan header now points at the TODO entries.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
c8a226cc	author	Will Norris
c8a226cc	added	26
c8a226cc	deleted	6
c8a226cc	files	1
c8a226cc	body	Step 5 PASS: deformer_golden (bit-identical), dfrm_strand, smoke and the\nnew aquarium ctests (11/11, Release, container) on 02f726c9; all eight\ntanks pass on Chromecast 1 (job J‑2926cf7cc193); macOS build green with\nAQUARIUM PARITY: MATCH. The lead-in is world-vertical (roll not\ncompensated). The exit-time abort deferral is struck through: it was a\nRelease heap overflow at texture load, fixed in 02f726c9.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
e941e460	author	Will Norris
e941e460	added	3
e941e460	deleted	1
e941e460	files	1
e941e460	body	Lionfish and Planted Tank abort at exit with free(): invalid pointer on\ndesktop (pre-E0 code too); test_species_movement.py lacks lion-pose in\nits Forth word list (6 failures). Listed as deferred items for triage.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
02e18dbc	author	Will Norris
02e18dbc	added	58
02e18dbc	deleted	18
02e18dbc	files	1
02e18dbc	body	Research document for H. reidi, written first: ring counts (most often\n35 tail rings, range 31-39), tail plate anatomy, grasping, fin\nfrequencies (20-60 Hz for H. reidi; the plan's 30-42 Hz is H. erectus),\nstrike timing (prey in the mouth at 5.7 ms; peak head rotation\n26.7 deg), size, colour, pairing, eyes and stocking, each with status,\nlink, DOI, locator, species and access limits.\n\nA3 portrait poster generated from it: eight panels, every claim\nchipped verified / other species / ours, nothing unverified printed.\n27 regression tests (one A3 page, fonts, type size, fit, edges, links,\nwording, build freshness, tail numbers match the plan).\n\nPlan: fold the findings in, raise the dorsal tip limit 10 -> 12.5 deg so\nthe tail's total dorsal range (~289 deg) matches H. kuda's 290 deg,\nmark the greeting and colourways as ours, correct the stocking source,\nand record verification steps 1-4 as PASS. Mockups follow the new limit.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
f394d62f	author	Will Norris
f394d62f	added	4
f394d62f	deleted	2
f394d62f	files	1
f394d62f	body	Face normals are computed once at load (rendobj3.cc:286) and drive the\nsoftware back-face cull and flat lighting, so a deformer that only moves\nvertices culls and lights with rest-pose normals. A coiled seahorse tail\nwould show holes. The plan's DFRM evaluator now rotates each deformed\nface's rest normal by its sample frame, with a test; the five existing\ndeformers keep stale normals as a deferred follow-up. The investigation\nexplains how culling works, why GPU skinning collides with the static\npath, and the ways out; it also corrects a citation to the real cull\nloop (static_mesh.cc:773-809).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
01d360f3	author	Will Norris
01d360f3	added	5
01d360f3	deleted	5
01d360f3	files	1
01d360f3	body	Will accepted the remaining recommendations on 2026-10-16: H. reidi,\nauthored hitching posts, and Deformer phase 2 after the seahorses ship.\nRetitle for the 2-pair default and add the plan's row to the index.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
623a8ca3	author	Will Norris
623a8ca3	added	446
623a8ca3	deleted	0
623a8ca3	files	1
623a8ca3	body	Plan for H. reidi seahorses in the saltwater Planted Tank: a 35-joint\nprehensile tail driven by DFRM v1 (rooted curve, weighted transform,\nclip playback) behind one generic deformer slot that the five existing\ndeformers move into, golden-tested. Includes research and A3 poster\nscope, behaviour, settings, measurement protocol and Deformer phase 2.\nWill decided D1 (engine edits for Phase 1), D3 (4 seahorses) and D5\n(1024 permanent texture page) on 2026-10-16.\n\nMockups: interactive tail rig, tank states over real Chromecast 1\ncaptures, settings sheet, and poster layout; build_mockups.py rebuilds\nthem and their thumbnails.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
-->
