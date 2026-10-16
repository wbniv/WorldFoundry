# Direct geometry review

Normals below use `(v1−v0) × (v2−v0)`.

| Source/group | Intended side and check | Migration |
|---|---|---|
| `renderassets/rendacto.cc`, built-in cube | Each triangle normal dotted with its centroid relative to the box centre is positive after conversion. | Reverse all 12 old-order triangles. |
| `renderassets/rendcrow.cc`, scarecrow | The sheet sits at minimum Y; its front is −Y, toward the viewer. The two original Blender crosses were +Y. | Reverse both triangles to −Y. |
| `gfx/rendmatt.cc`, tiled matte | The two drawn triangles agree with the explicit +Z normal. Background material remains cull-exempt. | Keep the existing draw order; update its explanation. |
| `renderassets/rendacto.cc`, `SetPlantGeometry` | Explicit normal uses `(b−a) × (c−a)` and the same `a,b,c` face indices. | Keep faces and explicit normals together. |
| `renderassets/dfrm_deform.cc`, bound sample normals | The bound triangle cross must agree with the loaded rest normal. | Use Blender order. |
| `renderassets/dfrm_deform.cc`, recomputed normals | Cross of deformed positions must agree with the same triangle order. | Use Blender order. Engine/Python parity and coil/culling tests pass. |
| Test cubes in `gfx/gfxtest.cc`, `particle/test.cc`, `anim/animtest.cc`, `physics/physicstest.cc` | Same closed outward cube convention as the runtime built-in cube. | Reverse each 12-face 3D list. |
| Test-only 2D quads and list terminators | These constructors do not derive 3D normals. | Keep. |
| `qbert_practice/gen_cube.py` | Cube top +Z; all exterior faces outward. | Reverse the old-hand list. Regenerates migrated `cube.iff` byte-identically. |
| `marble-madness-2/gen_level1.py` | Floors +Z; zero-thickness walls have both sides. | Correct floor/base wall order. All seven migrated outputs regenerate byte-identically. |
| `mm_practice/gen_ramp.py` | First pair already has upward Blender normals; second pair is its deliberate opposite. | Keep all four triangles. |
| `aquarium_tanks/models.py`, mirrored fin membranes | A CCW outline in XZ produces front −Y, back +Y and an outward perimeter. Mirroring Z had inverted whole shells. | Normalize outline direction before building. Arowana shares this helper; both mirror directions pass a volume check. |
| `aquarium_tanks/dfrm_ref.py` | Reference normals and generated test strands must agree with the engine's new rule. | Use Blender order; parity passes. |

The shared loader and normal function feed both GL and Metal. This review does
not enable hardware culling or claim a Metal render was performed on Linux.
