| Date | Change |
|------|--------|
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/ba9dae81f) | Tide plan: Tide ships in the Clocks APK; the About row needs a Clocks build from the current branch |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/2c3aea8e2) | Tide Harbour: the OpenStreetMap credit moves from the panel to a read-only About row in the settings form |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/e3f5f720d) | Tide Harbour plan: the sun's bearing verified on cast1 (within 1.4 px) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/81dbdd7eb) | Tide Harbour: the river panel's map draws the river's real banks and the Gulf coast |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/5950fe3fa) | Tide Harbour: the sun sits on its true bearing as the camera the shot has sees it |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/8683045e7) | Tide Harbour: a River panel On/Off setting (On by default) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/11e84a354) | Tide poster: panel 8 shows the engine's own picture of the finished level and its river panel |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/30191a240) | Tide Harbour: Q13 closed, the Phase 2 no-veil build stays as it is |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/5705a0903) | Tide Harbour: Q13 decided, option C (veils at 1080p, 30 FPS at night accepted) |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/ccc83818c) | Tide Harbour: the dial's numerals default to Roman |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/99e9cb77b) | Tide Harbour: Q13 approved, the clock is drawn at 1280 x 720 with the veils kept |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/a971252ba) | Tide Harbour: Q13 approved, the clock is drawn at 1280 x 720 with the veils kept |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/1efb68b28) | Tide Harbour plan: the settings object is built (D13, Verification 12 and 13) |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/a952a5ac6) | Tide Harbour plan: Phase 2 record, the night without a veil, Q9/Q10/Q12 applied |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/0dca1b221) | Tide Harbour night probe: the veil is fill-rate bound; 1280 x 720 holds 59.3 FPS |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/98c128d18) | Tide Harbour Phase 0, cast1 half: 59 FPS by day, 30 FPS at night, the bars band |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/5bf1a767e) | Tide Harbour plan and TODO: the clocks use the shared LEVEL extra, LevelCatalog and LevelLaunch |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/d1b93a52a) | Minute Machine audited against the level guides; thin objects are not invisible |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/7242ba346) | Tide Harbour Phase 0 spike (desktop half), and the level guides corrected |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/5d47d74ee) | The tide at Bangkok: an A3 poster, built |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/c2562c13a) | Clocks: every level carries a settings object (D13), and the audit that found none do |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/d15058a16) | Tide Harbour plan approved: D1-D12 and Q1-Q8, with Thai dial numerals |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/2764aa2cc) | Tide Harbour plan: status brought current, questions for Will, reference docs indexed |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/a0e94174c) | Tide Harbour: the Bangkok tide fitted and validated, an A3 tide poster planned |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/6b974e801) | Engine E1: WALL_DAY and WALL_UTC_OFFSET mailboxes, and a dated WF_WALL_CLOCK |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/7cf736574) | Tide Harbour plan: E1 date mailbox approved; runtime light control deferred to TODO |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/77614a8ce) | Tide Harbour plan: the second 3D clock, and the clocks bundle that holds it |

