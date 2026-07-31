# Plan: filesystem-viz on a flat-table + Forth-policy core — Filelight sunburst (P1) + FSN retrofit (P2)

## Context

**This is the start of a *family* of filesystem visualizations, not a one-off.** The desktop
disk-usage tools each pick a different encoding of the same tree — FSN/node-link (shipped),
**Filelight**/radial-sunburst (this), **KDirStat/QDirStat**/squarified-treemap (next), plus the
tiered and dome variants. They differ only in *layout + look*, never in *what they read*. So the
real deliverable here is a **shared core that hosts the family**: one C side that walks the
filesystem and emits a flat numeric table, and a per-view Forth policy that renders it. Adding a
visualization becomes "new emitter + new `.fth` policy," not a new engine subsystem.

We have one visualizer shipped — the FSN node-link browser (`wflevels/filesys/`), whose builder
is a **C++ monolith** (`fsn_build`/`fsn_spawn_tree`: scan → recursive layout → spawn, all in C;
the Director `.fth` just triggers it). This effort does two things:

1. **Build a second view — a 3D Filelight** radial disk-usage **sunburst** as a *walkable relief
   map* (flat sunburst centered on the player, each segment extruded upward by its size; walk
   onto a wedge + button to zoom in).
2. **Adopt — for both views — the architecture from the [zForth investigation §6](../../SRC/WorldFoundry-wbniv/docs/investigations/2026-06-13-zforth-recursion-stack-extension.md):**
   keep the structural work (recursive dir walk, byte sizes, the positions/arcs that need trig)
   in a **C syscall that emits a flat numeric table**, and move the **rendering policy** (size→
   height curve, color ramp, template choice, tiling resolution) into the Director `.fth`, which
   **iterates the table**. The payoff §6 identified:

   > The layout **aesthetic lives in the level's `.fth` and is hot-reloadable** — retune height,
   > color, spacing without recompiling the engine. Flat iteration = constant call depth → **no
   > recursion, no locals juggling, no return-stack bump** ("port the policy, not the recursion").

**Structure decision (answering "separate levels or what?"): separate levels, shared C core.**
`wflevels/filesys/` (FSN tree) and `wflevels/filelight/` (sunburst) stay distinct `.iff`s with
their own Director scripts and scaffolding, but share one set of C primitives in
`engine/stubs/scripting_zforth.cc`. Each view = **its own C emitter + its own Forth policy**
over the shared primitives. A unified runtime view-switcher (one level, toggle tree↔sunburst↔…)
is a future TODO — kept separate now because "update the existing FSN layout" means editing that
level in place.

**Phasing (as requested):**
- **Phase 1 — Filelight (new level)** on the flat-table/Forth-policy core.
- **Phase 2 — retrofit FSN `filesys`** from the C monolith to the same split (its tree-layout
  aesthetics become hot-reloadable too); verify visual + behavioral parity (regression guard).
- **Phase 3 / TODOs** — tiered monument, planetarium dome, unified switcher, procedural mesh.

