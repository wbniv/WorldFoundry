# Face normals for the five species deformers

Follow-up to the [saltwater seahorses plan](2026-10-16-saltwater-seahorses.md) ("Out of scope", first
listed under the E4 "Normals" note). Engine change authorised by Will for this fix only, 2026‑11‑01.

## Problem

The fish, fin, swim, jelly and lion deformers
([`mesh_deformer.cc`](../../wfsource/source/renderassets/mesh_deformer.cc)) rewrite vertex positions every
frame but never touch the face normals. Those are computed once, at load, from the rest pose
([`rendobj3.cc`](../../wfsource/source/gfx/rendobj3.cc), the `FACE` chunk: `CalculateNormal(v0,v1,v2)`).
The software back-face test ([`backface_cull.hp`](../../wfsource/source/gfx/backface_cull.hp)) and the
per-face lighting in the GL renderers (`rendgcl.cc`, `rendftl.cc`, …) both read that stored normal, so on a
bent fish, a flexed fin or a contracted jelly bell they cull and light against the rest pose.

The sixth kind, `DFRM`, already writes face normals: its evaluator recomputes a face that spans two
samples with the loader's winding, `(v1−v0)×(v2−v0)` normalised, keeps the last normal for a degenerate
triangle, and `DfrmDeformer::Pose` stores the result with `Vector3ToPS12` through
`RenderObject3D::GetWritableFaceList()`.

## Design

Reuse the `DFRM` mechanism, not a second one.

1. **One triangle-normal function.** The `FaceRecompute` arithmetic in
   [`dfrm_deform.cc`](../../wfsource/source/renderassets/dfrm_deform.cc) moves into
   `wf_render::TriangleNormal(v0, v1, v2, out)` in a new header,
   [`face_normal.h`](../../wfsource/source/renderassets/face_normal.h): float cross product, normalise,
   `false` (output untouched) when the length is not above 1e‑12. `DFRM` calls it in both places it built a
   triangle normal by hand (`FaceRecompute` each frame, and the rest normal of a `FaceSample` face at
   bind). The operations and their order are the same as before, so its output does not change;
   `dfrm_strand` still passes against the Python reference.
2. **One pass after each pose.** A file-local `RecomputeFaceNormals(const DeformTarget&)` in
   `mesh_deformer.cc` walks the actor's face list once, reads the three posed positions of each face,
   calls `TriangleNormal` and writes the face's normal through `GetWritableFaceList()`, exactly as
   `DfrmDeformer::Pose` writes its normals. A degenerate face keeps its last normal. Each species `Pose`
   calls it after writing positions, only on a successful pose; a refused call (non-finite input, changed
   swim span, other kind bound) returns before any write, so nothing changes.
3. **No allocation, no new buffers.** Every actor that deforms is built by the on-disk
   `RenderObject3D` constructor, which allocates its own face list, so writing it affects only that actor.
   The copy constructor (which shares faces) is used only by particle emitters, and particles are plain
   `RenderObject3D`s with no deformer slot. No shared copy-per-instance buffer, new API or representation
   change is needed.

Cost is one cross product, one square root and three divides per face per posed actor; the measured
numbers are under Verification.

From load to screen, the normals now follow the pose every frame instead of staying at the rest pose:

```mermaid
flowchart LR
    A["Level load:<br/>FACE chunk read"] --> B["rest-pose normals<br/>CalculateNormal(v0, v1, v2)"]
    B --> C["per-frame deform:<br/>species Pose moves vertices"]
    C --> D["RecomputeFaceNormals<br/>(new)"]
    D --> E["back-face cull<br/>N · (centre − eye) &gt; 0"]
    D --> F["per-face lighting"]
    B -. "before the fix:<br/>stale rest normals" .-> E
    B -. "before the fix" .-> F
```

Inside one call, the recompute runs after the positions are written and before anything is drawn:

```mermaid
flowchart LR
    S["Forth: fish-deform / fin / swim / jelly / lion-pose"] --> D["RenderActor3D::Deform"]
    D --> P["species Pose:<br/>write vertex positions"]
    P -->|refused input| X["return status,<br/>nothing written"]
    P -->|posed| N["RecomputeFaceNormals:<br/>one pass over faces"]
    N --> T["wf_render::TriangleNormal<br/>(v1−v0)×(v2−v0), normalised"]
    T -->|degenerate| K["keep last normal"]
    T -->|ok| W["faces[f].normal ="]
    W --> C["software back-face cull<br/>(backface_cull.hp)"]
    W --> L["per-face lighting<br/>(GL renderers)"]
    F["DFRM evaluator FaceRecompute"] --> T
```

