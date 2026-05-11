# Per-cube scripts vs. director-only — Q*bert cube logic shape

**Date:** 2026-05-11
**Context:** [Phase 1 cube consolidation plan](../plans/2026-05-10-qbert-cube-consolidation.md) shipped with all cube logic centralised in the director script. This investigation explores what it would look like if each of the 28 cubes had its own script instead — what gets simpler, what gets harder, and what the engine actually forbids today.

## TL;DR

- The cubes are [statplat](../../wftools/wf_oad/tests/fixtures/statplat.oad) actors. **The engine asserts that StatPlats have no script and no local mailboxes** at [actor.cc:679-681](../../wfsource/source/game/actor.cc) — so per-cube scripts are not just a "would they be nicer" question; they require either lifting that restriction or switching cubes to a non-StatPlat schema.
- The actual savings — and they are real — are mostly **clarity**: each cube's state-detect-and-recolor logic is currently encoded as a Forth `28 0 do … loop` in the director, addressing peer actors via `write-actor-mailbox`. A per-cube script reduces that to ~3 lines of "read my own state, write my own color" — no peer addressing, no `CUBE_ACTOR_BASE` indirection, no shared 28-slot mailbox arrays for state/prev-state.
- Costs are real too: 28 `NonStatPlatData` instances instead of 0, a Jolt body kind that isn't `JoltMakeStatic()`, 28 scriptinterpreter VMs ticking per frame instead of 1, and engine work to either teach StatPlats to run scripts or swap the cube schema.
- Net: **worth doing later** once the cube logic outgrows what's expressible in a single director loop (e.g. once enemies start landing on cubes and triggering per-cube animations / sound / particle spawns). For today's Phase-1 colour-swap workload, the director-only design is the right shape.

## What the engine forbids today

[actor.cc:674-688](../../wfsource/source/game/actor.cc), the `Actor::Init()` StatPlat path:

```cpp
if ( objdata->type == Actor::StatPlat_KIND )
{
    _nonStatPlat = const_cast<NonStatPlatData*>( &_statPlatData );

    AssertMsg( GetCommonBlockPtr()->Script == -1,
               *this << " -- No scripts allowed on StatPlat's" );
    AssertMsg( !GetCommonBlockPtr()->ScriptControlsInput,
               *this << " -- No scripts [and therefore no Script Controls Input] on StatPlat's" );
    AssertMsg( GetCommonBlockPtr()->NumberOfLocalMailboxes == 0,
               *this << " -- No local mailboxes allowed on StatPlat's" );
    AssertMsg( GetMovementBlockPtr()->Mobility == MOBILITY_ANCHORED,
               *this << " -- StatPlat's must be anchored …" );
#ifdef PHYSICS_ENGINE_JOLT
    _physicalAttributes.JoltMakeStatic();
#endif
}
else
{
    _nonStatPlat = new (theLevel->GetMemory()) NonStatPlatData(...);
    …
    _InitInput( startupData );
    _InitScript( startupData );
}
```

`_nonStatPlat` is the actor's per-frame mutable state block — animation manager, hitpoints, **script interpreter, local mailbox array, input handler**. StatPlats share **one** static `_statPlatData` sentinel and pay none of that per-actor cost. That's the whole point of the StatPlat kind: a "decorative geometry that never thinks" optimisation for cubes/walls/floors/pillars.

The Phase-1 cubes need to be `MOBILITY_ANCHORED` (Jolt static bodies, no movement, no AI, no physics queries except as collision targets) and they pay no `NonStatPlatData` cost. That's where the per-cube ~7 KB savings in the [cube-consolidation plan's measured 92% reduction](../plans/2026-05-10-qbert-cube-consolidation.md) come from.

