# Utah teapot reference data

`teapotCGA.bpt` is the 32-patch bicubic Bézier **Utah teapot** (Martin Newell, 1975;
Jim Blinn's 1976 proportions; Frank Crow's 1987 bottom), one patch per 16 control points,
vendored **verbatim**. `teapot.py` reads it; nothing else changes it.

| | |
|---|---|
| Source | [holmes3d.net/graphics/teapot/teapotCGA.bpt](http://www.holmes3d.net/graphics/teapot/teapotCGA.bpt) |
| Retrieved | 2026-10-31 |
| SHA-256 | `83c3cf09ff33cff17b8de714836c4c6758fccfc4288cef8671bacf0b7c294953` |
| Reference page | [University of Utah, the official Utah Teapot page](https://graphics.cs.utah.edu/teapot/) |
| Bounds | x −3.000…3.525, y −2.000…2.000, z 0.000…3.150 (base at z = 0, spout +X) |

Cross-checked 2026-10-31 against the patch table in three.js `TeapotGeometry` (MIT): the
control points of all 32 patches are identical and in the same order. The 1975 original had
28 patches and no bottom; the Utah page lists the version history. The Utah page states no
licence; the dataset has circulated unchanged since 1975.

Check it is still byte-identical to the source:

```
curl -s http://www.holmes3d.net/graphics/teapot/teapotCGA.bpt | cmp - wflevels/baseline/data/teapotCGA.bpt
```
