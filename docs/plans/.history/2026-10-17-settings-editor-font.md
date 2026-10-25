| Date | Change |
|------|--------|
| [2026-10-25](https://github.com/wbniv/WorldFoundry/commit/a8f4f9b1) | docs: UI font step 8 on both casts with the refreshed builds (14 of 16 checks) |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/80acb882) | UI font step 8: second round stopped before installs; device inspections |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/61e4504a) | UI font plan: step 8 is not complete until Cast2 and every app run |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/228b9cd4) | UI font Phase 3: Chromecast 1 verification; settings row counter moved |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/f5ea4849) | UI font plan: implementation notes and verification 1-10 |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/20c9e080) | UI font plan: F2-F6 approved |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/65adad34) | Plan: Atkinson replaces stb_easy_font everywhere, and stb_easy_font is deleted |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/6bc62d46) | Plan: the settings editor in Atkinson Hyperlegible Next, as finding-your-way |

<!--history-meta v1
a8f4f9b1	author	Will Norris
a8f4f9b1	added	15
a8f4f9b1	deleted	0
a8f4f9b1	files	1
a8f4f9b1	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PkFSbo6jcue9Gfyb6U9HVs
80acb882	author	Will Norris
80acb882	added	24
80acb882	deleted	0
80acb882	files	1
80acb882	body	Cast2 and the other apps cannot run without breaking the exact-restore rule:\nmenu-back covers aquarium only, the new APKs are versionCode 7 over installed\n5s, Cast2 lacks smb/snowgoons/qbert and the coordinator cannot uninstall or\ndowngrade. Read-only inspections of both devices are recorded.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
61e4504a	author	Will Norris
61e4504a	added	1
61e4504a	deleted	1
61e4504a	files	1
61e4504a	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
228b9cd4	author	Will Norris
228b9cd4	added	72
228b9cd4	deleted	11
228b9cd4	files	1
228b9cd4	body	Verification 8 and 9 of docs/plans/2026-10-17-settings-editor-font.md, on Cast1:\nmenu-back (aquarium, all eight tanks), baseline-settings 21/21, baseline-picker 12/12\nand aquarium-seahorses 13/13 pass with armeabi-v7a UI-font APKs; the previous apps\nare restored and their hashes verified (aquarium 3d796c77, baseline 72a39130).\nFrame times, APK and cd.iff sizes are recorded; the surface is 1920x1080, so the\natlas is 1:1 and nearest sampling shows no artifacts there. The macOS Codemagic\nresult is noted.\n\nThe device showed the form's row counter (1 / 7) overlapping the help line in\nRegular 28; it now sits right-aligned above the rows. Evidence is in\ndocs/diagnostics/ui-font/cast1/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
f5ea4849	author	Will Norris
f5ea4849	added	180
f5ea4849	deleted	3
f5ea4849	files	1
f5ea4849	body	Steps 1-7 and 10 pass (7 with two noted gaps); 8 and 9 are not done: the disk\nfilled during the APK build and Cast1 needs an administrator re-add.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
20c9e080	author	Will Norris
20c9e080	added	6
20c9e080	deleted	11
20c9e080	files	1
20c9e080	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
65adad34	author	Will Norris
65adad34	added	91
65adad34	deleted	53
65adad34	files	1
65adad34	body	Will widened the scope: the new font replaces the old one entirely and is\nused on the fishtank menu and every other place stb_easy_font draws (eight\nfiles). Seven variants (1024x2048 atlas), a missing atlas stops start-up,\nand a third mockup page compares the fishtank menu and the HUD strip with\ntheir Cast1 captures.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
6bc62d46	author	Will Norris
6bc62d46	added	128
6bc62d46	deleted	0
6bc62d46	files	1
6bc62d46	body	One shared WFGA atlas baked at build time (both pinned OFL weights, 198\ncode points, 4 variants, 1024x1024), shipped in every cd.iff and drawn\nthrough the existing bitmaptext/DrawGlyphs path, with an stb_easy_font\nfallback. Mockups compare Cast1 captures with the same layout in\nAtkinson; TODO [T3] waits on F2-F5.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
-->