**Angles are revolutions everywhere they cross into the table or Forth** — the engine's native
Euler unit (`Revolution`; `fsn_spawn_connector:167` divides `atan2` by 2π before
`Euler(Revolution(...))`). A full turn = `1.0`, a 6° wedge = `1/60 ≈ 0.0167` — a plain fraction
in zForth's float cell, so **no π and no trig on the Forth side**. The C emitter does any trig
(`cos/sin/atan2`) internally and stores/returns **revolutions**; Forth only *renders* —
`spawn-template`, `set-rotation` by a revolution value, `set-scale3`, `set-color3`. Height =
`isqrt` (existing word); HSV→RGB = trig-free piecewise-linear arithmetic. (In Filelight the
arc subdivision is a proportional split of the `[0,1)`-turn — so even the *emitter* needs trig
only in `fl-navigate`'s `atan2`, normalized straight back to revolutions.)

---

## Shared C core (the primitives both views render with) — `engine/stubs/scripting_zforth.cc`

Reused as-is from FSN: `fsn_scan`/`FsnEntry` (`:180`), `fsn_spawn`+`fsn_budget_left` (`:98`,`:90`,
exposed as `spawn-template`), `fsn_despawn`+`g_fsn_spawned`+deferred-rebuild (`:228`,`:337`),
`isqrt` (`:801`), and scale/color **from Forth** via existing `write-actor-mailbox` → 3040-42 /
3037-39 (phase-1 FSN already drove these).

New shared primitives (Phase 1 introduces; Phase 2 reuses):
| Word | Sig | Job |
|------|-----|-----|
| `subtree-bytes` (C `fl_subtree_bytes`) | `(path,statBudget)→int64` | recursive byte sum (the metric FSN never had) — used by both views |
| `set-rotation` | `( actor revs -- )` | expose `SetRotation(Euler(0,0,revs))` (the `fsn_spawn_connector:170` path) so Forth aims a spawned actor |
| `set-scale3` / `set-color3` | `( actor sx sy sz -- )` / `( actor 0xRRGGBB -- )` | 3-line Forth helpers over `write-actor-mailbox` (defined in each Director, or as bootstrap words) |

Each view adds **its own emitter + numeric accessors** (no string ever crosses to Forth, per §6).

---

## Mockups

### Filelight top-down — the sunburst you stand in the middle of

```
                          ░░ depth-2 ring ░░  (grandchildren, nested in parent's arc)
                    ┌───────────────────────────┐
                ░░ depth-1 ring ░░  (cwd's children, arc ∝ recursive size)
            ╔═══════════════════════════════════════╗
            ║   src    │   usr    │ home │ var │ …   ║   ← angle ∝ size
        ┌───╫────┬─────┼────┬─────┼──┬───┼─────╫───┐
        │   ║ li │ inc │    │ bin │  │ … │     ║   │   depth-2 nested inside
        │   ║ b  │     │    │     │  │   │     ║   │   each depth-1 wedge
        │   ╚════╪═════╪════╪═════╪══╪═══╪═════╝   │
        │        depth-0 center disk = cwd          │
        │              ╔═════════╗                  │
        │              ║   (P)   ║  ← player at the  │
        │              ╚═════════╝     center        │
        └───────────────────────────────────────────┘
   radius = depth · angle ∝ recursive size · walk OUTWARD onto a wedge to zoom in
```

### Filelight side view — extruded into a walkable relief

```
   height ∝ recursive size
           ▟███▙
          ███████              ▟██▙
         █████████   ▟█▙      ██████      ▁▃▅▃▁
      ▂▄ ███████████ ███ ████ ██████ ████ █████ ▅▃▂
     ════════════════════════════════════════════════  floor (z = 0)
       (P)│  src   │usr│ home │  var  │  …  │ d2 d2 │
       center  └──── depth-1 ring ────┘  └ depth-2 ┘
     the astronaut walks across the relief (visual, like FSN towers — no collision)
```

### Color — per-branch hue (Filelight signature)

```
   depth-1 branch i → hue = i/N around the wheel ; descendants tinted lighter with depth
     src=red   usr=green   home=cyan   var=blue   tmp=magenta
     src/ ███   src/lib/ ▓▓▓   src/lib/x/ ▒▒▒      ← V/S lifted per depth
```

### The §6 split — same for BOTH views, only the emitter + policy differ

```
  ┌──────────── C emitter (structural) ───────────┐    ┌──── Forth Director (policy) ────┐
  │ FSN:  fsn-scan  → rows (x,y, size, tag, …)     │    │ iterate rows:                    │
  │ FL:   fl-scan   → rows (depth,a0,a1,size,branch)│──▶ │   size  → HEIGHT curve   (tune)  │
  │  recursion · strings · cos/sin/atan2 positions  │tbl │   tag   → COLOR ramp     (tune)  │
  │  numeric accessors (seg-/node- *)               │    │   depth → TEMPLATE choice        │
  │  set-rotation · subtree-bytes · spawn-template  │    │   spawn-template/set-rotation/    │
  └─────────────────────────────────────────────────┘    │   set-scale3/set-color3          │
        must be C (the §6 walls)                          └──────── hot-reloadable ──────────┘
```

### Navigation — walk-in to zoom / re-root (both views)

```
   stand at center ──walk onto a depth-1 wedge──▶ press B → that subtree = new center, rebuild
                                                   press C → ascend to parent (floored at start)
   FL: player(x,y) → polar(r,θ) → ring band + arc → segment under foot
```

---

## Phase 1 — Filelight (new level `wflevels/filelight/`)

**C emitter (structure only).** `fl_subdivide(path, depth, a0, a1, branchId)` — scan dirs, split
the `[a0,a1)` arc (**revolutions**) ∝ each child's `subtree-bytes`, cull arcs < `FL_MIN_REV`,
push rows `{depth, a0,a1 (rev), sizeKB, branchId}` to `g_fl_segments`; depth-1 children seed a
new `branchId`. `fl-scan ( -- nSegments )` runs it from the root. Accessors `seg-depth/seg-a0/
seg-a1/seg-size/seg-branch ( i -- v )` — `seg-a0`/`seg-a1` return **revolutions** ∈ [0,1).
(sys 140-146.) `fl-navigate ( -- )` (sys 147): player polar → depth-1
segment under foot, B re-root / C ascend (deferred rebuild), disk play-bounds.

**Forth Director (policy — the LOOK lives here, hot-reloadable).**
```forth
\ wf
: RING1 12 ; : RING2 13 ; : RING3 14 ; : DISK 15 ;
: WEDGE-STEP 0.0167 ;        \ wedge Δ in REVOLUTIONS (≈6°) — tiling resolution, TUNE
: ring-tmpl  ( depth -- tmpl ) ... ;
: size>height ( kb -- sz ) isqrt 1 max 12 min ;          \ HEIGHT CURVE — tune freely
: branch>rgb  ( branch depth -- 0xRRGGBB ) ... ;         \ HUE RAMP (HSV→RGB, no trig)
: tile-seg ( i -- )                                       \ tile one segment's arc with wedges
   dup seg-depth >r  dup seg-a0  over seg-a1
   begin 2dup > while
      0 0 0  r@ ring-tmpl spawn-template  dup >r  over set-rotation
      1 1  2 pick seg-size size>height  r@ set-scale3
      3 pick seg-branch r@ branch>rgb    r> set-color3
      WEDGE-STEP +
   repeat 2drop r> drop ;
10 read-mailbox 0 = if 1 10 write-mailbox  fl-scan 0 ?do i tile-seg loop fi
1906 read-mailbox 6 fl-flydown
fl-navigate  fl-dirty? if despawn-all  fl-scan 0 ?do i tile-seg loop then
```

**Geometry — baked annular-sector wedge templates, instanced as Actors** (zero new render
plumbing; procedural `RenderObject3D` is possible — `MakeCube` `rendacto.cc:219` — but isn't an
`Actor`, so loses scale/color/removal/budget). Bake one **centered-at-origin** annular sector per
ring band (`innerR=d·w, outerR=(d+1)·w`, `w≈9 u`, d=1..maxDepth≈3) + a center disk; a spawned
instance needs only a Z-rotation to sit on its arc. Authoring (`make_annular_sector`, base-pivot
z=0):
```python
def make_annular_sector(name, innerR, outerR, sweep_deg=6, segs=4, h=1.0):
    import math; sw=math.radians(sweep_deg); ang=[i*sw/segs for i in range(segs+1)]
    verts  = [(innerR*math.cos(a),innerR*math.sin(a),0) for a in ang]
    verts += [(outerR*math.cos(a),outerR*math.sin(a),0) for a in ang]
    verts += [(innerR*math.cos(a),innerR*math.sin(a),h) for a in ang]
    verts += [(outerR*math.cos(a),outerR*math.sin(a),h) for a in ang]
    # faces: top cap + radial end caps + outer wall → from_pydata
```
The baked `sweep_deg` **must equal `WEDGE-STEP`** (6° = 0.0167 rev) so tiled wedges abut exactly
— author the mesh in degrees, step the runtime in revolutions; keep the two in sync.
Scaffolding copied from `blender_filesys.py`: astronaut + input routing + `Turn Rate=0.5`,
CamShot, Directional+Ambient lights, floor, room bbox, `'SLOT' 1l`, `Number Of Temporary
Objects 500`.

**P1 files:** `wflevels/filelight/blender_filelight.py`; its build artifacts (via `task build-level -- filelight`); a `task run-filelight`; and the committed plan `docs/plans/2026-06-13-filelight-3d-radial-sunburst.md`.
**P1 changes:** `scripting_zforth.cc` (the `fl_*` emitter + accessors + `set-rotation` + `subtree-bytes` + dispatch 12-19 + bootstrap words); `TODO.md`.

**P1 milestones:** M1 static sunburst (table right, Forth renders it); M2 per-branch hue +
fly-down + **hot-reload check** (edit `.fth` policy only, re-export, look changes, engine binary
untouched); M3 navigable re-root/ascend + disk bounds.

---

## Phase 2 — Retrofit FSN `filesys` to the flat-table split

**Goal:** convert the existing monolith so the *tree-view's* aesthetics are hot-reloadable too,
on the shared core — **without changing how it looks or plays** (regression guard).

**What moves where.** Today `fsn_spawn_tree` (`:244`) interleaves structure + render. Split it:
- **C emitter `fsn-scan ( -- nNodes )`** keeps the structural/trig work — the BFS tree walk, the
  fan-out positions (`30·cos a`, `R·cos/sin`), connector angles (`atan2`), recursive subdivision
  — and **emits flat rows**: a tower row `{x,y, sizeKB, depth}`, a wire row `{x,y, angleRevs,
  lenL, depth}`, and file rows `{x,y,topZ, sizeKB, mtime}` (or fold files into a node flag).
  Numeric accessors `node-x/node-y/node-angle/node-len/node-size/node-kind/node-mtime ( i -- v )`.
- **Forth Director (filesys) renders the rows** applying the policy now hardcoded in C: tower
  height (`isqrt(size)`), the warm→cool age color (port `fsn_color_by_age` math to Forth — it's
  trig-free), wire spawn+`set-rotation`+length-scale, file placement/cap. The existing
  templates (DirTemplate/FileTemplate/ConnectorTemplate, indices 12/13/16) are unchanged.
- `fsn-navigate`/`fsn-flydown` stay C (unchanged behavior).

**Reuse:** `set-rotation`, `subtree-bytes`, `spawn-template`, `set-scale3/color3` from the P1
core. The connector trick (spawn at parent, rotate, X-scale to length) becomes a Forth render
step using a C-emitted angle+length — identical output.

**P2 files:** edit `engine/stubs/scripting_zforth.cc` (replace `fsn_spawn_tree`'s render half
with `fsn-scan` emit + accessors; keep `fsn_subdivide`/positions in C); rewrite
`wflevels/filesys/`'s Director `.fth` (in `blender_filesys.py`) to the render loop; re-export +
`task build-level -- filesys`. Fold the change into
`docs/plans/2026-06-12-filesys-browser-level.md` ("Phase 3: flat-table refactor").

**P2 regression guard:** before/after screenshot parity + identical spawned-actor count + descend/
ascend still works. The retrofit must be visually indistinguishable; the only observable
difference is that editing the filesys Director `.fth` now re-skins the tree with no rebuild.

---

## Build & verify
```bash
task build                                                  # engine: shared core + fl_* emitter
blender --background --python wflevels/filelight/blender_filelight.py   # (P1)
task build-level -- filelight && task run-filelight          # walk the relief, zoom
# P2:
blender --background --python wflevels/filesys/blender_filesys.py
task build-level -- filesys   && task run-filesys            # MUST look/play identical to before
```
Each milestone: headless load (no asserts / "fell out of room"), interactive play-test +
screenshot, actor count vs the 500 cap. **Hot-reload proof (P1-M2 and P2):** change only `.fth`
policy words, re-export, relaunch → look changes, engine binary untouched.

## Follow-up TODOs (captured, not built now)
1. **KDirStat / QDirStat treemap view** — the *other* canonical disk-usage encoding: squarified
   rectangles, area ∝ size, nested by directory. On the same core: a new C emitter runs the
   squarified-treemap layout (rows `{x,y, w,h, depth, tag}`) and a Forth policy spawns a unit
   box per cell, XY-scaled to `w×h`, Z-extruded by size, colored by type/branch. No trig at all
   (axis-aligned rects) — the cleanest fit for the flat-table model yet. ([refs](../../SRC/WorldFoundry-wbniv/TODO.md): QDirStat, Filelight in the design-references entry.)
2. **#2 Tiered monument** — stack the sunburst rings at rising Z (stepped cone); orbit camera.
   Same `fl-scan` table; the Director just adds a per-depth base-Z — a *policy* change, no C edit.
3. **#3 Planetarium dome** — sunburst segments on a hemisphere (azimuth ∝ size, elevation =
   depth); spherical-sector meshes; player looks up.
4. **Unified runtime view-switcher** — one level holding all templates; a mode mailbox selects
   emitter+policy (tree ↔ sunburst ↔ treemap ↔ tiered ↔ dome) live. The natural endpoint once
   the family shares one core.
5. **Procedural single-mesh upgrade** — exact sectors via one runtime `RenderObject3D`
   (per-vertex `Vertex3D.color`); weigh new render plumbing vs. the fidelity gain.

## Out of scope
Real-collision walking on the relief (visual only); breadcrumb HUD; animated fly *into* a wedge;
files-as-segments in Filelight (dirs fan, files fold into the parent's size — the Filelight default).
