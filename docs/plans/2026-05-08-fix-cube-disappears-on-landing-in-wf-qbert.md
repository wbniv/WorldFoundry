# Plan — fix cube-disappears-on-landing in WF Q*bert

## Context

In `wflevels/qbert_practice/`, when Q*bert lands on a cube (apex), the
**entire cube vanishes** instead of flipping its top face from purple
(state 0) to yellow (state 2). Screenshot: Q*bert hovering over an empty
slot in the pyramid. Earlier today I fixed an `over` → `2 pick` stack bug
in the director's visibility fan-out, which got us this far (cubes show
the correct L1R1 palette at game start), but the post-landing transition
still fails.

What's verified:

- IFF assets are correct (`gen_cube.py` writes `cube_state{s}_r{r}.iff`
  with the right per-state top color: `0x5646EF` for state-0, `0xDEDE00`
  for state-2 of round 0; verified via hex dump of MATL chunk).
- Per-actor IFFs are byte-identical to the per-state source IFFs after
  the `shutil.copyfile` overwrite pass at the end of `blender_create_qbert.py`.
- Each actor's `wf_Visibility Mailbox` is correctly wired:
  `INDEXOF_VIS_BASE + r*84 + N*3 + s` (= 442 for cube 0 round 0 state 2).
- `Actor::isVisible()` in `wfsource/source/game/actor.cc:794` reads the
  mailbox value as a bool — direct, no caching.
- The director's visibility fan-out string baked into `qbert_practice.lev.bin`
  matches the post-fix source (`2 pick` not `over`), via `strings` grep.

What's unverified and is the prime suspect:

The fan-out's address computation is `440 + (i/3)*84 + j*3 + (i%3)`,
where `i` is the inner loop counter (combo 0..11) and `j` is the
**outer** loop counter (cube 0..27). `j` is defined in
[`engine/stubs/scripting_zforth.cc:234`](../../WorldFoundry.2026-new-level/engine/stubs/scripting_zforth.cc):

```forth
: j  ' lit , 2 , ' pickr , ; immediate
```

i.e. `j` compiles to `lit 2 pickr`, which reads return-stack item 2
(third from top). In a clean nested do/loop, R-stack from top should be
`[inner_counter, inner_limit, outer_counter, outer_limit]`, so `pickr 2`
gives the outer counter. Standard Forth semantics.

But `j` is **not used anywhere else** in the WF codebase — `grep -rn`
shows it's referenced only in `qbert_practice/blender_create_qbert.py`
and defined in `scripting_zforth.cc`. It's never been runtime-tested.
There's no zForth unit test for it.

If `pickr 2` returns the wrong value at runtime — because of how WF's
`do`/`loop+` primitives interact with the R-stack mid-iteration, or
because the `loop+` machinery temporarily perturbs R-stack and the
inner body sees `j` differently than expected — the address calc
writes to the wrong mailbox, and the state-2 actor's vis (mb 442 for
cube 0) never gets set to 1.

## Recommended approach

**Restructure the visibility fan-out to avoid `j` entirely** by making
the outer loop a fully unrolled walk over `cube_state` mailboxes, with
the inner loop handling only the (round, state) pairs (12 combos)
keyed by the *current* cube N held on the data stack instead of via
`j`.

Concretely: the outer loop pushes the cube index `i` onto the data
stack BEFORE entering the inner loop, so the inner body reads cube N
from the data stack (using `pick`) instead of from `j`. Stack layout
becomes `( cur_pal cube_state cube_N )` going into the inner loop.

### File to modify

`wflevels/qbert_practice/blender_create_qbert.py` — the
`DIRECTOR_SCRIPT` definition, specifically the "Visibility fan-out"
block around lines 685–714.

### New visibility fan-out

```forth
425 read-mailbox 4 %                      \ ( cur_pal )
28 0 do                                    \ outer: i = cube N
    200 i + read-mailbox                   \ ( cur_pal cube_state )
    i                                      \ ( cur_pal cube_state cube_N )
    12 0 do                                \ inner: i = combo 0..11
        \ Stack at body entry: ( cur_pal cube_state cube_N )
        \ Reach via pick (not j):
        \   pick 0 = cube_N    (top, depth 0)
        \   pick 1 = cube_state
        \   pick 2 = cur_pal
        i 3 / 2 pick =                     \ r==cur_pal? ( ... bool1 )
        i 3 % 2 pick = &                   \ AND s==cube_state?
        \ NB: after first `=`, stack is ( cur_pal cube_state cube_N bool1 ).
        \ Pushing combo_s and reaching cube_state via 2 pick now grabs
        \ cube_N (depth 2) — wrong. Re-arrange: do BOTH compares at the
        \ top of the inner body before any new pushes that perturb depth.
        if 1 else 0 then                   \ ( cur_pal cube_state cube_N flag )
        \ Address: 440 + (combo/3)*84 + cube_N*3 + (combo%3)
        \ cube_N is on data stack at depth 1 (just below flag).
        440 i 3 / 84 * +                   \ ( cur_pal cube_state cube_N flag base )
        2 pick 3 * +                       \ + cube_N*3 ; cube_N at depth 2
        i 3 % +                            \ + s
        write-mailbox                      \ pops flag, addr
    loop
    drop drop                              \ drop cube_N, cube_state
loop
drop                                       \ drop cur_pal
```

