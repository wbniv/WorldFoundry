| Date | Change |
|------|--------|
| [2026-05-02](https://github.com/wbniv/WorldFoundry/commit/d3d52731) | fix: marble visibility + SW isometric camera for mm_fromscratch |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/54edacdf) | feat(C): heading-based path geometry — type field lower byte = path direction |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/ea049144) | feat: MM ROM level data extraction — decoder, investigation, vendored ROM |

<!--history-meta v1
d3d52731	author	Will Norris
d3d52731	added	8
d3d52731	deleted	0
d3d52731	files	1
d3d52731	body	- Visibility Mailbox: 2002→1 (EMAILBOX_TRUE); local MBs init to 0 so 2002 was always invisible\n- CamShot Target: 'Target02'→'Player' so camera always looks at marble\n- CamShot Position: (-6,-8,10) — SW+above at 45° elevation, clears all trough walls\n- All Position axes: Relative — camera tracks marble with constant SW offset\n- Expanded Room/ActBox bbox to contain camera at all marble positions\n- FOV remains 60° (noted as no-op in movecam.cc — engine TODO)\n- Camera angle now matches arcade Marble Madness isometric SW view\n- Investigation doc: added turn-angle analysis (27° world-space, not 90°)\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
54edacdf	author	Will Norris
54edacdf	added	44
54edacdf	deleted	18
54edacdf	files	1
54edacdf	body	rom_to_blender.py: cross-sections placed perpendicular to heading_angle(type),\npositions cumulate via SEG_LEN × (cos θ, sin θ). Practice segs 0-8 run at\n18.28° (ENE S-curve, open-sided), segs 9-10 at 45° (walled trough, crest).\nSpawn moved above seg 9 (21.4, 7.1, Z=14) — ball rolls to goal without joystick.\nRoom/camera repositioned for new path extent X[0..25] Y[0..11].\nInvestigation doc updated with confirmed type-field → heading interpretation.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
ea049144	author	Will Norris
ea049144	added	329
ea049144	deleted	0
ea049144	files	1
ea049144	body	Reverse-engineered the Marble Madness arcade ROM level format via MAME\nLua runtime analysis. All 6 levels' path-segment geometry is now decoded.\n\n- assets/arcade-roms/marble.zip — vendored 38-file Atari ROM (git binary)\n- assets/arcade-roms/reference/practice_start.png — MAME headless capture\n- wflevels/marble-madness/decode_levels.py — decoder; reconstructs 68000\n  address space from interleaved ROM chips, walks level pointer table at\n  0x01DEC0, parses descriptor arrays + 24-byte segment records\n- wflevels/marble-madness/levels.json — decoded output: 6 levels, 66 total\n  segments, h_left/h_right/h_center heights + type codes\n- docs/investigations/2026-05-01-marble-madness-rom-level-data.md — full\n  methodology writeup with ASCII structure diagrams and height profiles\n- docs/plans/2026-05-01-marble-madness-faithful.md — M3 status update\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
