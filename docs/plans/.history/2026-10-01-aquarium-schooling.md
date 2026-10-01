| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/aa821f80) | school.fth: every mailbox slot has a name (MB_X, MB_VX, MB_DRO ...), long lines split into short helper words; the poster shows the named code in four columns |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/61f6a8bd) | Swarming plan: a mailbox map drawn from a real run (800..1009 for school.fth), the layout the tests now use, and the open follower-rig item |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2460bd2a) | Swarming: the Couzin zone model as a Forth core (school.fth, 2179 B, 6.2 ms/11 fish on the Chromecast), tested against numpy, and an A3 poster |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/50c932a2) | Plan: ten more aquarium fish that school and swarm around the player (Couzin zone model, player as leader), with rendered mockups |

<!--history-meta v1
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
