| Date | Change |
|------|--------|
| [2026-11-10](https://github.com/wbniv/WorldFoundry/commit/f13ce8bf) | Reef tanks finished; style review (step 15) parked by Will |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/6ba89afa) | Reef step 14: mark the textured GL/Metal scene comparisons expected-fail |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/d49cc850) | Reef step 14 PASS: GL sweep identical; untextured GL/Metal scene strict pass |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/51bab0f5) | Metal: compile the style shader as a separate program (reef step 14 strict sweep) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/93e7ba07) | Reef: step 12 PASS (anime Dream rerun, restore verified); step 14 S2 and Metal evidence |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/b9eba308) | Reef step 14: Metal sweep and GL/Metal scene recorded; caustics fixtures |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/52e3b25d) | Reef: the cleaning ends when the boxfish leaves reach (shrimp fix) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/13b3d659) | Reef W4: cast1 acceptance record; Dream host VRAM width fix |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/9818ff39) | Reef W4 step 6: desktop reaction test passes in both styles |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/8e938f3a) | Reef W5: ReefSettings Layout defaults to Random (Will approved) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/380337c3) | Reef D10: the humbug pair becomes Dascyllus reticulatus in both styles |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/b090a8fd) | Reef W5c: Forth layout finished; review renders, cast1 Random-5 gate, docs |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/bfe00512) | Reef: swap humbug for Dascyllus reticulatus in research (D10); park and commit poster sources |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/4bb0d148) | Reef research: boxfish Gulf record closed (D2); humbug flagged (D1) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/fef6db28) | Reef: keep W5b's anime per-piece cost (Will); speed work deferred to TODO |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/65d165bf) | Reef W5b: rock-module kit, site tables, worst-visible and room-slot budgets |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/8decb672) | Reef plan: realistic P3 abort is the 32 MB room slot; W5b budget in bytes |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/094f53a6) | Reef plan: R0 device run P0–P3 on cast1; realistic 97-object load abort |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/a205df47) | Reef: ReefSettings level settings object (plan W5a) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/ed2b171e) | Reef plan: W5 R0 spike results; D9 (where ReefSettings appears) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/aac370a8) | Reef plan: W5 decisions D5-D8 recorded |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/09da72be) | Reef plan: W5 procedural reef (random rocks, rock count, clustered colonies) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/8163dff4) | Reef plan: W3 placement approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/1a30b727) | Reef: nothing floats, everything attaches (plan W3) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/5030e6cd) | Reef plan: W2 approved, W3 started |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/7e42d059) | Reef: rebuild the nudibranch model; W2 skins approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/068281ff) | Reef: creature skins in their own atlas cells (plan W2) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/2099c8e7) | Reef plan: W1 worms approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b8831c71) | Reef: rebuild the Christmas tree worms (plan W1) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/04a42178) | Plan: reef finish, record the completed cast1 frame-rate gate |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b756367f) | Plan: finish the reef tanks (worms, skins, placement, acceptance) |

<!--history-meta v1
f13ce8bf	author	Will Norris
f13ce8bf	added	1
f13ce8bf	deleted	1
f13ce8bf	files	1
f13ce8bf	body	Will, 2026-11-10: "Park it, ship as is". Both looks ship as built with\ncaustics off; the review and the caustics call become a parked T5 item.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
6ba89afa	author	Will Norris
6ba89afa	added	1
6ba89afa	deleted	1
6ba89afa	files	1
6ba89afa	body	Will (2026-11-09): "Mark expected-fail". The reef-* and geom-* scenes\ndiffer only through texture sampling (llvmpipe vs the Apple GPU, bilinear,\nno mipmaps); they are xfail(strict=True) so an unexpected pass is\nreported. The untextured flat-* scenes stay hard asserts. Container run\nagainst Metal run 6af1bd90: 2 passed, 4 xfailed.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
d49cc850	author	Will Norris
d49cc850	added	1
d49cc850	deleted	1
d49cc850	files	1
d49cc850	body	GL (Will: "Run it"): DESIGNER_CHEATS Debug engines at fd9349c8, b03f5cb5\nand HEAD render all 34 sweep levels pixel-identically with every style\nfield at 0 (baseline level asserts on the pre-style engines).\nscripts/style-gl-sweep.sh reproduces it.\n\nUntextured scene (Will: "Fix the scene"): with the boxes lifted 0.12 off\nthe floor the depth tie is gone; Metal run 6af1bd90 (scenes-only, 6 min)\nagainst GL gives S3 byte-identical and S1 within 1/255 on every pixel; the\nstrict test passes for both flat scenes. Row 14 struck as PASS; caustics\nstay off pending step 15.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
51bab0f5	author	Will Norris
51bab0f5	added	2
51bab0f5	deleted	2
51bab0f5	files	1
51bab0f5	body	With every style field at 0, the Metal style engine moved 3 pixels by\n1/255 against the pre-style engine (aquarium_arowana, snowgoons-blender),\ndeterministically. A probe without the style work in wf_vs was pixel-\nidentical (Codemagic 6af1ade1): under fast-math the unused eye/normal/\nabsorb/caustic arithmetic changed code generation for the position and\nfog math. kMSL now keeps every style addition under #ifdef WF_STYLE (as\nGL does), the host compiles a second library with WF_STYLE and binds its\npipelines only while style shading is active. Proof run 6af1b29c: the fix\non b03f5cb5 renders all 34 sweep levels identical to fd9349c8, and the\nstyle program's output is byte-identical to before.\ntests/test_metal_style_variants.py keeps the style-off text equal to the\npre-style shader token for token.\n\nAlso records the untextured-scene result (one raster tie-break pixel)\nand folds the caustics decision into step 15 (Will, 2026-11-09).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
93e7ba07	author	Will Norris
93e7ba07	added	2
93e7ba07	deleted	2
93e7ba07	files	1
93e7ba07	body	Step 12: the anime reef Dream ran 5 min 29 s once cast1 was back; Seahorse\nGrid, tank random and game APK 30554973 are restored and verified.\n\nStep 14: S2 caustics cost 0.55 ms per frame on cast1 (22.90 -> 22.62 FPS),\ninside the 2 ms gate; left off pending Will's look review. Will kept the\nstrict Metal gates ("Keep strict, investigate"). Run 6af1a232: repeats are\nbyte-identical, so the sweep's 3 pixels at 1/255 are a deterministic Metal\nrounding change (suspect: the new wf_vs outputs under fast-math); on the\ngeometry-only scenes every pixel over 1/255 is bilinear texture sampling\n(the same pixels in the S1 and S3 scenes), not the style math.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b9eba308	author	Will Norris
b9eba308	added	1
b9eba308	deleted	1
b9eba308	files	1
b9eba308	body	macos-style-metal build 6af14d47 (12 Mac min): sweep fd9349c8 vs b03f5cb5\nover 35 levels is 32 identical, 2 off by 1/255 on 1-2 pixels, and one\nlevel asserts on both engines. The shared scene is within 1/255 on 99.97% of\npixels; about 95 silhouette pixels per frame exceed it. Both strict gates\nmiss by a few pixels, so the plan needs a gate decision (row 14).\n\nscripts/build-reef-caustic-variants.py makes the S2 off/on fixture levels\nfor the cast1 gate (off is byte-identical to the realistic reef, on\ndiffers in one byte).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
52e3b25d	author	Will Norris
52e3b25d	added	1
52e3b25d	deleted	1
52e3b25d	files	1
52e3b25d	body	Before: once cleaning timer 743 was set nothing cleared it, so a fish\nleaving mid-clean was chased by both shrimp for the rest of the 5 s\n(3.45 s, 3.72 units from the cave mouth in the engine). Now cell 742\nholds "fish within the station's reach" and the clean ends on the\nfirst tick it is 0; the 2 s still-start, the 5 s clean while the fish\nstays, and the station are unchanged.\n\nAfter, in the engine, both styles (and Random Seed 7): the clean ends\n0.00 s after the fish is seen gone and ShrimpOne stays within 0.14 of\nthe cave mouth. check-thai-reef.py asserts that window (ends <= 0.1 s,\nreach <= 1.2, home <= 0.1). New VM regression test\ntest_reef_cleaning_ends_when_the_fish_leaves_reach; the old cleaning\ntest had asserted the bug (cleaning continued after the fish swam out\nof reach) and now asserts the clean ends.\n\nRebuilt both levels, the menu bundle (other tanks at HEAD) and the reef\nDream variants. texcov PASS; reef suites 180 passed, 4 known failures.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
13b3d659	author	Will Norris
13b3d659	added	5
13b3d659	deleted	5
13b3d659	files	1
13b3d659	body	Steps 9 and 10 PASS on today's release APK 83efd2c6 (realistic 22.50,\nanime 20.69 FPS with Layout = Random). E7.1 FAIL: six pairs at 71.25 ms\nagainst 69.09-69.28 ms on 17 Oct. E7.2 reported: 1.615 vs 0.625 ms CPU\nper frame, 16 vs 2 draws. Step 12 partial: the realistic reef Dream ran\n5 min; cast1 left the network during the anime hold, so the restore is\nstill to do. Step 15 captures are ready for Will.\n\nThe Aquarium Dream asserted on both reefs (w = 1024, VRAMWidth = 1024):\ndream_host.cc passed no --vram-width. It now passes 2048, the same as the\naquarium app's wf_args.txt; tests/test_dream_host_vram.py keeps them in\nstep.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
9818ff39	author	Will Norris
9818ff39	added	1
9818ff39	deleted	1
9818ff39	files	1
9818ff39	body	scripts/check-thai-reef.py drives the boxfish to every reactor in the\nreal engine over the debug bridge and reads each reaction from the\nDirector's cells frame by frame, with Layout = Fixed via --property\n(the shipped default stays Random). scripts/build-wf-game-container.sh\nbuilds wf_game inside wf-linux-test:local; the test runs there under\nXvfb (llvmpipe), never on the host.\n\nEvery reaction is inside its window, realistic and anime alike:\nworms x15 close 0.15 s and reopen 3.05-7.95 s at their own timers;\ndusters 0.20 s / 3-6 s; clam 0.35 s / 4 s; crab 2 s; pair dives in\n0.5 s (actor z -0.48) and reopens at 2.5 s; shrimp start cleaning\nafter 2 s still and clean 5 s. Random with Seed 7 passes too.\n\nFinding (reported, not fixed): if the fish leaves mid-clean the shrimp\nfollow it ~3.7 units for the rest of the 5 s timer (743 is never\ncleared). Fix scheduled after cast1 acceptance.\n\nEvidence: docs/diagnostics/reef-reactions-2026-11-09/ (WebP per\nreaction, stills, traces, results JSON). Plan row 6 struck through.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8e938f3a	author	Will Norris
8e938f3a	added	5
8e938f3a	deleted	5
8e938f3a	files	1
8e938f3a	body	Will, 2026-11-09: "Approve, default Random". Seed 0, Rocks 3, Colonies\nNormal stay, so every entry lays out a new reef; Fixed stays selectable\nand still reproduces the reviewed reef. Without a catalog (species-VM\ntests) the poll's fallback stays Fixed. Both reef standalones and the\nmenu bundle rebuilt. Reef suites were still running at commit time\n(requested commit); results follow from the agent.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
380337c3	author	Will Norris
380337c3	added	3
380337c3	deleted	3
380337c3	files	1
380337c3	body	Will, 2026-11-09: swap the humbug (no citable Gulf of Thailand record)\nfor the reticulated dascyllus. Internal names stay "humbug" (headband\nhumbug); scene.py's species string is 'Dascyllus reticulatus'.\n\n- Skin (fishes.humbug, atlas cell 15, uvmap): one black bar behind the\n  head onto the front dorsal and pelvic fins, a faint grey rear bar,\n  pale grey body with a dark scale-margin net (realistic only; anime\n  flat), grey rear dorsal and anal fins, pectoral-base spot, pale snout\n  and tail. New fish_grey swatch after the water bands; 64 px scale\n  square at rows 192-255. Silhouette and behaviour unchanged; 292\n  triangles per fish (was 286); anime worst hull set 23,594 of 24,000.\n- Deleted the uncalled life._humbug().\n- Rebuilt both levels, the Aquarium menu bundle (other tanks at HEAD)\n  and the reef Dream variants (ignored outputs).\n- Docs: original plan D1 and species rows, mockup labels, finishing\n  plan W2 rows, skins-review note; review renders in\n  docs/diagnostics/reef-humbug-swap-2026-11-09/.\n\ntexcov --check PASS. Reef suites: 191 passed; failures are the 4 known\nones (worm harness, two menu-Taskfile tests, one screensaver import)\nplus the parked poster's visual-review gate.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b090a8fd	author	Will Norris
b090a8fd	added	24
b090a8fd	deleted	1
b090a8fd	files	1
b090a8fd	body	Random 5 rocks on cast1: realistic 22.11, anime 20.52 FPS (gate 20).\n4-5 rocks use two rows (right hero behind the fillers). Seed 0 keeps\nits drawn seed across Colonies changes. level_asset_links.py makes\nrelative links so the reef Dream variants rebuild in the container;\nthe species-VM fixture gains random/seed-random. Layout default stays\nFixed until Will reviews. Reef suites: 179 passed, 4 known failures.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
bfe00512	author	Will Norris
bfe00512	added	4
bfe00512	deleted	3
bfe00512	files	1
bfe00512	body	Will, 2026-11-09: swap the humbug (no citable Gulf of Thailand record)\nfor the reticulated dascyllus, Dascyllus reticulatus, and "park poster".\n\n- thai-reef-research.md is final: every species has a Gulf record.\n  D. reticulatus: Satapoomin 2000 Gulf checklist, Dat et al. 2023 (Tho\n  Chu), CAS specimen off Koh Samet (GBIF 473068089), 45 research-grade\n  iNaturalist Gulf observations. D1/D2 search log kept as history.\n- Finishing plan: step 1 done; steps 2 and 13 parked; D10 recorded.\n- Poster sources committed so they are not lost: scripts, notes, test\n  and the six illustrations make_poster.py uses (2.4-3.8 MB each).\n  Review drafts and superseded illustrations are gitignored.\n- claims.py, reef_art.py label and the audit name D. reticulatus; the\n  humbug drawings still need redrawing (noted in claim-review-notes.md).\n\nThe poster test still fails on the closed visual-review gate (3 failed,\n12 passed, 8 skipped, 12 errors), as intended while the poster is parked.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
4bb0d148	author	Will Norris
4bb0d148	added	3
4bb0d148	deleted	3
4bb0d148	files	1
4bb0d148	body	D2: Ostracion cubicus is recorded at Hin Khao, Ko Tao (Sutthacheep et al.\n2022) and in 11 research-grade GBIF occurrences on the Ko Tao and\nChumphon pinnacles.\n\nD1: no citable Gulf of Thailand record for Dascyllus aruanus. GBIF has\nnone in the Gulf, iNaturalist only captive ones, and the Gulf surveys\nread list D. reticulatus and D. trimaculatus instead. Search log and\noptions for Will are in the research ledger; nothing swapped. Poster\nexport (steps 2, 13) stays blocked on D1 and the visual-review gate.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
fef6db28	author	Will Norris
fef6db28	added	1
fef6db28	deleted	1
fef6db28	files	1
fef6db28	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
65d165bf	author	Will Norris
65d165bf	added	13
65d165bf	deleted	1
65d165bf	files	1
65d165bf	body	Six modules (three heroes = today's rocks with their dressing, three new\nfillers), pivot-centred box colliders, 16-point site tables, nine colony\nclumps, visibility cells 200-205/210-218. Fixed is the heroes at their\nFixed pivots and cooks to the same meshes (0.04 mm; renders differ on\n<0.04 % of pixels). report_budget.py --cooked now fails the build on the\nworst visible set, anime hulls and the 32 MB Room #0 slot. Arch gains a\nlintel-only collider. P4 on cast1: 22.03 / 20.26 FPS (gate 20).\nOpen: anime Fixed is 0.93 ms slower than before, cause unknown.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8decb672	author	Will Norris
8decb672	added	6
8decb672	deleted	4
8decb672	files	1
8decb672	body	A record job kept logcat: FatalError Lmalloc out of memory in Named\nRoom #0. Each mesh actor copies its mesh into the level's 32,000,000-byte\nslot; realistic P3 needs ~33.1 MB. Same level at 36 or 48 MB loads on\ncast1. Not an engine bug. Decision: W5b stays inside 32 MB with a\nbuild-time slot check; 36 MB is the tested fallback.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
094f53a6	author	Will Norris
094f53a6	added	26
094f53a6	deleted	8
094f53a6	files	1
094f53a6	body	Probes on copies of today's reef levels, three alternating runs each:\nhidden actors cost ~4-8 us/frame, one-shot moves cost nothing after\nentry. Realistic P3 (97 objects) aborts at load 4 of 4; anime P3 loads.\nCause unknown; W5b's realistic kit waits on it. P0 doubles as the\nre-run of original step 10 (22.95 / 21.19 FPS, both above 20).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
a205df47	author	Will Norris
a205df47	added	2
a205df47	deleted	2
a205df47	files	1
a205df47	body	A Director-owned level settings object, like the Jellyfish and Planted\ntanks': Layout (Fixed|Random, default Fixed until W5c), Rocks (1-5,\ndefault 3), Colonies (Sparse|Normal|Dense) and Seed (24-bit; 0 = a new\nreef on every entry). Both styles carry the catalog: generate.py copies\nsettings.oas/bindings next to each level and writes 'indices' into the\nactor map; both build.sh files run oas2oad and build-object-properties\n(the Jellyfish recipe); the screensaver catalog check knows ReefSettings.\nThe Director polls the four fields once a second (property@, and\nproperty-int-bytes@ for Seed) into mailboxes 860-863 for W5c. D9: a\nlevel settings object with no app code (Will). New test_thai_reef_settings\nplus a VM test that panel values reach the Director.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
ed2b171e	author	Will Norris
ed2b171e	added	25
ed2b171e	deleted	2
ed2b171e	files	1
ed2b171e	body	R0 code reading: moving and hiding pieces from Forth works, colliders\nfollow position but not rotation (one box per module, parked inside the\nroom), Forth's random is already reseeded per level, property@ and the\nTV panel work for a Director-owned catalog, the kit fits the limits, DFRM\nlobes are not worth it. The phone/coordinator settings path is\nPlanted-only today, so D9 asks whether W5a ships TV-panel-only. The\nrotation-latch bug R0 surfaced is fixed (4ca61197, c5b6bc33).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
aac370a8	author	Will Norris
aac370a8	added	2
aac370a8	deleted	2
aac370a8	files	1
aac370a8	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
09da72be	author	Will Norris
09da72be	added	169
09da72be	deleted	0
09da72be	files	1
09da72be	body	Will asked for clustered, random-ish placement like the Planted Tank,\nrandomly generated rocks with a viewer-set count, placement in Forth\nrather than engine code, and a settings object (the reef has none). The\nplan proposes a baked rock-module kit laid out by the Forth Director at\nlevel entry from a new ReefSettings object read with property@, with the\nPlanted Tank's founder-and-lineage colonies over pre-resolved site tables,\nan R0 feasibility spike and decisions D5-D8. Mock-ups render a colony\nprototype for three seeds and toy rock layouts for four seed/count pairs;\nW1-W3 sections gain their as-built screenshots.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8163dff4	author	Will Norris
8163dff4	added	1
8163dff4	deleted	1
8163dff4	files	1
8163dff4	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
1a30b727	author	Will Norris
1a30b727	added	1
1a30b727	deleted	1
1a30b727	files	1
1a30b727	body	An audit against the rock and sand (the analytic rock matches the export\nto ~0.01 units) found zoanthid carpets, cup corals and crusts 0.35-0.6+\nunits in front of the rock, most attached actors and the cauliflower and\ntable corals off their rock, the clam and mushroom coral above the sand,\nthe nudibranch 0.33 above it and bobbing, the shrimp station in mid-air,\nand the hermit crab 0.31 under the sand.\n\n- reef/surface.py: host surfaces, ray casts and smooth normals.\n- reef/placement.py: one table of attached things, resolved at export;\n  anchor_map() reports the resolved positions and generate.py reads them.\n- Polyps, cups and arch cups placed on the surface along its normal;\n  crusts conformed; the coral head's crab and humbugs move with it.\n- Nudibranch crawls flat on the sand at the left rock's foot and turns\n  to face its direction of travel; shrimp wait on the cave floor.\n- W3 tests in test_thai_reef_placement.py; movement tests read the\n  resolved station and host (the old nudibranch test required the bob).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
5030e6cd	author	Will Norris
5030e6cd	added	1
5030e6cd	deleted	1
5030e6cd	files	1
5030e6cd	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
7e42d059	author	Will Norris
7e42d059	added	1
7e42d059	deleted	1
7e42d059	files	1
7e42d059	body	Will approved every W2 skin except the nudibranch, which had barely\nchanged: its old tiles already approximated the colours and the model was\nthe problem (a tall blob with a fence of stalked tubercles). Phyllidia\nvaricosa now has a low flat mantle, three blue-grey ridges with\nyellow-capped tubercles on them, yellow rhinophores, and a top-down mantle\ntexture repeating the ridges with transverse margin ridges.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
068281ff	author	Will Norris
068281ff	added	3
068281ff	deleted	2
068281ff	files	1
068281ff	body	Will reported actors with no textures. Small creatures borrowed sponge,\nsand and rock tiles at ~87 texels per unit, or one flat texel, so they\nrendered as flat colour (crab and shrimp 86 % of area under 3 texels,\nnudibranch 62 % flat black).\n\n- reef/uvmap.py: one pure-Python UV function for every face; generate.py,\n  the texel audit and the review renders all use it.\n- atlas.py cells 9-14: duster radioles and tube, crab, shrimp, nudibranch,\n  hermit shell and legs, crusts; cell 15 humbug sheen and fan/star\n  gradients. Anime saturates and posterises them.\n- Builders use semantic skin keys; zoanthid heads and discs map one\n  flower-head motif each (partition keeps explicit UVs).\n- Colours from sourced references (docs/reference/thai-reef-skin-colours.md).\n- New tests/test_thai_reef_skins.py; texcov --check passes.\n- Both levels and the menu bundle rebuilt (other tanks from HEAD).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
2099c8e7	author	Will Norris
2099c8e7	added	1
2099c8e7	deleted	1
2099c8e7	files	1
2099c8e7	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b8831c71	author	Will Norris
b8831c71	added	9
b8831c71	deleted	9
b8831c71	files	1
b8831c71	body	The worms were flat "pine tree" cut-outs on white pegs, on a rigid 5 x 3\ngrid floating 9-14 cm in front of the Porites boulder, all pointing up,\ncoloured with borrowed tiles, and retracting toward a point 15 cm below.\n\n- scene.py: worm_mouths() places 15 tube mouths on the boulder surface\n  (shared Porites lobes and relief), camera- and up-facing, >= 0.14 apart,\n  crown axis = normal + 0.7 up; neighbours never share a colour morph.\n- life.py: twin spiral crowns (core + two-sided helical radiole ribbon,\n  4.5 turns, explicit UVs) and static collars + opercula in reef_hard.\n- atlas.py: repack to 16 cells of 256 x 256 (D2); cell 8 holds the eight\n  worm morphs (D1), cell 15 the flat swatches; UV writers updated.\n- worm_rig.py: curves rooted at the tube mouths along the crown axes, so\n  the retract scale collapses each crown into its mouth.\n- Anchor, director and actor origin all come from worm_mouths().\n- Both levels and the menu bundle rebuilt (other tanks taken from HEAD).\n- New tests/test_thai_reef_placement.py; the worm reaction test now reads\n  the mouths instead of the old grid.\n\nCrowns 4,920 triangles (budget 5,000). Review renders in\ndocs/diagnostics/reef-worms-2026-11-08/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
04a42178	author	Will Norris
04a42178	added	2
04a42178	deleted	2
04a42178	files	1
04a42178	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b756367f	author	Will Norris
b756367f	added	306
b756367f	deleted	0
b756367f	files	1
b756367f	body	Compares the 2026-11-02 reef plan's 15 verification steps with today's\nstate and adds W1 (rebuilt Christmas tree worms set into the Porites\nboulder), W2 (creature skins via a 16-cell atlas repack), W3 (placement\nand an anchor single source of truth, with a regression test) and W4 (the\noriginal plan's open steps). Mockups, a texel-coverage audit and the\nmockup generator are in the bundle.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
