| Date | Change |
|------|--------|
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/de9d0b05) | feat(condo): bath-N door + 640 master/closet locators, walking pace, HOME-safe task sources |
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/88c389c7) | docs(plan): 20 s room-tour video of 205/639 (bridge-driven walk + burnt-in captions) |

<!--history-meta v1
de9d0b05	author	Will Norris
de9d0b05	added	46
de9d0b05	deleted	35
de9d0b05	files	1
de9d0b05	body	Level rebuilt from the updated source model (~ commit 2c95db7): 87 actors,\n13 room targets; tests/walk_condo.py now also walks the guest-bedroom door\nand the new bath-N door.\n\nPace: ground speed is Running Acceleration's terminal velocity against\nRunning Deceleration (≈ accel/26), not Max Ground Speed — 8 gave 0.31 m/s,\nwhich the walk test misread as a blocked door. Default is now 40 ≈ 1.5 m/s;\nCONDO_ACCEL/CONDO_SPEED override for the tour build.\n\nTaskfile: $HOME in a sources: glob is not expanded by Task, so a changed\n.blend never retriggered condo-level; use (env "HOME").\n\nTour plan: scope is every blue (639-owned) room — 639's seven plus 640's\nmaster suite and room-2.9x3.3 — with the storyboard redrawn to match.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017TmcNaoJVBysfboB3VeC7N
88c389c7	author	Will Norris
88c389c7	added	95
88c389c7	deleted	0
88c389c7	files	1
88c389c7	body	Plan + storyboard mockup. Flags that 639-bath-N has no doorway in the\nsource model, so a 7-room tour needs a one-line DOORS addition there;\n6-room fallback documented.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017TmcNaoJVBysfboB3VeC7N
-->
