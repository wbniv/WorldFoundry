| Date | Change |
|------|--------|
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/8b23b54d) | The dart startles the school: a fast start (heading flipped at once, 2.5x speed for 0.6 s) for every follower within 5 body lengths |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/dd7b6e4a) | Swarming poster: audited against what is true now |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/4a906de5) | A hard wall limit for the followers (one left the tank on the Chromecast), the poster with Chromecast-only numbers, and the schooling demo clip |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/9fa728a0) | Swarming poster and plan: the in-engine Chromecast result (39 to 43 ms a tick and 20 fps as found, 11.3 ms and 59.9 fps after the mailbox fix), and what the poster does not claim now |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/bec1d758) | Mailbox calls cost 4.2 us each on the Chromecast: three per-call debug streams moved to DBSTREAM5; opt-in --script-profile; a bench level |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/aa821f80) | school.fth: every mailbox slot has a name (MB_X, MB_VX, MB_DRO ...), long lines split into short helper words; the poster shows the named code in four columns |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/f8dcca75) | Swarming poster: the Forth section is one column per rule word (width in proportion to its text), with its size and a one-line note; sources compacted so the page still fits |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/603e2e56) | Swarming plan: wiring school.fth into the level is Phase E, the point of the work, not out of scope |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/61f6a8bd) | Swarming plan: a mailbox map drawn from a real run (800..1009 for school.fth), the layout the tests now use, and the open follower-rig item |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2460bd2a) | Swarming: the Couzin zone model as a Forth core (school.fth, 2179 B, 6.2 ms/11 fish on the Chromecast), tested against numpy, and an A3 poster |

<!--history-meta v1
8b23b54d	author	Will Norris
8b23b54d	added	1
8b23b54d	deleted	1
8b23b54d	files	1
8b23b54d	body	Nothing in the level called sch-startle-all, so pressing A did nothing to the followers, and the old gentle startle (turn away at normal speed) scattered them little even in the model.\nschool_rig.fth: sd-dart-check (the rising edge of aq-dart-t, mailbox 1039). school.fth: a C-start in sch-startle-all, MB_KICK (parameter 981) as the startled speed gain.\nOn the real engine (scripts/analyse-aquarium-school.py --dart): mean distance to the leader 1.55 -> 4.17 BL within 1 s, back to about 2.4 by 4 s. Tests: the model, the built Director. The poster no longer says the dart does nothing.\nNot yet seen on the Chromecast (the TV was not reachable). Plan: docs/plans/2026-10-02-school-dart-startle.md.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
dd7b6e4a	author	Will Norris
dd7b6e4a	added	13
dd7b6e4a	deleted	13
dd7b6e4a	files	1
dd7b6e4a	body	The 'not claimed' note said the school was not in the game: it is, so it now says untuned and the dart is not wired; rule 8 says the startle is not called yet and rule 7 names the hard wall limit;\nthe engine timing pair is labelled as the earlier 2,936 B version; the real-level measurement (resting p_group 0.39, swimming 0.77, alignment +0.40) is printed; the tank figures are re-run with the\nwall limit (every run stays in the box); header and stat boxes shortened to fit; leader weight row says 3 in the game, untuned. Tests pin the wording.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
4a906de5	author	Will Norris
4a906de5	added	15
4a906de5	deleted	15
4a906de5	files	1
4a906de5	body	school.fth: a follower that would leave the box is put back on its edge and its heading reflected inward (test added); 3,216 B, 7.5 ms a step on the Chromecast.\nThe poster prints Chromecast timings only (no PC numbers), including the real level: 59.9 fps, p90 33.4 ms.\ntests/recordings/aquarium_school_demo.mp4: 51 s from the Chromecast's own screen (rest/swarm, swim right/school, rest, swim left, rest, swim and climb), captions burnt in;\nrecorded before the wall limit, so one frame shows a follower outside the glass. scripts/record-aquarium-school-chromecast.py records a new one when nobody is using the TV.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
9fa728a0	author	Will Norris
9fa728a0	added	1
9fa728a0	deleted	1
9fa728a0	files	1
9fa728a0	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
bec1d758	author	Will Norris
bec1d758	added	16
bec1d758	deleted	1
bec1d758	files	1
bec1d758	body	Found timing school.fth inside the engine on the real Chromecast HD: the Director took 39 to 43 ms a tick (20 fps); 7,750 mailbox calls x 4.2 us = 34 ms. The calls\nstreamed 'cmailbox << ... << std::endl' at DBSTREAM1 (LevelMailboxes::ReadMailbox, GameMailboxes::ReadMailbox, WorldFoundryMailboxesManager::LookupMailboxes), and CMake\ndefines SW_DBSTREAM=1 in every build, release included; dbstrm.hp says DBSTREAM1 is startup and shutdown only. At DBSTREAM5 the call costs 0.28 us (timer included) and the\nDirector takes 11.3 ms: 59.9 fps on the device. Origin: the lines are in the first commit (a2784f6e), harmless when SW_DBSTREAM was 0.\n\n- tests/test_mailbox_hot_path.py guards the mailbox read/write functions against a stream below level 5.\n- --script-profile (or WF_SCRIPT_PROFILE=1): every 5 s, the five most expensive actor scripts and the mean mailbox-call cost; off by default (one untaken branch); the flag is weak-linked so other Forth backends build.\n- AQUARIUM_SCHOOL_BENCH=1: a git-ignored bench level whose Director also runs school.fth.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
aa821f80	author	Will Norris
aa821f80	added	14
aa821f80	deleted	12
aa821f80	files	1
aa821f80	body	2,936 B and 7.0 ms a step on the Chromecast (was 2,179 B and 6.2 ms): each name is a word call. Still equal to the numpy reference to 1e-03.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
f8dcca75	author	Will Norris
f8dcca75	added	1
f8dcca75	deleted	1
f8dcca75	files	1
f8dcca75	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
603e2e56	author	Will Norris
603e2e56	added	3
603e2e56	deleted	3
603e2e56	files	1
603e2e56	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
61f6a8bd	author	Will Norris
61f6a8bd	added	26
61f6a8bd	deleted	0
61f6a8bd	files	1
61f6a8bd	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
2460bd2a	author	Will Norris
2460bd2a	added	208
2460bd2a	deleted	0
2460bd2a	files	1
2460bd2a	body	Reference model, standalone zForth host, tank runs in the real 13.4x3.4x4.7 BL box, zone-width sweep, device bench, data sheet with chips, poster generator,\n26 tests, Taskfile tasks, a plan with diagrams and mockups, and the findings folded into the schooling plan (leader weak, paper's turn rate does not fit the tank).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
