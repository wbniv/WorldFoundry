| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/484b035f) | feat(scripting): add read-actor-mailbox (cross-actor read) to zForth + WASM |

<!--history-meta v1
484b035f	author	Will Norris
484b035f	added	104
484b035f	deleted	0
484b035f	files	1
484b035f	body	Symmetric partner of write-actor-mailbox: a script can now read mailbox `idx` on\nANOTHER actor, removing the "push to global" indirection (B can pull\n`<A_idx> INDEXOF_X_POS read-actor-mailbox` directly instead of A republishing to a\nshared global each tick).\n\nThe TODO was stale on two counts (verified): custom syscall id 3 is NOT free (FSN\nclaimed custom 3-7 / sys 131-135), and Lua/JS did NOT need it — Lua + both JS\nengines (jerryscript, quickjs) already accept an optional trailing actor arg to\nread_mailbox. So:\n- zForth (the canonical, missing engine): new word\n  `read-actor-mailbox ( idx actor_idx -- val )` = custom 24 / `152 sys`, handler\n  mirrors read-mailbox's read path + write-actor-mailbox's actor lookup. Word def +\n  syscall-map comments (scripting_zforth.cc, neural_forth.h).\n- WASM/wamr (the only other engine genuinely missing it): `read_actor_mailbox(i32\n  idx, i32 actor) -> f32` host fn + (i32,i32)->f32 func type + import branch.\n- Lua / jerryscript / quickjs: already support it — unchanged.\n\nRegression guard wfmut_smoke RA1: a Forth write-actor-mailbox → read-actor-mailbox\nround-trip on a loaded level, eval'd in an override-free context (a scripted actor\nlike the player has a registered script override that RunScript runs instead of an\nad-hoc string; the mailbox words take an explicit actor index so the running\ncontext is irrelevant). Asserts the sentinel survives. Verified: FAILs before the\nword def (ZF_ABORT_NOT_A_WORD), PASSes after; full smoke 36 passed (the 1 fail is\nthe pre-existing SR0 spawn-test).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