One frame, in order, across the script, the deformer, the mesh and the renderer:

```mermaid
sequenceDiagram
    participant Scr as Forth actor script
    participant RA as RenderActor3D
    participant Def as species MeshDeformer
    participant Mesh as RenderObject3D
    participant GL as Renderer
    Scr->>RA: fish-deform (channels)
    RA->>RA: reject non-finite input, Check()
    RA->>Mesh: GetWrittableVertexList()
    RA->>Def: Bind() on the first call only
    RA->>Def: Pose()
    Def->>Mesh: write vertex positions
    Def->>Mesh: RecomputeFaceNormals: GetWritableFaceList(), one pass
    Def-->>RA: status
    Note over RA,GL: later in the same frame
    GL->>Mesh: read positions and face normals
    GL->>GL: cull with N · (centre − eye), light with N
```

The slot has two states, and only a successful pose in the bound state writes anything:

```mermaid
stateDiagram-v2
    [*] --> Unbound
    Unbound --> Bound: first valid call, Bind() ok
    Unbound --> Unbound: refused (bad input, no metadata)
    Bound --> Bound: Pose() ok, positions and normals written
    Bound --> Bound: refused (non-finite, span changed, other kind), nothing written
```

## Mockups

The change has a visible surface: what is lit and what is culled on every animated species mesh. Each
page below takes the real aquarium mesh, posed by the engine's own deformer (`deformer_golden_test
--dump`, the same steps as the golden test), and re-renders it in a canvas at rest, mid and extreme
(clamped) poses: the top row with the rest-pose normals the engine kept before the fix, the bottom row
with recomputed normals. Culling is the engine's test, the background is magenta so that holes show,
and yellow outlines mark faces whose cull decision is wrong (a front face dropped, or a back face
drawn). The camera is chosen from the mesh data, as the next section proposes: of 256 directions, the
one where the faces that change cover the most screen area at the extreme pose. These are software
re-renders of engine poses, not device or desktop captures; `scripts/deformer-normals-mockups.py`
regenerates them.

| Deformer | Extreme pose before the fix | Mockup |
|---|---|---|
| Fish (clownfish body, 310 faces) | 5 front faces culled, 31 back faces drawn, normal error up to 0.35 | [![Fish: before and after](2026-11-01-deformer-face-normals/fish.png)](2026-11-01-deformer-face-normals/fish.html) |
| Fin (betta tail, 896 faces) | 118 culled, 120 drawn, error up to 1.00 | [![Fin: before and after](2026-11-01-deformer-face-normals/fin.png)](2026-11-01-deformer-face-normals/fin.html) |
| Swim (rainbow goby fins, 328 faces) | 15 culled, 75 drawn, error up to 1.75 | [![Swim: before and after](2026-11-01-deformer-face-normals/swim.png)](2026-11-01-deformer-face-normals/swim.html) |
| Jelly (bell, 390 faces) | 8 culled, 25 drawn, error up to 0.30 | [![Jelly: before and after](2026-11-01-deformer-face-normals/jelly.png)](2026-11-01-deformer-face-normals/jelly.html) |
| Lion (lionfish, 4068 faces) | 444 culled (the pectoral fin), error up to 0.63 | [![Lion: before and after](2026-11-01-deformer-face-normals/lion.png)](2026-11-01-deformer-face-normals/lion.html) |

To regenerate: build `deformer_golden_test`, run it with `--dump` into a scratch directory, then
`scripts/deformer-normals-mockups.py <scratch> docs/plans/2026-11-01-deformer-face-normals`, and take each
PNG with `google-chrome --headless=new --window-size=1440,900 --screenshot=<page>.png file://<page>.html`
(quantised to 256 colours to stay under 512 KB).

## Deliberately ugly visual regression case

**Status, 2026‑11‑01:** not built in the engine. The camera choice from mesh data and the before/after
comparison are done offline in the Mockups above; the in-engine diagnostic shot, the `WF_CULL=0`
control, the review clip and the automated cull-area check described here remain open.

Use the real `swim_goby_fins` mesh, not a synthetic triangle. Its third golden-test pose is already an
extreme but accepted deformation:
`SetSwimDeformation(-.4, .03, .01, -1.6, .3, -0.46, .34)`; the fin amplitude clamps as it does in
gameplay. Before the fix, its worst face normal differs from the posed geometric normal by **1.75**
in vector length (more than 120°). This is the best existing case for making the culling error look
like a torn fin rather than a subtle lighting change.

