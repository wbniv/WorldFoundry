| Date | Change |
|------|--------|
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/ea049144) | feat: MM ROM level data extraction — decoder, investigation, vendored ROM |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/b72b2458) | M2: mm_practice S-curve trough + yellow sphere material |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/bccc0943) | marble-madness-2 M1: canonical iso camera + camera-relative input |

<!--history-meta v1
ea049144	author	Will Norris
ea049144	added	13
ea049144	deleted	12
ea049144	files	1
ea049144	body	Reverse-engineered the Marble Madness arcade ROM level format via MAME\nLua runtime analysis. All 6 levels' path-segment geometry is now decoded.\n\n- assets/arcade-roms/marble.zip — vendored 38-file Atari ROM (git binary)\n- assets/arcade-roms/reference/practice_start.png — MAME headless capture\n- wflevels/marble-madness/decode_levels.py — decoder; reconstructs 68000\n  address space from interleaved ROM chips, walks level pointer table at\n  0x01DEC0, parses descriptor arrays + 24-byte segment records\n- wflevels/marble-madness/levels.json — decoded output: 6 levels, 66 total\n  segments, h_left/h_right/h_center heights + type codes\n- docs/investigations/2026-05-01-marble-madness-rom-level-data.md — full\n  methodology writeup with ASCII structure diagrams and height profiles\n- docs/plans/2026-05-01-marble-madness-faithful.md — M3 status update\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
b72b2458	author	Will Norris
b72b2458	added	2
b72b2458	deleted	2
b72b2458	files	1
b72b2458	body	- gen_level1.py: replace L-shaped prototype with 7-section S-curve trough\n  (start → ramp A right → bridge 1 → ramp B left → bridge 2 → final ramp → goal)\n  4 m Z drop over ~36 m path; goal detection threshold updated to Y > 34\n- blender_update_player_sphere.py: use solid yellow material (flags=0,\n  color=0x00FFFF00) instead of texture; verified in sphere.iff MATL chunk\n- Remove debug prints from rendfcl.cc, material.cc, rendobj3.cc\n- Rebuild all four marble-madness IFFs via full build_level_binary.sh pipeline\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
bccc0943	author	Will Norris
bccc0943	added	157
bccc0943	deleted	0
bccc0943	files	1
bccc0943	body	Camera moved to (-18,-13,28): 45° yaw, 30° tilt, ~30 m from spawn — matches\ntuning.md spec (ISO_TILT_DEG=30, ISO_YAW_DEG=45, CAMERA_DISTANCE=30 m).\n\nPlayer Rotation C set to π/4 rad via gen_level1.py patch_orient so\nMarbleHandler fwd=(√2/2,√2/2,0): UP+LEFT = world +Y (leg 1), DOWN+LEFT = -X\n(leg 2) — faithful Marble Madness iso control mapping.\n\nPlan doc docs/plans/2026-05-01-marble-madness-faithful.md added covering\nM1 (done) through M5+ against the wf-games design docs.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