So adding scripts to cubes is **architecturally a regression toward the pre-Phase-1 cost curve** — not all of it (we'd still share `cube.iff`, still skip RenderObject3D fan-out), but a chunk of it.

## What "per-cube script" actually looks like (sketch)

### Each cube's Forth (replaces ~30 lines of director loop)

```forth
\\ wf cube per-tick — runs on every cube actor
\\ Reads its own state from local mb 0..2 (replacing global mb 200+N / 228+N).
\\ Writes its own FACE_COLOR mailboxes directly — no write-actor-mailbox.

\\ Local mailboxes:
\\   0  STATE        (0=unvisited, 1=in-progress, 2=cleared)
\\   1  PREV_STATE   (last tick's STATE)
\\   2  (reserved for future per-cube animation phase / particle countdown)

\\ Globals it reads (no writes):
\\   425  ROUND_NUMBER   — director-owned
\\   256+ ROUND_TOP_LUT  — director-populated 48-entry table

\\ State-change detect → write own TOP color.
0 read-mailbox 1 read-mailbox over over <> if
  drop                                    \\ ( cur )
  425 read-mailbox 3 * over + 256 + read-mailbox  \\ ( cur rgb )
  3037 write-mailbox                      \\ FACE_COLOR_TOP on self
  1 write-mailbox                         \\ PREV_STATE := cur
else
  drop drop
then
```

That's the **entire** per-cube tick. No peer addressing. No `CUBE_ACTOR_BASE` arithmetic. No 28-iter loop. The director shrinks correspondingly — it loses ~30 lines of per-tick fan-out and keeps only:

- Round/level state machine
- Win check (count cubes with STATE != 2 — still needs global mb 200..227, OR a different signalling pattern, see below)
- Level transition broadcasts (LIT/SHADOW — still applies to all 28 cubes; see below)

### What does and doesn't simplify

| Concern | Director-only (current) | Per-cube script |
|---|---|---|
| Per-cube state change → own TOP color | 30-line `do…loop` in director | 3 lines per cube, no peer addressing |
| Level transition LIT/SHADOW broadcast | Director iterates `28 0 do … write-actor-mailbox loop` | **Same shape** — director still has to tell 28 cubes. Per-cube scripts could pull (each tick check "did level change since last tick?") but that means 28 reads per frame forever, vs. director writes 56 mailboxes per ~80s. Push is cheaper. |
| Win check (count cleared cubes) | Director loops global mb 200..227 | Two clean options: (a) keep global state mb's as a write-through cache that each cube updates after its own state change — director still loops 28 — or (b) message-port style: each cube on becoming cleared increments a director-owned counter via `write-actor-mailbox`. (b) avoids the per-frame scan entirely. |
| Player landing on cube → state advance | Player script computes `(row, col) → mb 200+N` and pokes global state | Player would need to know each cube's actor-index and write to its local STATE mailbox via `write-actor-mailbox`. Roughly the same arithmetic, just a different target namespace. |
| `CUBE_ACTOR_BASE` indirection | Required (director addresses peers by index) | Disappears for state changes; still needed for whoever does the level-transition broadcast (still the director) |
| First-tick palette init | Director loops + broadcasts | Each cube does its own; director still owns the ROUND_TOP_LUT data |
| Total Forth LOC | Director: ~150 cube-related lines | Director: ~50 lines; each cube: ~10 lines = 1× cube script + 28× actors referencing it |

### Net Forth complexity

Per-cube wins on the most-touched code path (state→colour, runs every cube every tick) at the cost of having cube logic split across two files. The split itself isn't bad — it's the same shape as player + director today.

## Engine costs

### Option A: switch cubes from StatPlat → Platform (or new "ActiveStatPlat")

Requires:
- Switch the cube schema from [statplat.oad](../../wftools/wf_oad/tests/fixtures/statplat.oad) → [platform.oad](../../wftools/wf_oad/tests/fixtures/platform.oad). The names line up with the class hierarchy: **`StatPlat: public Actor`** ([statplat.hp:49](../../wfsource/source/game/statplat.hp)) and **`Platform: public Actor`** ([platform.hp:52](../../wfsource/source/game/platform.hp)) are *sibling* `Actor` subclasses. `StatPlat` is the "Static Platform" — anchored geometry with no script, no local mailboxes, no NonStatPlatData (the four asserts above are the optimisation). `Platform` is the scriptable counterpart, built for moving floors but accepts `Mobility = Anchored`. ([Director](../../wfsource/source/game/director.hp), by contrast, is invisible-logic-only — no mesh, no body — which is what `director_obj` itself uses; not a candidate for cubes.)
- 28 × `NonStatPlatData` allocations from level memory. Rough estimate: at minimum a script-interpreter handle (a few hundred bytes for a zForth VM state), an `AnimManager*`, hitpoints scalar, shield slot, plus the local-mailbox array (3 cells × 4 bytes if we use the minimal layout above). Call it ~1–2 KB per cube × 28 = **~30–60 KB** added back to HalLmalloc.
- Jolt: today's `_physicalAttributes.JoltMakeStatic()` only fires under the StatPlat branch. The Platform branch creates a dynamic-by-default body; we'd need a code path that says "anchored Platform → static body" so we don't pay 28 dynamic-body costs (Jolt dynamic-body memory is several × static).
- Per-frame: 28 script interpreters tick instead of 1. Each script is ~10 zForth ops on the steady-state path (state-change detect that almost always returns "no change"). zForth is a threaded interpreter; per-op cost is sub-µs on Linux but real on PSX-class targets. Worst case 28 × 10 ops × 60 Hz = 16800 op-dispatches/sec — dust on Linux, measurable on a 33 MHz R3000.

### Option B: lift the StatPlat script restriction

The four asserts at [actor.cc:679-682](../../wfsource/source/game/actor.cc) date back to the StatPlat optimisation as a memory measure — StatPlats use the static `_statPlatData` sentinel to skip per-actor allocations. Lifting them means:

- StatPlats that opt in to scripts must own a real `NonStatPlatData`. Effectively this collapses into "StatPlat is the same as Platform-with-anchored when scripted" — i.e., Option A with extra steps.
- Or: add a `NonStatPlatData_Lite` with only the script-interpreter + minimal local mailbox slab, skipping animation/input/hitpoints. ~200 bytes/actor instead of ~2 KB. **This is the interesting variant** — it would let StatPlats grow scripts at proportional cost.

Either way, this is an engine project of meaningful size (probably a couple-day plan, with careful Jolt body-kind reconciliation), not a 30-LOC change.

## When per-cube scripts actually pay off

The current Phase-1 workload is colour swaps driven by state changes. That's about the **simplest** thing a per-cube script could do, and the director loop expresses it perfectly well. Per-cube scripts become *required* (or strongly preferred) when cube behaviour stops being "uniform 28-way data fan-out" and starts being "each cube has its own animation phase / particle countdown / sound trigger / disc-attachment / spinning-disc kind / Coily-rebuff state." Concretely:

| Future feature | Director-only fit | Per-cube script fit |
|---|---|---|
| Flashing colour cycle when round-clear latches | Easy — director loops 28 cubes, sets phase | Easy — each cube ticks its own phase |
| Per-cube particle burst on landing | Awkward — director would need a 28-slot "particle countdown" array | Natural — local mb tracks own countdown |
| Disc-occupied cubes (Levels 2+) | Director needs to encode which cubes are disc-attached | Each cube knows its own role |
| Sound on cube state change | Director has to enqueue 28 possible sounds | Each cube fires its own SOUND mailbox locally |
| Cube destroy / regrow (boss-room style) | Director enumeration | Per-cube state machine |
| Per-cube ambient bob/jiggle | Doesn't fit director — every cube would need its own animation phase, which is exactly what a per-cube script provides naturally |

The crossover point is somewhere around "any per-cube behaviour with its own clock." Until then, the director-only design is correct.

## Recommendation

Defer. Stay with the director-only design for Phase 1 and any near-term enemy-AI / disc-attach / flashing-clear work that can still be expressed centrally. **Revisit when** the first per-cube *animated* state lands (particle burst on landing is the most likely first trigger) — at that point sketch a real plan that:

1. Picks Option A vs. Option B (probably B with `NonStatPlatData_Lite`).
2. Migrates state ownership: local STATE/PREV_STATE per cube; director-owned ROUND_NUMBER and ROUND_TOP_LUT only.
3. Replaces the state-change scan with either write-through globals (cheaper for win-check) or message-port style (cheaper for state-change handling).
4. Re-measures HalLmalloc to ensure the regression is bounded (target: <1 MB added).

Until then, the Phase-1 design holds.

## See also

- [Phase 1 cube consolidation plan](../plans/2026-05-10-qbert-cube-consolidation.md) — director-only design and measured savings
- [actor.cc:670-705](../../wfsource/source/game/actor.cc) — StatPlat vs non-StatPlat init paths
- [statplat.hp](../../wfsource/source/game/statplat.hp), [platform.hp](../../wfsource/source/game/platform.hp), [director.hp](../../wfsource/source/game/director.hp) — sibling `Actor` subclasses; StatPlat is the script-free "Static Platform" optimisation of Platform
