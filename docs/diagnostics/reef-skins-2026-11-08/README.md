# Creature skins: review, 8 November 2026

W2 of the [reef finishing plan](../../plans/2026-11-08-reef-tanks-finish.md). **Approved by Will, 2026‑11‑08, except the nudibranch** ("everything except nudibranch is approved"); the nudibranch was rebuilt below and awaits review. Will, 2026‑11‑08: "go ahead with W2". Colours follow the sourced [skin colour references](../../reference/thai-reef-skin-colours.md) (W0).

> [!NOTE]
> These are **Blender renders** (CPU Cycles, the static bake's sun) of the generator's own meshes with each style's real atlas. They are not engine captures, for the same reason as the [worm review](../reef-worms-2026-11-08/README.md): the desktop engine cannot run in the containers on this machine. **Before** is the code at `b8831c71` with its UV rule; **after** is this change. Every image is labelled.

## Mobile animals

Left to right: guard crab, banded shrimp, hermit crab, nudibranch, humbug.

| | Before | After |
|---|---|---|
| Realistic | ![](animals-realistic-before.jpg) | ![](animals-realistic-after.jpg) |
| Anime | ![](animals-anime-before.jpg) | ![](animals-anime-after.jpg) |

## Nudibranch, rebuilt (awaiting review)

Will asked whether the nudibranch had changed: barely. Its borrowed tiles (teal ridges, yellow boxfish tile) were already near the target colours, and the model was the real problem: a tall black blob with stalked tubercles in a single fence-like row. The rebuild follows the [colour references](../../reference/thai-reef-skin-colours.md): a low, flat black mantle; three raised blue-grey ridges along it; yellow-capped tubercles sitting directly on the ridges; yellow rhinophores at the front; and a mantle texture, mapped top-down, that repeats the ridges and adds short transverse ridges at the margins. 1,202 triangles (was 1,156). It still sits about 23 cm above the sand and bobs vertically; fixing that is W3.

| | Before | After |
|---|---|---|
| Realistic | ![](nudibranch-realistic-before.jpg) | ![](nudibranch-realistic-after.jpg) |
| Anime | ![](nudibranch-anime-before.jpg) | ![](nudibranch-anime-after.jpg) |

## Sessile life

Left to right: feather dusters, zoanthid carpet, sea fan, feather star.

| | Before | After |
|---|---|---|
| Realistic | ![](sessile-realistic-before.jpg) | ![](sessile-realistic-after.jpg) |
| Anime | ![](sessile-anime-before.jpg) | ![](sessile-anime-after.jpg) |

## What changed

| Actor | Before | After | Atlas |
|---|---|---|---|
| Guard crab | 97 % on the barrel-sponge pore tile, 86 % of its area in faces under 3 texels: flat orange | brown-orange polished carapace with sparse orange-red spots, banded legs, dark claw fingers | cell 10 |
| Banded shrimp ×2 | tan sand and orange sponge tiles | red and white bands, white antennae | cell 11 |
| Hermit crab | rock-grey shell and orange sponge | cream shell with brown spiral growth lines, pale lip, mottled maroon legs | cell 13 |
| Nudibranch | 62 % one flat black texel; teal clam-tile ridges; tall blob with a fence of stalked tubercles | rebuilt: see the section above | cell 12 |
| Feather dusters | flat white and sponge-pore bands; sand tube | buff and dark-brown banded radioles with barbs; muddy leathery tube | cell 9 |
| Zoanthid carpets | 66 % of area under 3 texels | each head and oral disc maps one flower-head motif; columns and tentacles get dense mottle | tile 5, tile 0 |
| Encrusting crusts | sponge and coralline tiles | finer pore and mottle crusts (they still stand off the rock: that is W3) | cell 14 |
| Humbugs | flat white | white with a faint belly-to-back sheen (realistic); flat white in anime | cell 15 |
| Sea fan | coralline tile | base-to-tip purple gradient (D3: no pattern) | cell 15 |
| Feather star | coralline arms, tan pinnules | gradient arms; the pinnules stay on the tan polyp tile, because a first render with gradient pinnules lost the two-tone feathery look | cell 15, tile 1 |

**How.** A new pure-Python module, `reef/uvmap.py`, now computes every face's UVs: the generator assigns them, and the texel audit and these renders measure them. Creature skin keys sample their own cell at a per-creature density (2.5–6 cycles per unit, mirrored so no face spans a wrap). Static surfaces keep their world projection.

**Audit.** `texcov.py --check` measures the exported UVs. Every creature W2 reskins is now at or under 20 % of its area flat or under 3 texels. The crab, shrimp, hermit crab, nudibranch, dusters and worms are at 0–3 %, and the zoanthid groups are under 20 %. The humbug's black bars, the sea fan and the feather star stay flat by design (D3).

## Tests

- `tests/test_thai_reef_skins.py` (new, 14 tests): each creature ≤ 20 % flat; its skin keys sample only its own cell and none of the borrowed tiles; zoanthid carpets ≤ 20 %; cells 9–14 painted in both styles; every reef key has a UV rule.
- 106 reef, placement, skins, movement, DFRM and exporter tests pass. Both levels and the menu bundle were rebuilt; the other eight tanks are untouched.

## Reproduce

```sh
task aquarium-thai-reef-level && task aquarium-thai-reef-anime-level
python3 docs/plans/2026-11-08-reef-tanks-finish/texcov.py --check
python3 -m pytest -q tests/test_thai_reef_skins.py
# before tree: git show b8831c71:wflevels/aquarium_thai_reef/reef/<file>.py into build-docker/reef-before/reef/
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
  --python docs/diagnostics/reef-skins-2026-11-08/render-skins.py -- build-docker/reef-skin-render after
```
