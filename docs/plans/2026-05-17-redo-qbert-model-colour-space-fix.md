# Redo Q✱bert — model + colour-space fix

**Status:** DONE (commit `0215c30f`) — sRGB→linear colour fix + arcade-faithful Q*bert player model.

## Context

The catalogue PNG of Q✱bert renders him yellow with a short pale beak — neither matches the arcade. Two root causes, addressed together:

1. **Wrong colour from sRGB-as-linear mismatch.** [`blender_create_qbert.py:367-375`](../../wflevels/qbert_practice/blender_create_qbert.py) `_make_principled_material` writes the RGB triple straight into `BSDF.Base Color.default_value`. Blender treats that socket as **linear**, but the authored values are sRGB (`(1.00, 0.53, 0.00)` is `#FF8700` — saturated arcade orange). Pushed in as linear, the green channel over-brightens on its way back to sRGB display and the hue shifts to yellow. Same bug affects every other material made through this helper (greenball, coily egg purple, etc.).
2. **Snowman silhouette with too-stubby snout.** Current model is two separate spheres (body + head), a short cone (`depth=0.45`, `radius1=0.18 → radius2=0.10`), white eye spheres with no pupils, and two visible cylinder legs. Arcade Q✱bert is a single ovoid, long tubular proboscis, big eyes with black pupils, no visible legs.

Outcome: an arcade-faithful Q✱bert that reads as orange in both the in-engine view and the catalogue render, with the trumpet snout silhouette.

User confirmed scope: **arcade standard reference, full overhaul**.

## Reference images (what to match)

