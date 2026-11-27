| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/41508fa0a) | Candle flicker: Option B measured against A on cast1 (+1.39 ms CPU a frame), the look material, the study camera resolved |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/34c6f5ce0) | Cuckoo Village: size gate re-set to 9 MiB (Will), enforced by a test |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/6af3636d5) | Cuckoo Village: the candle flames flicker (Option A: four meshes a tree, two shapes a group, 24 two-sine rules) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/021bb3c4f) | Candle flicker plan: judge the variants by eye (tree clips, a near study, a frame strip) as well as by profile |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/d56dc0951) | Candle flicker plan: measure with the engine's frame profile through variant-benchmark; the profile job cannot resolve a tenth of a millisecond at a locked 33.4 ms |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/a7097f770) | Display mailboxes: verification recorded (edge flush on five shapes, width follows the screen); candle flicker plan: the deformer is a measured option |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/2ba08b6b1) | Candle flicker plan: a semicolon broke the sequence diagram |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/a35980cc5) | Plan: flickering candle flames (four meshes a tree, a clock-driven shape swap), with mockups and diagrams |

<!--history-meta v1
41508fa0a	author	Will Norris
41508fa0a	added	27
41508fa0a	deleted	1
41508fa0a	files	1
41508fa0a	body	variant-benchmark J-83080304e587 (A then B, 60 s after 15 s, --frame-profile through the Dream host): CPU total 22.19 ms (A)\nagainst 23.58 ms (B), the director +1.76 ms and the deformer +0.44 ms; both 30 fps. The gate (B within 0.1 ms of A) fails;\nA stays shipped and the choice is Will's (TODO, T5). Near-study strip and loops (desktop, same instants), cast1 tree clips\n(J-cb9ea5a3f79a, J-26738f3d4732) and a comparison page in the plan bundle. The camera pointed where told all along: the\ncapture's warm-up was one frame (NaN start), the director's own camera writes run after the camera update, and the aimed\ncandle sits inside the foliage. Evidence, analysis script and the measurement-build patch in\ndocs/diagnostics/candle-flicker-ab-cast1-2026-11-27/. New TODO: the Player falls out of the room in a desktop Debug run.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
34c6f5ce0	author	Will Norris
34c6f5ce0	added	1
34c6f5ce0	deleted	1
34c6f5ce0	files	1
34c6f5ce0	body	Will accepted the proposed 9,437,184-byte gate after the size accounting in\nthe flowers plan (step 7). tests/test_cuckoo_village_size.py enforces it; the\nlevel is 8,787,968 bytes today.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
6af3636d5	author	Will Norris
6af3636d5	added	28
6af3636d5	deleted	1
6af3636d5	files	1
6af3636d5	body	Each tree's ten candles are two groups of five; each group's flames are built in two shapes (tall and leaning\ntoward +X, short and leaning away, 8 triangles each) and the director shows one at a time, switching about 7.4\ntimes a second a group with a different phase for each of the 24 groups. 48 flame actors, cells 232 to 279\n(215 to 226 freed), still lit by the candle season and the window glow, so Window lights puts them out.\nChecked against timeline.flame_shape in the real zForth VM (38,080 cells) and by the model tests. Level +46 KB.\nOption B (a DFRM deformed flame) stays on the branch candle-flicker-spike; its cast1 measurement is a TODO item.\nRebuilt with scripts/clocks-levels.sh regenerate: Minute Machine's files also change because the merged levcomp now\ngives a level without a settings holder a default one (Show framerate).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
021bb3c4f	author	Will Norris
021bb3c4f	added	13
021bb3c4f	deleted	1
021bb3c4f	files	1
021bb3c4f	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
d56dc0951	author	Will Norris
d56dc0951	added	3
d56dc0951	deleted	3
d56dc0951	files	1
d56dc0951	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
a7097f770	author	Will Norris
a7097f770	added	36
a7097f770	deleted	15
a7097f770	files	1
a7097f770	body	Display mailboxes plan: results under each verification step with raw output; the panel keeps its\nsize so its share of the width follows the screen (27 % on a television, 21 % on the Pixel), which\ncorrects the plan's 27 % everywhere; mockup regenerated to match; resize and Pixel steps open.\nNew guard test: half_w() is today's HALF_W, and each screen shape gets its own edge.\nCandle flicker plan: the engine can deform meshes (DFRM v2, 16 curves a mesh); the plan now has the\nvisibility swap (A) and a deformer-driven flame (B) side by side, with a cast1 measurement first.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
2ba08b6b1	author	Will Norris
2ba08b6b1	added	1
2ba08b6b1	deleted	1
2ba08b6b1	files	1
2ba08b6b1	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
a35980cc5	author	Will Norris
a35980cc5	added	136
a35980cc5	deleted	0
a35980cc5	files	1
a35980cc5	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
-->
