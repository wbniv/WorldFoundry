| Date | Change |
|------|--------|
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/00ae68df) | feat(condo): master-bedroom window POV pan; tour cut → 40 s |

<!--history-meta v1
00ae68df	author	Will Norris
00ae68df	added	111
00ae68df	deleted	0
00ae68df	files	1
00ae68df	body	A second first-person camshot: step into the 1.6 m strip along 640's curved south glass\nand the shot cuts to cs_master — a Relative (−1.8, 0, 1.7) offset that lands past the\nglass and outside the shell's bbox, so the physics camera has nothing to climb over —\nwhile MasterLook pans 5 s from Sathu Pradit Road to the south-east up to the river loop\nto the south-west, KCC Apartments mid-pan. The balcony block became add_pov_camera()\n(zone + camshot + scripted look target); the Director forwards interior, balcony,\nmaster in that order so a window shot wins while its strip is occupied.\n\nTour: the master-bedroom hold moves from the room centre to the window with a 5 s hold\n(a 3 s hold only played 60 % of the pan); raw 45.2 s → 40.4 s cut (TOUR_SECONDS 40).\n\nPlan: docs/plans/2026-09-19-condo-master-window-pov.md\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017hM4VFRoFFkipNVRLTs42g
-->