Make one isolated diagnostic shot with that fin enlarged to fill most of the frame, a saturated
magenta background behind it, low ambient light and one hard white side light. Keep mesh, pose,
camera, light, material and `WF_CULL=1` identical for the two builds. Choose the camera *from the
mesh data*: over a fixed grid of view directions, evaluate `WfFaceIsBackfacingAt` once with the
stored rest normal and once with the posed triangle normal, then choose the direction with the
largest **projected area** of disagreeing fin faces. Put the camera on that ray at three mesh
radii, looking at the posed fin's centroid. This removes guesswork about which side of a thin fin
will show the fault. Save the selected direction, pose values and mesh hash in the fixture so the
shot is repeatable.

| Frame | Expected visual result |
| --- | --- |
| Rest pose, either build | Continuous fin; baseline for geometry and light. |
| Extreme pose, old stored normals | Magenta background cuts through the bent fin where front-facing triangles were wrongly culled; surviving triangles have abrupt light bands. |
| Same extreme pose, recomputed normals | Fin remains continuous and the light follows its bend. Vertex positions must match the old build bit for bit. |

Also render the extreme pose with `WF_CULL=0` in both builds. The holes should disappear in that
control while stale-normal lighting remains, separating culling from shading. For a short review
clip, alternate rest and extreme pose every half second; the old build should visibly pop or
flicker at the bend, while the fixed build should move continuously. Show the two builds side by
side and include a red pixel-difference overlay; label this as a diagnostic comparison, not a
gameplay screenshot.

The automated check should record the chosen camera, the count and projected area of faces whose
cull decision differs, and the maximum normal error. It should fail without recomputation and
pass with it; the existing golden position comparison guards against a geometry change. Review
the actual render before setting a pixel-area threshold, since an isolated tiny face could pass a
face-count assertion while still being invisible to a person. If the goby fins occupy too little
screen area even when enlarged, repeat the same setup with the larger `fin_betta_tail` mesh and
its third golden-test pose (`1.56, .4, -.3, .3`, with clamps).

## Effect on recordings

Positions are unchanged, so the `deformer_golden` position fixtures stay bit-identical. Rendered output
of every tank with a species deformer changes slightly (lighting follows the bend; a few back faces near
the bend flip). The committed Linux frame reference
`tests/fixtures/renderer/aquarium-linux-frame20.png` is checked by `test_renderer_references_fresh.py`;
it is re-rendered if, and only if, that test fails after the change. It passed (Verification step 4),
so nothing was re-recorded. No other committed file is a rendered regression reference for these
tanks. The captures under `docs/diagnostics/` and in older plan bundles are dated evidence of what a
device showed at the time, not references any test compares against, so they are left as they are.

## Verification

**Where it ran (2026‑11‑01).** The Linux test container could not be used: the image was not in the local
store and building it needs about 700 MB, while the root disk had 2.3 GB free and fell under 650 MB while it
built, so the build was stopped. Steps 1–4 ran on the host instead, with every build directory and the
unpacked Jolt sources in tmpfs (`/tmp`), so the root disk was not written. The host is
an i7‑1185G7 that was shared with other sessions (load average 8–11 on 8 threads).

1. Deformer tests pass in the Linux container, including the new normal check (every face of every posed
   species mesh equals a fresh `CalculateNormal` of its deformed vertices within 1e‑4):
   `scripts/in-linux-container.sh bash -c 'cmake --build /build/dfn --target deformer_golden_test dfrm_strand_test && ctest --test-dir /build/dfn -R "deformer_golden|dfrm_strand" --output-on-failure'`

    Run on the host, Release, as `cmake --build <tmpfs>/b --target deformer_golden_test dfrm_strand_test && ctest -R "deformer_golden|dfrm_strand" --output-on-failure`:

    ```
    1/2 Test #3: deformer_golden ..................   Passed    0.36 sec
    2/2 Test #4: dfrm_strand ......................   Passed    6.12 sec
    100% tests passed, 0 tests failed out of 2
    ```

    ```
    ok   fish_clownfish_body    normals: 310 faces, max error 6e-08
    ok   fish_clownfish_body    6 steps, 3559 words identical
    ok   fin_betta_tail         normals: 896 faces, max error 6e-08
    ok   fin_betta_tail         5 steps, 6911 words identical
    ok   swim_arowana_body      normals: 5000 faces, max error 6e-08
    ok   swim_arowana_body      5 steps, 52791 words identical
    ok   swim_goby_body         normals: 484 faces, max error 6e-08
    ok   swim_goby_body         4 steps, 3017 words identical
    ok   swim_goby_fins         normals: 328 faces, max error 6e-08
    ok   swim_goby_fins         3 steps, 2065 words identical
    ok   jelly_bell             normals: 390 faces, max error 6e-08
    ok   jelly_bell             5 steps, 3486 words identical
    ok   lion_lionfish          normals: 4068 faces, max error 6e-08
    ok   lion_lionfish          5 steps, 37536 words identical
    ```

    **PASS** (on the host, not in the container). The position fixtures are still bit-identical.

