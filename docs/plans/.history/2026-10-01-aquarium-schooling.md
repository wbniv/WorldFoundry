| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/0269cd95) | Android size trim iter 2 plan: implemented; measurements both ABIs x three apps; verification 1-4 PASS, 5 pending |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ace2e0be) | Aquarium: ten more fish that school and swarm round the player's fish (AQUARIUM_SCHOOL_N=10), running on the Chromecast HD |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/bec1d758) | Mailbox calls cost 4.2 us each on the Chromecast: three per-call debug streams moved to DBSTREAM5; opt-in --script-profile; a bench level |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/aa821f80) | school.fth: every mailbox slot has a name (MB_X, MB_VX, MB_DRO ...), long lines split into short helper words; the poster shows the named code in four columns |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/61f6a8bd) | Swarming plan: a mailbox map drawn from a real run (800..1009 for school.fth), the layout the tests now use, and the open follower-rig item |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2460bd2a) | Swarming: the Couzin zone model as a Forth core (school.fth, 2179 B, 6.2 ms/11 fish on the Chromecast), tested against numpy, and an A3 poster |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/50c932a2) | Plan: ten more aquarium fish that school and swarm around the player (Couzin zone model, player as leader), with rendered mockups |

<!--history-meta v1
0269cd95	author	Will Norris
0269cd95	added	6
0269cd95	deleted	0
0269cd95	files	1
0269cd95	body	Plan: status, checklist, deviations (--exclude-libs added to item 2; the\n0.11 spelling of the WAV-only init; the plan's export list kept), a\nmeasurements table (iteration-1 counterfactual rebuilt from today's source,\nas found, now) with raw numbers, and the verification steps with their raw\noutput. Step 5 (the user's snowgoons sideload) stays PENDING; the condo\nrelease ran on the Chromecast HD instead (59.9 fps, phonepad listening).\n\nPredictions that did not hold, now written down: -fno-exceptions leaves\n51 KB + 13 KB of the prebuilt libc++'s unwind data; the .dynsym/.dynstr\nsaving appeared only with --exclude-libs; MA_NO_VORBIS saves 0 B\n(miniaudio 0.11 compiles Vorbis only with stb_vorbis included).\n\nApril size report: a follow-up note linking the results report, and a\ncorrection of its MA_NO_VORBIS attribution.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
ace2e0be	author	Will Norris
ace2e0be	added	16
ace2e0be	deleted	2
ace2e0be	files	1
ace2e0be	body	Phase 1 (the rig made per-fish): every rig mailbox goes through fish-off (mailbox 1016, 0 for the player), so the one rig poses a follower from its own 40 mailboxes\nat 1100 + 40 (k - 1) and its own five part actors (the Director's actor words read them from slots 1017..1021 when fish-off is not 0). The followers share the player's\nfive meshes: 50 part actors, no new assets. The default level is unchanged in behaviour (regenerated: its scripts carry the new header).\nPhase 2 (the behaviour, wired, untuned): the player's fish is the leader; school above 1.0 body lengths a second, swarm below 0.45, blended into the zone width;\ntwo followers updated a frame (12 Hz each), all ten posed every frame (school_rig.fth). Level built into wflevels/aquarium_school (git-ignored) with larger room/object memory.\nOn the real Chromecast HD, release build: 59.9 fps median, p90 33.4 ms; the Director 10.2 ms a tick. Screenshot in the plan. scripts/capture-aquarium-school.py renders it on the PC.\nNot done: anemone avoidance, the startle on the dart, sizes, tuning.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
bec1d758	author	Will Norris
bec1d758	added	1
bec1d758	deleted	1
bec1d758	files	1
bec1d758	body	Found timing school.fth inside the engine on the real Chromecast HD: the Director took 39 to 43 ms a tick (20 fps); 7,750 mailbox calls x 4.2 us = 34 ms. The calls\nstreamed 'cmailbox << ... << std::endl' at DBSTREAM1 (LevelMailboxes::ReadMailbox, GameMailboxes::ReadMailbox, WorldFoundryMailboxesManager::LookupMailboxes), and CMake\ndefines SW_DBSTREAM=1 in every build, release included; dbstrm.hp says DBSTREAM1 is startup and shutdown only. At DBSTREAM5 the call costs 0.28 us (timer included) and the\nDirector takes 11.3 ms: 59.9 fps on the device. Origin: the lines are in the first commit (a2784f6e), harmless when SW_DBSTREAM was 0.\n\n- tests/test_mailbox_hot_path.py guards the mailbox read/write functions against a stream below level 5.\n- --script-profile (or WF_SCRIPT_PROFILE=1): every 5 s, the five most expensive actor scripts and the mean mailbox-call cost; off by default (one untaken branch); the flag is weak-linked so other Forth backends build.\n- AQUARIUM_SCHOOL_BENCH=1: a git-ignored bench level whose Director also runs school.fth.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
aa821f80	author	Will Norris
aa821f80	added	2
aa821f80	deleted	2
aa821f80	files	1
aa821f80	body	2,936 B and 7.0 ms a step on the Chromecast (was 2,179 B and 6.2 ms): each name is a word call. Still equal to the numpy reference to 1e-03.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
61f6a8bd	author	Will Norris
61f6a8bd	added	2
61f6a8bd	deleted	0
61f6a8bd	files	1
61f6a8bd	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
2460bd2a	author	Will Norris
2460bd2a	added	30
2460bd2a	deleted	1
2460bd2a	files	1
2460bd2a	body	Reference model, standalone zForth host, tank runs in the real 13.4x3.4x4.7 BL box, zone-width sweep, device bench, data sheet with chips, poster generator,\n26 tests, Taskfile tasks, a plan with diagrams and mockups, and the findings folded into the schooling plan (leader weak, paper's turn rate does not fit the tank).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
50c932a2	author	Will Norris
50c932a2	added	153
50c932a2	deleted	0
50c932a2	files	1
50c932a2	body	Revised after the user asked whether swarming had been researched first: it had not. The plan now cites the literature (Pitcher's shoal/school\ndistinction; Couzin et al. 2002, read from the paper: zones of repulsion/orientation/attraction, the four collective states, p_group and m_group,\nhysteresis; Couzin et al. 2005 on informed leaders; real ocellaris clownfish are site-attached, not schooling) and builds the behaviour on that model.\nThe startle on a dart is decided (yes). A C++ flocking fallback is explained as a ladder and left as the user's decision after Phase 0 measures.\nAdds a TODO item (unranked: tiers are set in a Fable session).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
