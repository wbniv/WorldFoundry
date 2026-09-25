| Date | Change |
|------|--------|
| [2026-05-02](https://github.com/wbniv/WorldFoundry/commit/78507fa8) | docs: expand mm-level-elevations with additional MAME reference screenshots |
| [2026-05-02](https://github.com/wbniv/WorldFoundry/commit/4c49ac03) | docs: add screenshots to mm-level-elevations investigation |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/45745892) | marble-madness: calibrate GAME_UNIT to 0.05 m/unit; clean up debug prints |
| [2026-05-01](https://github.com/wbniv/WorldFoundry/commit/6dfb872e) | docs: Practice + Beginner elevation tables, shape classification |

<!--history-meta v1
78507fa8	author	Will Norris
78507fa8	added	31
78507fa8	deleted	7
78507fa8	files	1
78507fa8	body	User-edited: replaced single Beginner/Practice screenshots with a set of\ntimestamped MAME captures covering both levels at multiple points in each\nrun, plus a cliffs warning shot from a later level. Five new images added\nunder docs/investigations/mame-screenshots/.\n\nAlso rebuilds mm_fromscratch binaries with the cam-remap fix (&/| operators).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
4c49ac03	author	Will Norris
4c49ac03	added	24
4c49ac03	deleted	2
4c49ac03	files	1
4c49ac03	body	Three reference images now populate the doc's screenshot section:\n- mame-beginner-race.png — MAME Beginner race capture (marble in trough)\n- mame-practice-level.png — MAME Practice level capture (crowned path)\n- blender-beginner-path.png — EEVEE render of calibrated Beginner path mesh\n  showing trough structure, two heading turns, back wall, and goal platform\n\nAlso fixes PATH_HALF table entry (4.0 → 2.0 m, matching current calibration)\nand updates the rationale note accordingly.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
45745892	author	Will Norris
45745892	added	35
45745892	deleted	32
45745892	files	1
45745892	body	GAME_UNIT halved from 0.1 → 0.05 m/unit: Beginner trough walls drop from\n49–66° to 30–48° from horizontal, matching the shallow-to-moderate bowl\nprofile visible in MAME captures.  PATH_HALF/SEG_LEN unchanged — only\nvertical heights change so all XY positions stay valid.\n\nAlso: remove PRE/POST diagnostic fprintfs from jolt_backend.cc (flat-ground\nthreshold 0.999 was already committed); remove dead PBO code and [capture]\ndiagnostic prints from display.cc; update blender_mm_fromscratch.py spawn/\ncamera/target Z values and Forth respawn Z; update elevation investigation\ndoc with new Z columns and wall-angle table.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
6dfb872e	author	Will Norris
6dfb872e	added	105
6dfb872e	deleted	0
6dfb872e	files	1
6dfb872e	body	Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
