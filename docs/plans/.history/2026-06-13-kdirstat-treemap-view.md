| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/86e790e4) | feat(treemap): KDirStat/QDirStat squarified disk-usage treemap view |

<!--history-meta v1
86e790e4	author	Will Norris
86e790e4	added	72
86e790e4	deleted	0
86e790e4	files	1
86e790e4	body	Third filesystem visualizer on the §6 flat-table + Forth-policy core. Flat\nsquarified treemap (KDirStat-style): the plane tiled with rectangles, area ∝\nrecursive size, nested by directory, coloured by file type — read top-down,\nwalkable. User-chosen: flat true-2D, colour-by-type, static (no re-rooting).\n\n  • C emitter tm-scan (scripting_zforth.cc): the Bruls squarified-treemap layout\n    (pack children into rows along the shorter side while the worst aspect ratio\n    improves; recurse per dir) + an extension→type-id classifier (the string\n    stays in C). Emits a flat table {x,y,w,h,type,depth} (TmCell) + tm-x/y/w/h/\n    type/depth accessors. Pure arithmetic — NO trig (tm_worst is the Bruls form).\n  • Render policy in the Director .fth: spawn a corner-pivot unit box per cell,\n    set-scale3 (w,h,slab), set-color (type>rgb). The file-type palette + slab\n    height are hot-reloadable. Cleanest geometry yet — one unit box + non-uniform\n    scale IS every cell; no bespoke meshes.\n\nNew syscalls 160-168 (tm-config/tm-scan/tm-*) + set-scale3 bootstrap word. New\nlevel wflevels/treemap/ + task run-treemap. Budget gotcha fixed with area-based\nculling (TM_MIN_AREA/TM_MIN_LEAF) so ~250 cells fill the whole rect under the 480\npool (depth-first layout otherwise eats the budget on the first huge subtree).\nPlan: docs/plans/2026-06-13-kdirstat-treemap-view.md\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
