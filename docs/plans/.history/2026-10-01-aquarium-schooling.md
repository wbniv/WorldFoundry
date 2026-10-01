| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2460bd2a) | Swarming: the Couzin zone model as a Forth core (school.fth, 2179 B, 6.2 ms/11 fish on the Chromecast), tested against numpy, and an A3 poster |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/50c932a2) | Plan: ten more aquarium fish that school and swarm around the player (Couzin zone model, player as leader), with rendered mockups |

<!--history-meta v1
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
