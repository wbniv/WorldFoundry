# Investigation: Blender mesh export non-determinism → canonicalize vertex/face order

**Date:** 2026-06-02
**Status:** Root-caused + fixed (canonical order in the mesh writer)

## Symptom

Re-running a level's `blender --background --python blender_create_*.py` with **no code change**
re-exports some `.iff` meshes with different bytes — the multi-part meshes built via
`bpy.ops.object.join()` (goomba, koopa, mario/player, …), while simple single-primitive meshes
(cube, redball) stay identical. Long-standing noise ([TODO](../../TODO.md) "Blender mesh export is
not byte-stable", surfaced 2026-05-22). It forced manual `git checkout` of unrelated meshes on every
regen and made "re-export is behaviour-preserving" impossible to assert by bytes.

## Root cause (confirmed)

It is a **pure vertex/face re-ordering**, not value drift. Two fresh re-exports of `goomba_00.iff`
parsed at the `VRTX` chunk (24-byte `<iiIiii` = u, v, color, x, y, z entries):

```
A: VRTX n=183   B: VRTX n=183
position multiset EQUAL (pure reorder)?  True
full-entry  multiset EQUAL?              True
order identical?                         False
```

Identical 183-vertex set, **different order**. The mesh writer
([`export_level.py::_write_mesh_iff`](../../wftools/wf_blender/export_level.py)) emits vertices in
the order it first encounters them while iterating `bm.faces → face.loops`; that inherits the Blender
mesh's internal polygon order, which `bpy.ops.object.join()` concatenates **non-deterministically**
across the joined parts (player happened to be stable run-to-run; goomba was not). So the VRTX/FACE
chunks churn run-to-run with byte-identical geometry.

## Consequence correction

Because the churn is identical geometry, it does **not** change collision/physics — so it did **not**
cause the W1-2 re-export boot crash (coin-room actor fell through the floor → bungee camera
`ValidPtr(trackObject)` assert at `movecam.cc:1067`) seen during the smb_common P1b work. That crash
is a **separate, flaky** physics/camera issue (the committed build boots clean 3/3; a churned rebuild
crashed once — small-sample luck, not geometry). The camera-robustness gap (it should fall back to
`mainCharacter` instead of asserting on an out-of-room/null track object) is still worth fixing, but
it is independent of this export bug. (Earlier notes/commit that attributed the crash to the churn
were wrong.)

## Fix

Canonicalize vertex + face order in `_write_mesh_iff`, after building `split_verts`/`face_triples`
and before packing the `VRTX`/`FACE` payloads:

1. Re-key every split vertex by its **fixed-point `(x, y, z, u, v)`** (the same `*65536` quantization
   the payload uses), so geometrically-identical verts merge and the order is a deterministic sort.
2. Remap each face's vertex indices to the canonical indices; drop any triangle collapsed by the
   merge; **sort** the face list.

Geometry + UVs + materials are unchanged (same verts, same tris, same winding) — only the on-disk
order becomes canonical, so two re-exports are now byte-identical. This is a writer-side fix, so it
makes **every** mesh export deterministic regardless of why Blender's internal order varies (more
robust than trying to force `join()` to be deterministic).

**One-time churn:** the first re-export after this fix re-canonicalizes every committed mesh's byte
order; thereafter they're stable.

## Verification

- `goomba_00.iff`: two fresh re-exports → **0 differing bytes** (was 1164).
- All 74 W1-1 meshes: **0 differ run-to-run** (target).
- W1-1 regressions stay green (`verify_smb_scroll`, `verify_smb_scoring`); the level renders/plays
  identically (order-independent).
