# Blender normal convention migration evidence

16 October 2026. Dedicated worktree `blender-normal-convention`, based on
`0a1289295f177b59525fe1018b8cd58672036bbf`.

The [original inventory](model-inventory.json) walks IFF chunk boundaries in
819 tracked `.iff` paths. It records 528 distinct original `MODL` hashes and
4,849 model occurrences, including standalone models, nested bundles, Android
asset links and fixtures. The [decision manifest](model-decisions.json) records
an action and evidence for each original hash: 436 `reverse_all`, two
`reverse_selected`, 90 `keep`.
Geometry scores are clues, especially for open sheets, mirrored parts and
interior surfaces; source intent is noted for deliberate exceptions.

The [shell audit](original-components.json) checks disconnected components and
opposite-side pairs. Two models have mixed closed-shell signs: `ar_anal.iff`
and `goldfish.iff`. Their mirrored ventral membranes already have outward
Blender order; the manifest keeps those faces and reverses the remaining
legacy faces. The shared membrane generator now normalizes outline direction
so future exports reproduce outward dorsal and ventral shells. The audit also
confirms every zero-volume `keep` marked as paired has an opposite triangle
for every face; the separately reviewed embedded ramp is a single upward sheet.

[Direct geometry decisions](direct-geometry.md) cover built-in and test face
lists, matte and plant draws, both DFRM normal paths and direct IFF generators.
All six saved level scenes were re-exported into scratch space. The
[source comparison](blender-source-review.json) records 313 mesh outputs:
303 agree with migrated face geometry/direction, nine older baseline source
meshes have no current geometry match, and Qbert's saved cube is a placeholder
for the separately verified `gen_cube.py` output. No comparable source was
found pointing the opposite way. Original saved scenes were not overwritten.

The [conversion report](conversion-applied.json) records before/after hashes
for every regular IFF containing a model and each selected face count. It
changed 702 regular IFF files. The nine tracked symlinks whose targets changed
remain symlinks. The [post inventory](post-inventory.json) still finds 4,849
model occurrences. Distinct hashes fall from 528 to 525 where formerly
different windings now converge. No model parsing errors were found. Two
historical fixture roots, `wflevels/oad/test.iff` and
`wfsource/source/streams/strtest.iff`, are malformed IFF containers without
loadable `MODL` records and were left byte-identical.

`scripts/verify_face_hand.py` compares every tracked IFF path to its base
revision, applies only the reviewed FACE swaps in memory and checks the exact
resulting bytes. It verified 819 paths, 528 original model hashes, 460,447
selected triangles and 702 changed regular files. Positions, UVs, materials,
chunk sizes and non-FACE bytes are unchanged. The verifier also checks that
tracked symlinks still point to files. Run:

```sh
python3 scripts/verify_face_hand.py \
  --inventory docs/diagnostics/blender-normal-convention/integration-original-inventory.json \
  --decisions docs/diagnostics/blender-normal-convention/integration-model-decisions.json
```

The conversion is offline. Loading a model does not perform a legacy winding
correction. External old-hand IFF files need conversion before use.

## Validation

- Desktop engine build passed.
- Exporter, DFRM reference and converter guards: 17 passed.
- Engine DFRM parity/unit check: passed (`ctest -R '^dfrm_strand$'`).
- Desktop GL culling/prelit guards: 19 passed, two known dynamic-level skips
  (`snowgoons`, `snowgoons-blender`). The capture commands now use `--no-fps`
  because the changing FPS number invalidated otherwise identical frames.
- [Frame-100 GL captures](renders/results.json) cover Qbert, the arowana,
  translucent jellyfish, plants and condo; [cull comparisons](renders/comparisons.json)
  record their differences. Images were inspected for visible geometry. The
  dome has zero visible pixels with culling both off and on because its unchanged
  legacy Forth script produces compile error 7. Its frame-comparison pass is
  therefore not visual coverage. Repair/rebuild and recapture it before release.
- The [grown plant capture](renders/aquarium_plants-mature.png) shows runtime
  foliage with culling enabled after 60 simulated seconds. Its
  [run record](renders/mature-plant-result.json) uses a 5 Hz fixed simulation
  step; this is a visibility check, not a performance measurement. The earlier
  20 Hz capture request exceeded its 180-second timeout before frame 1,200.
- Qbert's cube and all seven direct-generated Marble Madness course meshes
  regenerate byte-identically.
- Offline Aquarium release APK builds for `arm64-v8a` and `armeabi-v7a`.
- [Bundle/APK verification](bundles-and-apk.json) repacks eight CD bundles and
  checks the APK's exact `assets/cd.iff` and both native libraries. The desktop
  CD's existing older baseline variant is preserved and recorded independently.
- The broad Android static test set has 44 passes, six skips and four existing
  stale expectations (asset file lists, pre-coordinator task routing and the
  desktop CD's eight-level order). No failure concerns migrated mesh bytes.
- Both Chromecast render checks are pending: Will confirmed their shared
  network is unavailable. Coordinator reconnect J‑a4be8ca239d8 failed with
  `device-not-found-on-network`; no direct-control fallback was used.
- Metal rendering is pending on an Apple host.
- **Correction, 2026‑10‑17.** The snowgoons arena, `quadpatch01` (`2ce88ee4…`), and its classic twin (`77b1e014…`) were wrongly kept, so GL and Metal both culled the floor. Both are now `reverse_all` in both manifests, and 13 IFFs were re-converted with `convert_face_hand.py --only-hash`. A render audit of every other `keep` found no other inverted model; `cyber` is unverified. See [metal-snowgoons-cull-2026-10-17](../metal-snowgoons-cull-2026-10-17/README.md).

## Integration with the newer seahorse work

The merge into `2026-new-level` includes the seahorse commits through
`66d03efd`. The original evidence above describes the feature branch before
integration. The [integration inventory](integration-original-inventory.json)
and [extended decisions](integration-model-decisions.json) cover that newer
base: 825 tracked IFF paths and 534 original model hashes.

The six added seahorse/post models were reviewed before conversion. Their
source uses Newell normals and explicit interior points to orient surfaces
outward; the fins intentionally have two-sided materials. A fresh Blender
export into scratch space confirms that all six old exports point opposite
to the new exporter. The [source comparison](integration-seahorse-source-review.json)
records their hashes and comparisons. Triangles agree after reversal; binary
exports differ because exporter sorting/index placement can also change.
The migration preserves the existing vertex, UV, material and DFRM bytes.

Both newer planted-tank bundles were retained and migrated, including their
embedded seahorses. The full verifier passes against `66d03efd`: 468,277
selected face swaps, 2,869 changed model occurrences and 708 changed regular
files. The [final inventory](integration-post-inventory.json) records all
remaining models. The [integration conversion report](integration-conversion-applied.json)
covers the eight files needing further changes after the initial merge.

The Aquarium Android menu bundle still contains its intentionally retained
older planted-tank variant, as documented in `7b0662c4` and the seahorse plan.
Its meshes are migrated and byte-verified independently. The earlier eight
bundle/APK rebuild checks describe the feature branch; the newer standalone
planted tank is not included in that APK. Rebuild the selector after the
other session's pending Aquarium bundle work is integrated. Chromecast tests
remain pending the unavailable shared network.

Integration checks: 85 focused migration, seahorse asset, tail deformation,
Forth behavior and settings tests passed. The existing engine DFRM parity
binary passed again; its engine sources are unchanged by the integration.
