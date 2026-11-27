| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/680bd2ea4) | Lava lamp poster: mailbox names in the Forth, 16:40 in the base, footer note gone |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/fe58bb056) | Lava lamp poster, second layout after Will's review: no tags, Forth column |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/f787848b6) | Lava lamp A3 poster (Phase P): research first, a review draft for Will |

<!--history-meta v1
680bd2ea4	author	Will Norris
680bd2ea4	added	3
680bd2ea4	deleted	3
680bd2ea4	files	1
680bd2ea4	body	Will (2026-11-27): "give mailbox numbers actual NAMES", "make time on lava lamp\nshow 16:40", and remove the footer's explanatory and colophon note.\n\n- The printed Forth shows each level cell by its lamp.py name (BLOB0_STUCK,\n  STARTED, P1...). The shipped script keeps its numbers: these are level user\n  mailboxes outside mailbox.inc, and naming them in the script (constant words\n  in the per-step heat loop, or new mailbox.inc entries) would change behaviour,\n  so the level and the Clocks bundle are not rebuilt. lamp.py gains STARTED\n  (109) and forth.py uses it; the generated director is byte-identical. The test\n  maps every printed name back through lamp.py and finds the result in the .lev.\n- render_hero.py poses the base at WALL_HOUR 16, WALL_MINUTE 40 (digit actors\n  by visibility, as ll-time does); re-rendered in the Blender container.\n- The footer is the numbered source list alone; a test keeps the note out.\n\nStill a review draft: the visual review stays pending until Will approves.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
fe58bb056	author	Will Norris
fe58bb056	added	2
fe58bb056	deleted	4
fe58bb056	files	1
fe58bb056	body	Will (2026-11-27): "remove (verify) and (ours) tags... pretty-print the forth\nand put in a narrower, longer column; consider how to relayout".\n\n- No status tag is printed. The statuses still gate the build; a sourced\n  sentence ends in its superscript source number, and the footer says a\n  sentence without one is ours.\n- The Forth is a full-height side column: ll-env, ll-heat0 and ll-tick from\n  the shipped director, laid out by make_poster.pretty() (indented if/else/then,\n  a break after each store). Whitespace is the only change; the test checks\n  each block against lava_lamp.lev. Stack effects sit above the code.\n- Three columns, panels numbered in reading order, the render first and larger.\n- The plan's mockup bundle gains poster-v2 (the draft itself, with notes).\n\nStill a review draft: the visual review stays pending until Will approves.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
f787848b6	author	Will Norris
f787848b6	added	25
f787848b6	deleted	0
f787848b6	files	1
f787848b6	body	docs/reference/lava-lamp-research.md is written first: physics, the wax and the\nliquid, six patents checked on Google Patents, the history (with Q7's 1959 line),\nthe level's Forth, and what was not found or was corrected (the starlight holes\nare the Lava Lite Century's, not the Astro's; US 3,689,139 has two inventors).\n\ndocs/reference/lava-lamp-poster/ follows the Tide Harbour pipeline (claims and\nchips in make_poster.py, the seahorse exporter) with the reef poster's visual-\nreview gate: until the research records Will's approval only a marked draft\nbuilds, exporting lava-lamp-review-draft-a3.pdf (not committed). The hero is a\nCPU Cycles render of the shipped scene (render_hero.py, Blender container); the\npatents carry QR codes (make_qr.py, committed SVGs); the model's numbers and the\nForth words are read from wflevels/lava_lamp, and the test finds each word in\nthe shipped .lev. task poster-lava-lamp, task test-poster-lava-lamp.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
