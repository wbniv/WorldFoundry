| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/76c9f028) | docs(investigations): zForth recursion-stack extension — cost + native-Forth scanner analysis |

<!--history-meta v1
76c9f028	author	Will Norris
76c9f028	added	312
76c9f028	deleted	0
76c9f028	files	1
76c9f028	body	Grounded analysis prompted by FSN pushing its recursive builder into C++.\nFindings: the WF build already runs ZF_RSTACK_SIZE=64 (not 32 — that's the\nvendor's unused Linux sample); one global g_ctx, so a bump costs the delta once;\nthe inner interpreter is a trampoline, so deep Forth recursion consumes the\nrstack array, never the C stack. Raising both stacks to 256 = +1,536 B once\n(2.3% of sizeof(zf_ctx)=66,336, dominated by the 64 KB dict). The real depth\nmultiplier is the no-locals tax: a recursive word >r-stashes its live vars, so\n64 slots ≈ ~15 levels of (x,y,depth) recursion.\n\nAdds §6: native-Forth scanner vs. the C++ sys word. The sys boundary isn't a\nshortcut — zf_cell is float with no strings, so OS handles/paths can't cross to\nForth; the index-iterator (cwd-*) is the only representable native point, and\nphase 1 already used it. The move worth making (if live-tunable layout is\nwanted) is policy-in-Forth over a flat numeric node table emitted by C — which\nsidesteps recursion entirely; only porting the recursion itself needs the stack\nbump, and that's the least worthwhile variant.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