2. The normal check bites: with the five `RecomputeFaceNormals` calls removed, `deformer_golden` fails on
   the normal check for all seven cases.

    Run as the new test against the engine before the fix (same tree, built before the engine edit), which
    is the same thing as removing the calls:

    ```
    FAIL fish_clownfish_body    normals: max error 0.502 over 310 faces (tolerance 1e-04)
    FAIL fin_betta_tail         normals: max error 1 over 896 faces (tolerance 1e-04)
    FAIL swim_arowana_body      normals: max error 0.171 over 5000 faces (tolerance 1e-04)
    FAIL swim_goby_body         normals: max error 0.931 over 484 faces (tolerance 1e-04)
    FAIL swim_goby_fins         normals: max error 1.75 over 328 faces (tolerance 1e-04)
    FAIL jelly_bell             normals: max error 0.302 over 390 faces (tolerance 1e-04)
    FAIL lion_lionfish          normals: max error 0.699 over 4068 faces (tolerance 1e-04)
    ```

    (the seven position lines were `ok … identical`.) **PASS**: all seven cases fail without the fix.

3. Per-call cost: `deformer_golden_test /src /src/tests/fixtures/deformer_golden --bench` in the container,
   with and without the recompute, Release build.

    On the host, the binary from before the fix and the one after, interleaved three times; 20 000
    steady-state `Deform` calls each; the median of the three runs, in µs per call:

    | Case | Vertices | Faces | Before | After | Added |
    |---|---:|---:|---:|---:|---:|
    | fish_clownfish_body | 193 | 310 | 0.47 | 8.5 | 8.0 |
    | fin_betta_tail | 450 | 896 | 4.9 | 28.0 | 23.1 |
    | swim_arowana_body | 3514 | 5000 | 24.1 | 158.2 | 134.1 |
    | swim_goby_body | 250 | 484 | 2.0 | 14.0 | 12.0 |
    | swim_goby_fins | 228 | 328 | 2.2 | 10.4 | 8.2 |
    | jelly_bell | 229 | 390 | 7.0 | 14.8 | 7.8 |
    | lion_lionfish | 2499 | 4068 | 76.3 | 174.4 | 98.1 |

    That is about 20–27 ns per face on this loaded host. The face loop alone, compiled standalone with the
    same flags, measured 19–27 ns per face on the same host at the same time. The loop is about 25 SSE
    instructions with one `sqrtss` and two divides per face, no calls and no allocation, so an unloaded
    core should be several times faster. Replacing the three divides by one reciprocal and three multiplies
    made no measurable difference, so the exact division stays, which keeps `DFRM` bit-identical.
    **PASS** (measured; the Chromecast cost is not measured, see step 5).

4. The Linux frame references are fresh: `test_renderer_references_fresh.py` in the Linux container.

    On the host instead (`task build`, with its object directory linked into tmpfs; host GL on the desktop
    display, which is where the references came from):

    ```
    ============================== 2 passed in 9.88s ===============================
    ```

    The aquarium capture compared directly with its reference:

    ```
    640x480: exact=307198/307200 (99.999349%)
    max channel delta histogram: {0: 307198, 1: 2}
    pixels exceeding tolerance 3: 0
    PASS
    ```

    **PASS**: frame 20 of `aquarium-standalone.iff` differs from the reference in 2 pixels by 1 level, so
    `aquarium-linux-frame20.png` is not stale and was not regenerated.

5. On a Chromecast, every tank of the eight-tank selector opens and animates (coordinator job).

    **Not run.** It needs an APK built from this change, and the root disk had under 1 GB free (at one
    point 349 MB) throughout, while an Android build needs several GB. No coordinator job was submitted.
    The `[verify T3]` TODO entry carries this step.