Canonical 1982 Gottlieb arcade Q✱bert. Designed by Jeff Lee. The character is described in [Wikipedia's Q✱bert article](https://en.wikipedia.org/wiki/Q*bert) as a *"two-legged, big-nosed, orange creature that jumps around on a pyramid"* with an *"armless spherical body"* and a *"tubular nose"* (from which the prototype shot "mucus bombs", later removed).

Images downloaded to `docs/qbert/refs/` in the repo (md-to-pdf.sh embeds local files, not remote URLs — see follow-up note at end of plan):

**Gameplay screenshot — pyramid in play, characters visible (PLAYER 1 / LEVEL 1 / ROUND 1):**

![Q*bert arcade gameplay screenshot showing the pyramid mid-game](/home/will/WorldFoundry.2026-new-level/docs/qbert/refs/qbert-arcade-gameplay.png)

**Original arcade cabinet artwork (side art) — the canonical character reference:**

![Q*bert arcade cabinet side-art showing the character with trumpet nose, big eyes, two feet, no legs](/home/will/WorldFoundry.2026-new-level/docs/qbert/refs/qbert-arcade-cabinet.jpg)

**Jeff Lee's original concept sketch (pyramid + character iterations):**

![Jeff Lee's original Q*bert concept sketch on graph paper](/home/will/WorldFoundry.2026-new-level/docs/qbert/refs/qbert-concept-sketch.jpg)

Source: [Wikipedia — Q✱bert](https://en.wikipedia.org/wiki/Q*bert). Sprite-sheet PNG with every direction and animation frame: [The Spriters Resource — Q✱bert (Arcade), asset 60496](https://www.spriters-resource.com/arcade/qbert/asset/60496/) (browser-only; Spriters Resource returns 403 to programmatic fetches).

**Key silhouette features to reproduce:**
- Spherical orange body with the head merged smoothly into the top (no neck gap — reads as one continuous ovoid in profile, slightly more elongated vertically than wide).
- Long **tubular** snout (cylinder, not a quick taper cone) projecting forward; subtle flare at the tip ("trumpet bell") — arcade sprite is a 2D pixel approximation but the bell silhouette is clearly suggested.
- Two large round eyes with **black pupils** (white sclera, dark dot) on the forward face, just above the snout.
- Two stubby orange **feet** directly under the body — no visible legs sticking out as cylinders; the body's underside meets the feet directly (arcade sprite shows tiny stubs at most).
- **No arms.** "Armless spherical body" is explicit.
- All-orange body+head+feet+snout. The snout is the same orange in the arcade sprite (the existing `mat_snout` pale-peach is a stylistic embellishment — switch to body orange for faithfulness).

## Recommended approach

### Step 1 — Colour-space fix (single function, fixes every material)

Edit [`_make_principled_material`](../../wflevels/qbert_practice/blender_create_qbert.py#L367) to convert sRGB → linear before writing to the BSDF socket. Keep `mat.diffuse_color` (viewport solid-shade) as the sRGB value since that channel is already sRGB-managed.

```python
def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _make_principled_material(name, rgb):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        lin = tuple(_srgb_to_linear(c) for c in rgb)
        bsdf.inputs['Base Color'].default_value = (*lin, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat
```

This single edit corrects every actor's colour authored through the helper. The arcade-orange body `(1.00, 0.53, 0.00)` will render as actual orange (`#FF8700`) in Blender and through the .iff export pipeline. Same fix is mirrored in [`docs/qbert/catalogue/render_cards.py`](../../docs/qbert/catalogue/render_cards.py) `_make_emission_material` — it already has a proper `hex_to_rgb_linear` for cube faces, but I'll add the same path for any new actor materials it might create.

### Step 2 — Rebuild the Q✱bert mesh in `_build_qbert_player_mesh`

Replace [`_build_qbert_player_mesh`](../../wflevels/qbert_practice/blender_create_qbert.py#L378) (lines 378–464) with an arcade-faithful version. Keep the function signature (returns one joined mesh named `QbertPlayerMesh`) so the caller at line 467+ doesn't change.

| Part | Current | New (arcade-faithful) |
|------|---------|-----------------------|
| Body | UV sphere r=0.55 at z=0.55 | UV sphere r=0.60 at z=0.70, scaled to (1.0, 1.0, 1.15) — vertically ovoid orange ball. |
| Head | Separate UV sphere r=0.40 at z=1.25 | UV sphere r=0.45 at z=1.20, smoothly *intersecting* the body (no neck gap); same `mat_orange`. Joins so silhouette reads as one continuous form (snowman-merged-into-pear). |
| Snout | Cone r1=0.18→r2=0.10, depth=0.45 at x=0.40 | **Trumpet** in three pieces, all `mat_orange` (same colour as body — arcade sprite is monochrome orange): (a) cylinder length 0.40, r=0.09 — tube; (b) flared cone r1=0.09 → r2=0.16, depth=0.12 — bell; (c) tiny flat ring cap at the bell mouth. Anchored at x=0.30 on the head, tip at x≈0.85. |
| Eyes (white) | Two UV spheres r=0.07 at x=0.30, y=±0.14, z=1.40 | Larger: r=0.12 at x=0.28, y=±0.18, z=1.40. `mat_eye` (white). |
| Eye pupils (new) | — | Two small black UV spheres r=0.05 at x=0.37, y=±0.18, z=1.40, just in front of the white spheres. New `mat_pupil = (0.02, 0.02, 0.02)`. |
| Legs | Two cylinders r=0.13 depth=0.30 at z=0.15 | **Near-vanishing stubs**: shrink to cylinders r=0.10 depth=0.10 at z=0.10. Wikipedia describes Q✱bert as "two-legged", so keep just enough geometry to read as a tiny knee — but the cylinders no longer protrude awkwardly. `mat_orange`. |
| Feet | Two flattened spheres at z=0.04 | Bigger and tucked directly under the body: flattened UV sphere r=0.24, scale (1.3, 1.0, 0.35), at z=0.05, y=±0.22, front at x=+0.10. Same `mat_feet` (slightly darker orange — gives the feet visual separation from the body even though arcade sprite uses one orange shade). |

Removed: `mat_snout` is unused after this change (snout is `mat_orange`). Pupils add `mat_pupil`. Net material count: 4 (was 4).

Vert budget after redesign: body 60 + head 50 + snout-tube 20 + snout-bell 16 + snout-cap 8 + eyes 2×30 + pupils 2×16 + leg-stubs 2×12 + feet 2×24 ≈ **270 verts**. Slightly over the prior ~250 ceiling — if pool pressure shows up at build time, drop the leg stubs (saves 24) per `feedback_check_git_diff_before_bumping_pools`.

### Step 3 — Rebuild artefacts

1. Re-run `blender_create_qbert.py` in Blender to regenerate `qbert_practice.blend` (joined mesh + actor wiring intact).
2. Run the level build pipeline per the memory `feedback_qbert_blender_build_pipeline` — build the .lev binary and run iffcomp standalone so `player.iff` reflects the new mesh.
3. Spot-check by booting the level (`task run-debug` or the standard run script for qbert_practice).

### Step 4 — Refresh the catalogue render

Re-run the Blender headless render so `docs/qbert/catalogue/actor_player.png` shows the new orange trumpet-snouted Q✱bert. No other catalogue file changes needed:

```sh
blender --background wflevels/qbert_practice/qbert_practice.blend \
        --python docs/qbert/catalogue/render_cards.py
```

This will also re-render the 12 other actor PNGs and the 17 pyramid PNGs with the corrected colours. Side effect: the redball/greenball/coily egg colours will *also* shift slightly (toward their true sRGB targets). That's the right outcome — the prior renders were uniformly mis-managed.

## Critical files

- **Edit:** [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) — `_make_principled_material` (lines 367–375) and `_build_qbert_player_mesh` (lines 378–464).
- **Re-run (no edit):** [`docs/qbert/catalogue/render_cards.py`](../../docs/qbert/catalogue/render_cards.py) — refreshes catalogue PNGs.
- **Regenerated artefacts:**
  - `wflevels/qbert_practice/qbert_practice.blend`
  - `wflevels/qbert_practice/player.iff`
  - `wflevels/qbert_practice/qbert_practice.lev`, `.lev.bin`, `.iff`
  - `docs/qbert/catalogue/actor_player.png` (plus the rest as a side-effect refresh)

## Verification

1. **py_compile** of `blender_create_qbert.py` after edit, per `feedback_py_compile_check`.
2. **Build chain:** open the .blend (or run via Blender), re-run the Python file inside Blender, build .lev + standalone .iff per `feedback_qbert_blender_build_pipeline`.
3. **In-game visual check:** boot the level — Q✱bert at the apex should be saturated arcade orange (`#FF8700`), trumpet snout visible from camera-facing position, pupils visible in eyes, no legs poking out below the body. Capture screenshot to `tests/screenshots/qbert_player_redesign.png` per `feedback_screenshots_for_proof`.
4. **Catalogue render:** re-run `render_cards.py`, open `~/tmp/catalogue.html` from `task md -- docs/qbert/catalogue.md` — `actor_player` card now shows orange Q✱bert with trumpet nose and pupils.
5. **Regression spot-check:** confirm redball/greenball/coily-egg renders still look correct after the colour-space fix (red stays red, green stays green; only mid-channel-mix colours like the coily-egg purple shift, in the *right* direction).

## Out of scope

- No texture maps — colour-only materials (vert budget + .iff material model favours per-face flat colour). If post-redesign the eyes need a glint highlight, that's a follow-up.
- No animation rig — Q✱bert's hop stretch-and-squash is engine-side per `wf_Script` and doesn't touch the mesh shape.
- No change to player.iff schema or the wf_blender exporter — purely an asset rebuild.
- Other actor models (Sam, Slick, etc.) are not redesigned, though they'll benefit from the colour-space fix automatically.

## Follow-up

- **md-to-pdf.sh remote-image support.** Reference images had to be downloaded to `docs/qbert/refs/` because `/home/will/python-tui-lib/scripts/md-to-pdf.sh` only handles local image paths; `![alt](https://...)` falls through and renders as a plain link with the leading `!` stripped. Drafted a one-function patch (`_resolve_to_local` that fetches remote URLs into `${HOME}/tmp/img-cache/` keyed by SHA-256 of the URL); not applied because the file lives outside this repo and auto-mode flagged that as scope escalation. Worth doing as a separate, explicit ask.
