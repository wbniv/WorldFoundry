| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/b2f18cf6) | feat(filelight): 3D Filelight — walkable radial disk-usage sunburst (P1) |

<!--history-meta v1
b2f18cf6	author	Will Norris
b2f18cf6	added	266
b2f18cf6	deleted	0
b2f18cf6	files	1
b2f18cf6	body	A second filesystem visualizer (sibling of FSN filesys), built on the §6\nflat-table + Forth-policy split: C walks the tree, computes recursive byte\nsizes, and subdivides the [0,1) revolution circle ∝ size — emitting a flat\nnumeric segment table (fl-scan + seg-* accessors, scripting_zforth.cc). The\nDirector .fth iterates the table and applies the RENDER POLICY (depth→template,\nsize→height, per-branch hue, wedge tiling) by spawning baked annular-sector\nwedge templates at the origin, rotating them to their arc (revolutions — the\nengine-native Euler unit), Z-scaling by size, colouring by hsv>rgb. No string\ncrosses to Forth; flat iteration → no recursion, no rstack bump.\n\n  M1 static sunburst — fl-scan/fl_subdivide/fl_subtree_bytes + seg-* + set-\n     rotation; annular-sector wedge + centre-disk templates; Director tile loop.\n     35 segments → ~150 wedges, 0 out-of-room skips, no asserts.\n  M2 colour + cinematics — per-branch hue (hue=branch/8, depth desaturates) via\n     the hsv>rgb C math primitive; fl-flydown. HOT-RELOAD PROVEN: rotating the\n     hue in the Director .fth re-skinned the level with the engine binary's\n     mtime unchanged (rebuilt level only).\n  M3 navigable — fl-navigate polar (r,θ)→depth-1 segment, B re-root / C ascend,\n     disk play-bounds, deferred despawn→re-scan→re-render. Smoke-tested headless\n     (WF_FL_TEST_DESCEND): descend './wftools' → ascend '.' cycle, no crash.\n\nNew engine syscalls 140-150 (fl-config/fl-scan/seg-*/set-rotation/fl-navigate/\nfl-flydown/hsv>rgb) + bootstrap words r@/spawn0/set-color. New level\nwflevels/filelight/ + task run-filelight. Plan:\ndocs/plans/2026-06-13-filesystem-viz-on-a-flat-table-forth-policy-core-f.md\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
