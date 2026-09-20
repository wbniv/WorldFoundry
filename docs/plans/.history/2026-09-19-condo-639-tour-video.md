| Date | Change |
|------|--------|
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/466adf4b) | fix(main): window switches survive the game's argv parser (-height= was taken for -h) |
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/e59fcf28) | feat(condo): 30 s captioned room tour of all 11 blue rooms — tour-639.mp4 |
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/caba2591) | docs(plan): tour video — author the path once, replay frame-exact |
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/de9d0b05) | feat(condo): bath-N door + 640 master/closet locators, walking pace, HOME-safe task sources |
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/88c389c7) | docs(plan): 20 s room-tour video of 205/639 (bridge-driven walk + burnt-in captions) |

<!--history-meta v1
466adf4b	author	Will Norris
466adf4b	added	1
466adf4b	deleted	1
466adf4b	files	1
466adf4b	body	ParseCommandLine matched switches by first letter, so -height=960 hit the\n'h' help branch and exited with usage, -width= fell through to the\n"unrecognized" debug print and -fullscreen toggled the DESIGNER_CHEATS 'f'\nframe-rate flag. The HAL (ParseWindowSwitches) had already consumed them\ncorrectly since 2026-06-04. Recognise -width/-height/-xpos/-ypos/-window/\n-fullscreen explicitly as platform-handled no-ops, make -h/-help and -f\nexact matches, list them in usage(); document in command-line-switches.md.\n\nTour recorder gains --size WxH / TOUR_SIZE (default stays 640x480; the\ncommitted tour-639.mp4 is unchanged). Known limitation recorded: the\ncapture pipe assumes 30 rendered fps, so HD takes play fast — TODO added.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017TmcNaoJVBysfboB3VeC7N
e59fcf28	author	Will Norris
e59fcf28	added	121
e59fcf28	deleted	40
e59fcf28	files	1
e59fcf28	body	The tour build (wflevels/condo_639_640_tour, `task tour-condo-639`) is the\ncondo level with the player's Forth replaced by a waypoint servo compiled\nfrom tour-639.path.json: each leg pushes toward the waypoint coordinate\nfrom either side and advances only when within 0.12 m AND nearly stopped\n(X/YSPEED), so momentum can't slide him into a jamb (the first\n"complete once past" version stalled at the closet door 1 run in 4). Leg\ncounter is global mailbox 500, hold timer 501, done flag 502.\n\ntests/record_condo_639_tour.py records it with -record_video, times the\ncaptions off the leg counter + level clock over the bridge, cross-checks\neach hold against the room's target bbox, then ffmpeg burns the .srt in,\nprepends a title card and setpts to TOUR_SECONDS (30). Four takes: same\nroom order every time, cue drift ≤ 0.7 s.\n\nWhy not bridge-driven input: inject_input holds one override per slot\nand the loop renders (records) every iteration even when paused, so\nframe-exact external replay isn't available; a position-based walk is.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017TmcNaoJVBysfboB3VeC7N
caba2591	author	Will Norris
caba2591	added	30
caba2591	deleted	15
caba2591	files	1
caba2591	body	Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017TmcNaoJVBysfboB3VeC7N
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
