| Date | Change |
|------|--------|
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/65adad34) | Plan: Atkinson replaces stb_easy_font everywhere, and stb_easy_font is deleted |
| [2026-10-17](https://github.com/wbniv/WorldFoundry/commit/6bc62d46) | Plan: the settings editor in Atkinson Hyperlegible Next, as finding-your-way |

<!--history-meta v1
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
