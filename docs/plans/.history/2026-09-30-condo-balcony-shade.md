| Date | Change |
|------|--------|
| [2026-10-03](https://github.com/wbniv/WorldFoundry/commit/10310efe) | Save pending plans, balcony RFQ materials, notes and transcripts |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/1e4cf3e0) | RFQ packet: Zigbee motor is a price check only; plan is fixed-code RF + own bridge |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/65bf4504) | RFQ packet: remote must be fixed code, not rolling/hopping code |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/20c29cbd) | Balcony shade: see-through waterproof (clear PVC) fabric wanted; packet, LINE message and plan updated |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/10836a51) | Condo 639 balcony: zip screen, 7 cm recess + grass, west-façade ledge; POV cuts off |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/613a692a) | RFQ packet: awning removal is out of the shops' scope (someone else removes it first) |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/e39a69b3) | Balcony shade plan: grass covers the whole recessed floor, turns up edges |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/f71c1241) | Balcony shade plan: the ledge runs the full west wall of 639 and 640 |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/3dd48d3a) | Balcony shade: view and airflow when raised is the top priority; spec 'when raised' row |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/4f7b172c) | Balcony shade: rain protection is required (waterproof fabric), RF remote + Zigbee inquiry, grass under 1 cm |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/42adeac4) | Balcony shade: artificial grass, pigeons, rain; fix section (recess spans whole patio); RFQ packet updated |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/643ff9fa) | Condo balcony shade plan: awning is being replaced (open question 6 answered) |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/fc046f37) | RFQ packet: add annotated opening photo; plan: existing awning open question |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/510882a8) | Condo balcony shade: jambs (south full wall, north 10 cm stub), opening flush south |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/8883f82d) | Condo balcony shade: fold in Will's answers (ledge 35 deep x 64 tall, patio 280, 3 m ceilings) |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/ce0a2fa6) | Plan condo 639 balcony zip screen (solar-strip motor) and 7 cm floor recess |

<!--history-meta v1
10310efe	author	Will Norris
10310efe	added	3
10310efe	deleted	1
10310efe	files	1
1e4cf3e0	author	Will Norris
1e4cf3e0	added	1
1e4cf3e0	deleted	1
1e4cf3e0	files	1
1e4cf3e0	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
65bf4504	author	Will Norris
65bf4504	added	1
65bf4504	deleted	1
65bf4504	files	1
65bf4504	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
20c29cbd	author	Will Norris
20c29cbd	added	16
20c29cbd	deleted	16
20c29cbd	files	1
20c29cbd	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
10836a51	author	Will Norris
10836a51	added	335
10836a51	deleted	2
10836a51	files	1
10836a51	body	Level model for docs/plans/2026-09-30-condo-balcony-shade.md part B (§ 7d of\nblender_create_condo.py, CONDO_SHADE=0 builds the old level back):\n\n- Whole recessed patio (x 2.75..5.55, y -1.95..-0.10) dropped 7 cm by a bmesh\n  split of unit-639's floor, closed with welded risers; 1 cm darker-green grass\n  slab on top (CONDO_GRASS), so the walk-on step is 6 cm.\n- Shell parapet replaced: 1.11 m / 10 cm pony wall, north jamb + pier, and one\n  west-facade-ledge actor along both units' west wall (x -4.21..7.90, soffit\n  2.15), cut around every wall top and coloured from the wall under it (fixes\n  the ochre-over-blue ledge; regression check in the model test).\n- Shade: cassette with solar-strip material, two guides, 8 edge-free fabric\n  slats + bar driven from the Director (Z_POS = lift + (1-c) park), B / key 2\n  within 0.9 m, 2 s travel, reversible; bar stows in the cassette when raised;\n  wall switch cue on the south jamb. Mailboxes 60-64; reach band disjoint from\n  the glass doors' (asserted).\n- Automatic window/patio POV cuts gated behind CONDO_POV_TRIGGERS (default\n  off, Will); doll-house is the only automatic shot. camera-controls test\n  expects the doll-house after a reset; superseded notes on three plans.\n- Rebuilt condo_639_640, _tour and _touch. tour-639.mp4 is now stale.\n\nTests: tests/verify_condo_balcony_shade_model.py (headless geometry, on/off),\ntests/verify_condo_balcony_shade.py (in-engine bridge: step, walls, reach,\ntravel, reversal, one-press-one-thing, no camera cut). Verification 1-7 with\nraw output in the plan.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
613a692a	author	Will Norris
613a692a	added	3
613a692a	deleted	3
613a692a	files	1
613a692a	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
e39a69b3	author	Will Norris
e39a69b3	added	1
e39a69b3	deleted	1
e39a69b3	files	1
e39a69b3	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
f71c1241	author	Will Norris
f71c1241	added	8
f71c1241	deleted	5
f71c1241	files	1
f71c1241	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
3dd48d3a	author	Will Norris
3dd48d3a	added	3
3dd48d3a	deleted	3
3dd48d3a	files	1
3dd48d3a	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
4f7b172c	author	Will Norris
4f7b172c	added	10
4f7b172c	deleted	9
4f7b172c	files	1
4f7b172c	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
42adeac4	author	Will Norris
42adeac4	added	14
42adeac4	deleted	5
42adeac4	files	1
42adeac4	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
643ff9fa	author	Will Norris
643ff9fa	added	1
643ff9fa	deleted	1
643ff9fa	files	1
643ff9fa	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
fc046f37	author	Will Norris
fc046f37	added	2
fc046f37	deleted	0
fc046f37	files	1
fc046f37	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
510882a8	author	Will Norris
510882a8	added	5
510882a8	deleted	5
510882a8	files	1
510882a8	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
8883f82d	author	Will Norris
8883f82d	added	19
8883f82d	deleted	14
8883f82d	files	1
8883f82d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
ce0a2fa6	author	Will Norris
ce0a2fa6	added	105
ce0a2fa6	deleted	0
ce0a2fa6	files	1
ce0a2fa6	body	Real-world spec for the 268 x 111 cm opening, level-model approach (new\nsection 7d, 8-slat roll animation), two mockups, five open measurements.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01TfMcgfFyhXKC4CNP5iF7Nz
-->
