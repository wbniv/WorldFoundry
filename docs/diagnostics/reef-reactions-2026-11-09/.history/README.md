| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/9818ff39) | Reef W4 step 6: desktop reaction test passes in both styles |

<!--history-meta v1
9818ff39	author	Will Norris
9818ff39	added	66
9818ff39	deleted	0
9818ff39	files	1
9818ff39	body	scripts/check-thai-reef.py drives the boxfish to every reactor in the\nreal engine over the debug bridge and reads each reaction from the\nDirector's cells frame by frame, with Layout = Fixed via --property\n(the shipped default stays Random). scripts/build-wf-game-container.sh\nbuilds wf_game inside wf-linux-test:local; the test runs there under\nXvfb (llvmpipe), never on the host.\n\nEvery reaction is inside its window, realistic and anime alike:\nworms x15 close 0.15 s and reopen 3.05-7.95 s at their own timers;\ndusters 0.20 s / 3-6 s; clam 0.35 s / 4 s; crab 2 s; pair dives in\n0.5 s (actor z -0.48) and reopens at 2.5 s; shrimp start cleaning\nafter 2 s still and clean 5 s. Random with Seed 7 passes too.\n\nFinding (reported, not fixed): if the fish leaves mid-clean the shrimp\nfollow it ~3.7 units for the rest of the 5 s timer (743 is never\ncleared). Fix scheduled after cast1 acceptance.\n\nEvidence: docs/diagnostics/reef-reactions-2026-11-09/ (WebP per\nreaction, stills, traces, results JSON). Plan row 6 struck through.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