The two `pick`s in the comparisons need rethinking — let me restructure
once more for cleanliness. The cleanest layout: do BOTH comparisons
into a single AND'd flag *before* pushing the address:

```forth
425 read-mailbox 4 %                       \ ( cur_pal )
28 0 do
    200 i + read-mailbox                   \ ( cur_pal cube_state )
    i                                      \ ( cur_pal cube_state cube_N )
    12 0 do
        \ Compute flag first; stack is ( cur_pal cube_state cube_N ).
        \ - i 3 / = combo_r;  cur_pal at depth 2 → 2 pick
        \ - i 3 % = combo_s;  cube_state at depth 1 → 1 pick (= over)
        \   ...but `over` would dup cube_state. Simpler: compare
        \   AGAINST cur_pal first (deeper), then cube_state.
        i 3 / 2 pick =                     \ ( ... bool_r )
        i 3 % 3 pick = &                   \ ( ... combined_flag )
        \ Now stack is ( cur_pal cube_state cube_N flag ).
        \ Compute address: 440 + (combo/3)*84 + cube_N*3 + (combo%3).
        i 3 / 84 *                         \ ( ... flag r*84 )
        440 +                              \ ( ... flag base )
        2 pick 3 * +                       \ ( ... flag addr_partial ); cube_N at depth 2
        i 3 % +                            \ ( ... flag addr )
        write-mailbox                      \ writes flag at addr
    loop
    drop drop                              \ drop cube_N, cube_state
loop
drop
```

Wait — second compare is `i 3 % 3 pick =`. After `bool_r` is on
top, stack is `( cur_pal cube_state cube_N bool_r combo_s )` after `i 3 %`.
At depth: 0=combo_s, 1=bool_r, 2=cube_N, 3=cube_state. So `3 pick`
reaches cube_state. ✓

I'll write the final version into the script with explicit stack-trace
comments at every step so it's auditable.

### Verification

1. Build: `bash wftools/wf_blender/build_level_binary.sh qbert_practice`
2. Confirm the rebuilt director script in `qbert_practice.lev.bin` no
   longer contains the literal token ` j ` via:
   `strings wflevels/qbert_practice/qbert_practice.lev.bin | grep -E ' j [0-9*]'`
   (should return nothing for the visibility fan-out; only intro/etc
   may still have unrelated `j` if any — there shouldn't be any).
3. Launch engine, hop on apex, observe: apex cube top face flips to
   yellow `#DEDE00`, sides remain teal/dark-teal. No disappearance.
4. Hop on a row-1 cube, confirm same behavior across all 28 cubes.
5. Clear the round, advance to L1R2; confirm the new round's state-0
   palette renders correctly across all 28 cubes (this is the
   round-clear branch's `cur_pal` advance — same fan-out logic
   handles this transition).

### Fallback if the issue is elsewhere

If after this restructure the cube *still* disappears on landing, the
problem is not `j` but something else. Add a debug-bridge probe to
`mb 442` (vis for cube 0 round 0 state 2) before and after a hop:

```python
import socket, json
def get(slot):
    s = socket.create_connection(('localhost', 7777))
    s.send((json.dumps({"op":"get_mailbox","slot":slot}) + '\n').encode())
    r = s.recv(4096); s.close(); return r
print("pre-hop:", get(440), get(442))   # expect 1, 0
# hop
print("post-hop:", get(440), get(442))  # expect 0, 1 — if not 0,1 the fan-out is buggy
```

If `mb 442` IS getting set to 1 post-hop but the cube still doesn't
render, the issue is in the engine's actor loading or per-state IFF
resolution — investigate `wfsource/source/game/actor.cc:isVisible()`
call sites and whether `cube_NN_rR_sS.iff` resolves correctly for
non-default actors.

## Critical files

| File | Action |
|---|---|
| `wflevels/qbert_practice/blender_create_qbert.py` | Replace the visibility fan-out block (lines ~685–714) with the `j`-free restructure above. Keep the surrounding director script (cube-state advance, win check, round-clear, intro state machine, etc.) unchanged. |
| `wflevels/qbert_practice/qbert_practice.lev.bin` | Will be regenerated by the build step; no manual edit. |

## References

- Director script source: `wflevels/qbert_practice/blender_create_qbert.py`
  lines 616–717 (the full `DIRECTOR_SCRIPT` string).
- zForth `j` definition: `engine/stubs/scripting_zforth.cc:234`.
- zForth `pickr` semantics: `engine/vendor/zforth-41db72d1/src/zforth/zforth.c:205`
  (`return ctx->rstack[RSP(ctx)-n-1];` — third-from-top for `pickr 2`).
- Engine visibility check: `wfsource/source/game/actor.cc:794`
  (`return GetMailboxes().ReadMailbox(...).AsBool();`).
- Per-state IFF generator: `wflevels/qbert_practice/gen_cube.py` —
  state-2 of round 0 is `0xDEDE00` yellow, MATL chunk verified
  byte-correct.