<!--history-meta v1
ba9dae81f	author	Will Norris
ba9dae81f	added	1
ba9dae81f	deleted	1
ba9dae81f	files	1
ba9dae81f	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
2c3aea8e2	author	Will Norris
2c3aea8e2	added	2
2c3aea8e2	deleted	0
2c3aea8e2	files	1
2c3aea8e2	body	The river map is OpenStreetMap data under the ODbL, which asks for the credit wherever the map is shown. Will (2026-11-22): remove the (c) from the\npanel, add it to an about box. The credit plate is gone from the panel and a read-only "About the map" row (two choices: the credit, selected, and\nwhere the licence is) joins the Tide Harbour settings form in the same change, so there is no gap; the phone's capabilities asset lists it read-only.\nOSM's guidance prefers a corner credit for a browsable map and tolerates an easily found About entry for apps: noted in the plan. Checked: 86 Tide tests,\nthe panel in the real engine, check-tide-harbour.py --options PASS. Not seen on a device (the Tide APK must be rebuilt with this level).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
e3f5f720d	author	Will Norris
e3f5f720d	added	1
e3f5f720d	deleted	1
e3f5f720d	files	1
e3f5f720d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
81dbdd7eb	author	Will Norris
81dbdd7eb	added	2
81dbdd7eb	deleted	0
81dbdd7eb	files	1
81dbdd7eb	body	The map drew the river as a line of one width and said the coast was not drawn. It now draws the river as water: both banks, the\ntrue width, an island near the mouth, and the Gulf's coast either side of the mouth, from OpenStreetMap (natural=water with\nwater=river, and natural=coastline; ODbL, credited on the panel). fetch_river_outline.py makes chao_phraya_outline.json (one\nOverpass request; member ways joined into rings; polygons within 600 m of the centreline; rings simplified finer where that made\nthem cross; triangles stored), polytri.py triangulates (ear clipping with the holes bridged in), and map_mesh() draws the\ntriangles cut to the map's window. The centreline stroke is gone: the polygons cover every 50 m of it. The Pak Nam label moves\nclear of the wider mouth. Tests: the triangles cover each polygon exactly, none over an island, the whole centreline in the water;\nthe desktop engine matches the model on all eight dates.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
5950fe3fa	author	Will Norris
5950fe3fa	added	2
5950fe3fa	deleted	0
5950fe3fa	files	1
5950fe3fa	body	The sun disc is placed on the ray from the camera toward the sun, on a plane about 150 m away. The model and the director cast\nthat ray from a fixed reference camera (CAMERA_REF), but the river panel pulls the camera back and shifts it sideways and the\ndrift swings it, so the disc was 3 to 8 degrees off its true bearing (model, panel on: 3.5 deg at 16:05 and 8.2 deg at 17:35;\nengine, 8 Jan 17:51: 79 px). The ray now starts at the camera's own position: scene() uses cs_wide, and the director's new\nth-sun uses the Camera actor it reads for the panel. In the engine the disc now lands within a pixel of the projected true\nbearing at 17:35. Regression tests pin the angle (panel on, off and no drift); the engine matches the model on all eight dates.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
8683045e7	author	Will Norris
8683045e7	added	11
8683045e7	deleted	0
8683045e7	files	1
8683045e7	body	A fifth TideHarbourSettings field, River panel (On|Off, live, first choice the default). Off hides every part of the river\npanel and its arrows (global cell 694 for the field, 709 for the parts' visibility) and gives the harbour the whole screen:\nthe director sets the panel's on-screen share to 0, so the camera has no pull-back and no shift. The model, the director, the\nsettings asset and the tests follow; the desktop engine matches the model for every value of every setting (answered 5 of 5),\nand scripts/check-tide-harbour.py --capture gains --set NAME=INDEX to see a value. The oas headers were regenerated with\ntask gen-oas-headers (ht_and_objects_match_golden passes); that also adds the missing break after the TideHarbourSettings\ncase in objects.c, which fell through into CuckooVillageSettings.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
11e84a354	author	Will Norris
11e84a354	added	1
11e84a354	deleted	1
11e84a354	files	1
11e84a354	body	The harbour drawing was a design sketch; it is now the engine's capture of the shipped level at 17:51 Thai time on 8 January (the\n'now' dot on the panel's tide curve), with the river panel and its map credit. The panel's claims say what the panel is and give\nthe readings at that moment (20:40 high 2.7 m, 04:50 low 1.3 m), which turns.py reproduces (20:42, 04:47). check-tide-harbour.py\n--capture gains --no-fps so the picture has no frame counter. Rebuilt PDF and PNG: no panel overflows. README and plan updated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
30191a240	author	Will Norris
30191a240	added	5
30191a240	deleted	5
30191a240	files	1
30191a240	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
5705a0903	author	Will Norris
5705a0903	added	5
5705a0903	deleted	5
5705a0903	files	1
5705a0903	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
ccc83818c	author	Will Norris
ccc83818c	added	4
ccc83818c	deleted	4
ccc83818c	files	1
ccc83818c	body	Will, 2026-11-21: "let's put the harbor clock tower to roman numerals, per your original suggestion",\nreversing his earlier choice of Thai (Q2/D8). Dial numerals keeps all three choices; Roman is now first,\nso it is the default (0), and Thai is the second. Changed: the .oas choice order and help text (.oad\nregenerated), timeline OPTIONS and the visibility mapping, the director's two numerals cells, the tests\nthat pinned the order, the plan's D8 and Q2. Level, capabilities asset and bundle rebuilt. Tests pass\n(59 passed in the clocks and Tide suites, the director against the real zForth included); the desktop\nengine check (check-tide-harbour.py --options) was not run.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
99e9cb77b	author	Will Norris
99e9cb77b	added	5
99e9cb77b	deleted	5
99e9cb77b	files	1
99e9cb77b	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
a971252ba	author	Will Norris
a971252ba	added	5
a971252ba	deleted	5
a971252ba	files	1
a971252ba	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
1efb68b28	author	Will Norris
1efb68b28	added	28
1efb68b28	deleted	12
1efb68b28	files	1
1efb68b28	body	The state line, the Q9 row, the audit table and the Phase 2 record now say\nwhat was escalated, what was approved (registration only, the Sea Stars\npattern) and what was built: clocksettings.inc, TideHarbourSettings, its\nregistration and class, one object in the level, property@ reads into\ncells 690-693 and the phone asset. Verification 12 carries the strict\naudit (complete for Tide Harbour; Minute Machine is Phase 2b, so the run\nexits 1) and 13 the VM and launch-override engine runs.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
a952a5ac6	author	Will Norris
a952a5ac6	added	152
a952a5ac6	deleted	8
a952a5ac6	files	1
a952a5ac6	body	- State line: Phase 2 built and checked on the desktop; D5 revised;\n  Q9, Q10 and Q12 applied pending Will's confirmation; the settings\n  object escalated; nothing has run on a TV.\n- D5 row and a new section, "Phase 2 decision: the night without a\n  veil": the director re-colours the day's materials through the\n  FACE_COLOR mailboxes, keyed on the sun's altitude in whole degrees and\n  constant above 12 degrees; nothing translucent; the dial, hands and\n  moon never re-coloured; with a state diagram of the looks and what it\n  costs (meshes leave the static-buffer path after the first dusk),\n  unmeasured on cast1.\n- Phase 2 record: what is built, the settings escalation with its exact\n  cause (levcomp's "unknown class", objects.c's assert, the files Sea\n  Stars' type touched), the bugs found and fixed, what is not measured,\n  and what Phase 4 needs.\n- Verification: raw output under steps 1, 2, 3, 4, 10, 12 (FAIL as\n  expected) and 13; step wording kept.\n- New and changed files: the rows Phase 2 added; Out of scope no longer\n  lists the Thai numerals Q2 put in scope.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
0dca1b221	author	Will Norris
0dca1b221	added	9
0dca1b221	deleted	5
0dca1b221	files	1
0dca1b221	body	Four cast1 probes of the night scene (150 actors, Release APK, 2 runs of 30 s each): the control (veil and\nglows) and the veil alone both take exactly 33.4 ms a frame at 1080p (29.97 FPS, every refresh missed, thermal\nstatus 0); the glows alone run 58.45 FPS; the full scene on a fixed 1280 x 720 surface runs 59.31 FPS. So the\nfull-screen translucent veil costs the whole difference and it is fill rate, not the glows or the actor count.\n\nD5 is revised, pending Will: keep the veils and draw this clock at 1280 x 720 (new question Q13; the small Thai\nnumerals are checked at 720p as a Phase 2 gate). The README gets the night-probe section with the table and the\n720p frame, night-probe-summary.json holds the per-run numbers with the job ids, and the open items now name what\nwas not run: sizes between 720p and 1080p, small-text legibility at 720p, the warm dusk veils.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
98c128d18	author	Will Norris
98c128d18	added	27
98c128d18	deleted	9
98c128d18	files	1
98c128d18	body	Measured on cast1 (Chromecast HD, Release APK, coordinator profile workflow): 46, 100 and 150 posed actors\nhold the display's refresh rate by day (59.46, 59.31, 59.29 FPS). With the dark veil and the lit-window\nglows on screen the same device runs at exactly 29.97 FPS: all 909 frames took 33.4 ms, 100% of refreshes\nmissed, thermal status 0. D5 (veils) is reopened; the cause (veil, glows or 1080p fill) is not isolated.\nThe 36 flat water bars band on the TV, by day and at night. The dial and the moon dim at night.\n\nAn earlier read-out that a veil costs about 1.3 FPS was wrong: the day runs had no veil showing. The\nplan, D5, D7, the banding risk and the TODO entry now say what was measured. The engine log in a job's\nevidence is cumulative across launches; the README says how to read it.\n\nAlso: the plan's launch sentence names LevelLaunch and LevelCatalog (TankLaunch was renamed upstream), and\nits clock-tower picture is now a PNG copy in the plan bundle instead of a cross-repository path that\nresolves only from the main checkout.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
5bf1a767e	author	Will Norris
5bf1a767e	added	5
5bf1a767e	deleted	5
5bf1a767e	files	1
5bf1a767e	body	Will, 2026-11-21: "LEVEL is correct". The plan named a clock-only --es clock extra and\nplanned parallel ClockChoice and ClockLaunch classes; the aquarium launch plan's generic\nmechanisms are already on 2026-new-level and the clocks bundle uses them instead.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
d1b93a52a	author	Will Norris
d1b93a52a	added	23
d1b93a52a	deleted	2
d1b93a52a	files	1
d1b93a52a	body	The [T2] audit: Minute Machine passes nearly every rule (ASCII director with no stray backslashes, sun aimed\ncorrectly under the measured light convention, room holds the camera, 59.7 FPS on cast1). Gaps: it never sets\ncamera fog (harmless today, the scene is within about 10 m), it has no settings object (D13, Phase 2b), it\nimports the snowgoons scaffold instead of starting from the baseline toolkit (Q10), and its built outputs are\ngit-ignored where the aquarium levels commit theirs and check them for freshness (Q12).\n\nCorrected the guide's thin-object entry. It says a mesh too thin along the camera's depth axis can be invisible,\nbut Minute Machine's 8 mm cards render on the real TV, and in the spike a sky, nine veils and seven glows built\nas single zero-thickness quads (wound toward the camera) render with the same pixels as boxes\n(TANK_SPIKE_QUAD=1, captured under docs/diagnostics/tide-harbour-spike-2026-11-21/). The entry now says thickness\nalone is not the cause and to check winding and the room first; the veils subsection and the plan's checklist no\nlonger ask for boxes. Q12 added to the plan; the audit item moves to Done.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
7242ba346	author	Will Norris
7242ba346	added	39
7242ba346	deleted	3
7242ba346	files	1
7242ba346	body	Four throwaway levels (46, 100, 150 and 150 posed actors) built through the Blender container and run\nin the Debug engine under software GL; relative cost and look only, cast1 not yet run. The river is 36\nseparately posed bars. Variant d runs a fast day with nine translucent "veils" (fixed opacity, one shown\nat a time through its visibility mailbox) and glow overlays drawn in front of them: day to dusk to night\nworks with no engine change. The dial and the moon must be drawn in front too, or they dim.\n\nReading docs/level-building.md and docs/level-design-troubleshooting.md in full, which should have come\nfirst, showed the spike had walked into four documented traps (grey fog inherited from the snowgoons\nscaffold, an actor leaving the room, coplanar overlapping faces, zero-thickness quads) and that the guides\nthemselves had errors. Corrected: the directional-light recipe has the wrong sign for current content\n(measured: five settings, four faces of known normal, fifteen readings; B = +alt tilts the light down),\nthe mailbox scope table (user range is 2-1900; system starts at 1901 and now holds WALL_DAY and\nWALL_UTC_OFFSET), two camera.cc line references, and an overstated claim about actor indices (qualified\nwith the Minute Machine engine comparison). Added: a veils subsection, and troubleshooting entries for the\nlight sign and for build knobs that never reach the container (only TANK_*, AQUARIUM_* and four more\nprefixes are forwarded; an earlier lighting sweep was void for exactly that reason).\n\nPlan: D5 now veils; a Phase 0 spike record; the rules the guides impose on every clock level; Q10 (start\nfrom the baseline toolkit) and Q11 (prune Docker's build cache, which I will not do unasked). TODO item to\naudit Minute Machine against the guides.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
5d47d74ee	author	Will Norris
5d47d74ee	added	44
5d47d74ee	deleted	2
5d47d74ee	files	1
5d47d74ee	body	Portrait A3 (297 x 420 mm), eight panels, 27 claims each chipped verified, other source or\nours, on the repository's poster pipeline. The research document comes first; make_poster.py\nrefuses to build on an unconfirmed claim, a verified claim with no source or an ours claim\nthat does not name what computes it. The numbers are read from tide_constants.json and\ntime_zone_check.json and from the Navy's printed table, not typed. The exporter reuses the\nseahorse poster's, changing only the PDF name.\n\nPanels: two highs a day or one; a sum of waves; spring and neap; a year of highs and lows;\nfrom a table to constants; how good it is (median 4.1-4.5 cm on an unseen year); which clock\nthe table uses; the harbour and what we do not know. Review found and fixed: a negative\nspring-neap period, a chip calling design statements measured, spikes in the year panel on\ndays with no low, a caption at 2.30:1 contrast, and a wrapped title. Nine tests pass, including\nan independent check of the period against NOAA's speeds and a contrast and size check on all\ndrawn text. Still open and not ours to tick: a person reads the printed-size proof, and the\nprint is on matte stock.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
c2562c13a	author	Will Norris
c2562c13a	added	61
c2562c13a	deleted	2
c2562c13a	files	1
c2562c13a	body	Will: "make sure level has a settings object (same for all clocks---audit)". Audited both\nclocks against the pattern the Planted, Jellyfish, Reef and Sea Stars levels use (an .oas type\nwith live fields, one placed object, property@ in the director, a capabilities asset for the\nphone form, a live-field test). Neither Minute Machine nor Tide Harbour has any of the six.\nscripts/audit-clock-settings.py checks all six per clock; its own test builds a fake tree\nthat passes and removes each piece to see exactly that check flip.\n\nPlan: D13, a Settings objects section (the standard, the audit, a common Clock sheet),\nPhase 2b for Minute Machine's retrofit, LevelSettings becoming a factory by clock id in\nPhase 3, verification steps 12-13, and open question Q9 (what clocks share). The Minute\nMachine plan's D10 is marked superseded for the settings object. TODO item added.\n\nAlso: the tide fit now writes the time-error, longest-gap and error-by-waves-kept numbers the\nposter will print, and the research document's time-zone claim is corrected (the GLOSS\nhandbook verifies Ko Lak's zone; the UHSLC file's own clock is not stated on any page read).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
d15058a16	author	Will Norris
d15058a16	added	17
d15058a16	deleted	18
d15058a16	files	1
d15058a16	body	Will: "accept all except answer to q2 is thai". Every recommendation stands except the\ntower dial, which carries Thai numerals (D8). The harbour mockup now draws them and shows\nthe cost: at the harbour's scale the digits are small, so the plan lists two remedies in\norder (a dial about 1.5x larger, or digits only at 12, 3, 6, 9 with ticks between) and keeps\nRoman numerals as the fallback. Phase 2 first checks that a Thai font is in the Blender\ncontainer image. The questions section becomes a record of the answers.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
2764aa2cc	author	Will Norris
2764aa2cc	added	20
2764aa2cc	deleted	2
2764aa2cc	files	1
2764aa2cc	body	The plan said nothing was built; E1 and the tide fit now are. Adds a Questions for Will\nsection (Q1-Q8, each with a recommendation and what it blocks), marks the poster phase as\nstudied and mocked up but not built, and adds a TODO item for it. Reference rows for the\ntide research and the Forth math words contract in wf-status.md (README.md is a symlink to\nit), and the plan-index row now mentions the tide, the poster and the date mailboxes.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
a0e94174c	author	Will Norris
a0e94174c	added	68
a0e94174c	deleted	8
a0e94174c	files	1
a0e94174c	body	Phase 0(c). The Royal Thai Navy Hydrographic Department publishes predicted highs and\nlows for station HD (Royal Thai Navy Headquarters, on the river in Bangkok). Fitted 64\nharmonic constituents to the 2026 table and scored them on 2027, which the fit never saw,\nand the reverse: median height error 4.5 and 4.1 cm, 90th percentile 11 cm, on a 2.8 m\nrange. The table's clock is UTC+7, measured against Ko Lak's observed hourly record\n(median mismatch 11 min at +7 h, 308 min at 0). Form factor 1.36, mixed and mainly\nsemidiurnal, agreeing with an independent model study (1.06).\n\ntide_fit/ holds the reproducible tooling (polite fetch, parser, Doodson-number\nconstituents, fit, clock check); tests/test_tide_constants.py pins the constants to eight\ndays copied by hand from the printed table and fails for a 7 h clock slip, a wrong K1\nphase or a halved M2. Research document written first, with each claim labelled verified,\nother source or ours (measured), and what was not found. The mockups now use the real\ntide. Plan: poster added (D11), sun and moon decided (D12: a formula, no tables, no moon\nclaim), D6 settled, Phase 0 record and verification steps recorded; task tide-refit added.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
6b974e801	author	Will Norris
6b974e801	added	30
6b974e801	deleted	1
6b974e801	files	1
6b974e801	body	The Tide Harbour clock needs the calendar day (a tide changes day to day) and the\nUTC offset (the tide constants are Thai local time). Two read-only system\nmailboxes, 1925 and 1926, latched with the hour, minute and second from one\ninstant so a script never sees a new day beside an old hour; GLOBAL_SYSTEM_MAX\nmoves to 1927. WF_WALL_CLOCK accepts [YYYY-MM-DDT]HH:MM:SS[.mmm][+HH:MM|-HH:MM|Z][@rate];\nthe time-only form is unchanged and a malformed value still stops the engine.\n\nUnit test checks day numbers against an independent count (leap days, 2000 and 2100,\nbad dates and offsets) and steps across midnight at exact instants with the new\nsampleAfter. Engine tests read the mailboxes through the debug bridge: frozen dated\noverride, a fast clock crossing the new year, the device's own day and offset, and\nmalformed specs. Nine engine tests pass in the container Debug build.\n\nPlan: docs/plans/2026-11-21-tide-harbour-clock.md (E1, approved by Will 2026-11-21).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
7cf736574	author	Will Norris
7cf736574	added	10
7cf736574	deleted	10
7cf736574	files	1
7cf736574	body	Will approved adding the date to the engine (E1). Runtime light control (formerly E2)\nis its own TODO item and the screensaver no longer depends on it: the day turns to\ndusk and night with a sliding sky, glow actors and keyed looks (D5).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
77614a8ce	author	Will Norris
77614a8ce	added	233
77614a8ce	deleted	0
77614a8ce	files	1
77614a8ce	body	A Bangkok stilt-house harbour whose river, boats, sky and clock-tower dial are\na function of the date and time, animated entirely by posing rigid actors from\nthe clock. Also one cd.iff of clock levels with the engine's own level menu as\nthe chooser, and a clock extra or saved choice that skips it. Researched the\nAquarium's chooser, the Dream host's level argument, what scripts can and cannot\nchange (light colour is read once), and public tide sources; states what was not\nfound. Engine change E1 (a date mailbox) needs permission; E2 only if Phase 0\nasks. Three mockups (live harbour, six moments, the chooser) and four diagrams.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
-->
