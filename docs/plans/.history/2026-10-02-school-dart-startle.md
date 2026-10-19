| Date | Change |
|------|--------|
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/8b23b54d) | The dart startles the school: a fast start (heading flipped at once, 2.5x speed for 0.6 s) for every follower within 5 body lengths |

<!--history-meta v1
8b23b54d	author	Will Norris
8b23b54d	added	105
8b23b54d	deleted	0
8b23b54d	files	1
8b23b54d	body	Nothing in the level called sch-startle-all, so pressing A did nothing to the followers, and the old gentle startle (turn away at normal speed) scattered them little even in the model.\nschool_rig.fth: sd-dart-check (the rising edge of aq-dart-t, mailbox 1039). school.fth: a C-start in sch-startle-all, MB_KICK (parameter 981) as the startled speed gain.\nOn the real engine (scripts/analyse-aquarium-school.py --dart): mean distance to the leader 1.55 -> 4.17 BL within 1 s, back to about 2.4 by 4 s. Tests: the model, the built Director. The poster no longer says the dart does nothing.\nNot yet seen on the Chromecast (the TV was not reachable). Plan: docs/plans/2026-10-02-school-dart-startle.md.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
