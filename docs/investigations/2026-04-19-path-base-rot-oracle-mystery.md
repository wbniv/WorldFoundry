# `_PathOnDisk.base.rot` mystery bytes in oracle `snowgoons.iff`

**Date:** 2026-04-19
**Status:** **RESOLVED** — all 8 bytes are uninitialized memory (see Resolution below).
**Audience:** archaeology notes for `wftools/iff2lvl/path.cc`; was drafted as a question to KTS before we found the answer.

---

## Resolution (2026-04-19)

**The `Euler` used in `path.cc` is the plain POD struct defined inline in `wftools/iff2lvl/global.hp:68-73`:**

```cpp
// This is a replacement (in progress) for br_euler.  The ordering is always XYZ_S
typedef struct
{
    float a;
    float b;
    float c;
} Euler;
```

Public `.a/.b/.c`, no constructor. `path.cc` pulls this in via `#include "global.hp"` at line 24 — it never includes `euler.hp`, so the `#error !!` tombstone is irrelevant to this TU. No `WF_TOOL` / `MAX_BUILDMODE` preprocessor gating is involved. `euler.hp`/`euler.cc` are orphaned dead code from the earlier class-based Euler (private `_a/_b/_c` with `GetA()/SetA()` accessors); the `#error !!` was a deliberate tripwire to prevent accidental reuse after the replacement POD landed in `global.hp`.

**Consequence:** `Euler rotEuler;` is default-initialization of a POD struct — all three `float` members are *indeterminate*. Then:

```cpp
diskPath->base.rot.a = WF_FLOAT_TO_SCALAR(rotEuler.a);   // WF_FLOAT_TO_SCALAR(garbage float)
```

feeds a garbage float through `(fixed32)(x * 65536.0f)` and narrows the result to `u16`. So the three u16 axes are *also* uninitialized, not just the `.order`/`.pad` u8s that fall out of `new char[]` default-init. **All 8 bytes of `base.rot` are indeterminate memory.** The determinism across re-runs is a stack/heap layout artifact of the short-running plugin (same allocator state, same call pattern → same uninitialized contents), not evidence of any real value being stored.

The third u16 (`.c = 0x0000`) matching expectations is coincidence — whatever float sat there happened to be 0.0 or small enough to narrow to zero fixed32.

### What were these bytes *supposed* to contain, and whose path is it?

**Whose path:** snowgoons has exactly one `_PathOnDisk` record, and it belongs to **`snowman01`** — the snowgoon enemy that walks back and forth across the yard. The intermediate `.lev` text confirms it: `wflevels/snowgoons/snowgoons.lev` under `{ 'NAME' "snowman01" } { 'PATH' ... }` with three `position.{x,y,z}` channels and three `rotation.{a,b,c}` channels.

**What `base.rot` is for:** it's the **base rotation of the path's coordinate frame** — specifically the rotation of the *parent object* a relative/hierarchical path is anchored to. The runtime in `wfsource/source/anim/path.cc:157` adds it to every sampled rotation:

```cpp
rotation += _baseRot;   // Add offset for relative path or zero for absolute path
```

For an **absolute** path, `base.rot` is supposed to be zero (identity) — the per-channel rotation channels carry the full orientation.
For a **relative/hierarchical** path (one with an `ObjectToFollow`), `base.rot` would carry the parent's orientation so the per-channel angles can be expressed in the parent's local frame.

**snowman01 is absolute.** Its `.lev` entry has `Object To Follow ""` (empty). The `'BROT'` chunk in the `.lev` text is correctly authored as identity — `0, 0, 0, 1` (quat) — exactly as the design intends. So the on-disk `base.rot` *should* be `00 00 00 00 00 00 00 00`.

**Why isn't it?** Two failures compound:

1. **`QPath::baseRotation` (the class member) is never consulted by `QPath::Save`.** The class stores `Quat baseRotation;` correctly — set to identity by the default constructor, or to the caller's quat by the relative-path constructor. But `Save` declares a shadowing local `Euler rotEuler;` and writes *that* (uninitialized) instead of converting `baseRotation` → Euler.

2. **The Quat→Euler conversion was never implemented.** `QPath::AddRotationKey` (`wftools/iff2lvl/path.cc:151-158`) is a stub:
   ```cpp
   #pragma message ("KTS " __FILE__ ": finish this")
   //QuatToEuler(newRotation - baseRotation, angles);
   assert(0);
   ```
   Same conversion was needed in `Save`, never got written, and the save path papered over it by declaring a fresh local and writing garbage.

**Why it escaped notice:** even for the relative-path case where `base.rot` semantically matters, the runtime **overwrites it on every frame** from the parent object's live rotation (`wfsource/source/movement/movepath.cc:109`: `path->SetBaseRot( target->GetPhysicalAttributes().Rotation() )`). The saved bytes are clobbered before first use. For the absolute-path case (snowman01), the bytes are read into `_baseRot` and then added to every frame's rotation — but the per-channel rotation channels authored into snowgoons happen to produce angles that look correct with or without the garbage offset (short path, low-res visuals, no other reference to compare against). So the bug has been shipping undetected since 1995–2010.

### What this means for `levcomp-rs`

The `TODO` that currently emits the literal 8-byte sequence `b1 02 85 c6 00 00 20 4f` is a mirror of heap garbage. The verification plan below (flip to zeros once the end-to-end round-trip works and confirm nothing changes) is the right path to drop the literal constant. Given the runtime reads these bytes into `_baseRot` and the per-channel rotation channels then overwrite the actor rotation every frame, the flip to zeros is very likely safe.

### Why the conventions exist: this bug is exactly what they were designed to prevent

The `Euler` in `global.hp:68-73` violates at least three WF coding conventions, and those violations are what make the bug possible. It's a nice teaching moment:

**1. "No public data" (`wfsource/source/codingstandards.txt:103`)**
> *"inline accessors are free, so there is no reason to ever have public data."*

`Euler` exposes `a/b/c` directly. That's the only reason `rotEuler.a` compiled at all — a proper class with `GetA()/SetA()` (like `wfsource/source/math/euler.hp`) wouldn't have matched the pattern in `path.cc`.

**2. Canonical form / four special members (`docs/coding-conventions.md §4.1`, older IS C++ §5)**

`Euler` declares *none* of the four — no default constructor, no copy, no assignment, no destructor. Modern §4.1 scopes the rule to resource-owning classes, so it doesn't strictly apply here; but the older IS C++ canonical-form rule (which `codingstandards.txt` recommends generally) covers all classes. The author flagged it themselves in the comment: *"This is a replacement (in progress) for br_euler."* It was meant to become a real class and never did. An explicit default constructor would almost certainly have zero-initialized `a/b/c`, the same way `wfsource/source/math/euler.hp`'s constructors do.

**3. `Validate()` discipline (`codingstandards.txt:74-82`, `docs/coding-conventions.md §5`)**
> *"Every class should have an inline function named `Validate()`. … Constructors should call Validate upon exit."*

`Euler` has no `Validate()`. If it had one that asserted `a/b/c` are finite and within `[0, 1)` revolutions (per the "angles are in revolutions" project rule), and the default constructor called it on exit — the debug build of `iff2lvl` would have asserted the first time `QPath::Save` ran instead of silently emitting garbage.

So the bug isn't "the compiler did something weird." It's *"a type that should have been a class was left as a POD shim, which bypassed three separate WF conventions each independently designed to prevent this class of bug."* The garbage bytes in the oracle are exactly what `codingstandards.txt` was written to make impossible.

**Caveat on scope:** the WF coding standards were strictly enforced for the **game-engine runtime** (`wfsource/source/…`) and *much* more loosely for the **tools** (`wftools/iff2lvl`, the Max plugin, etc.). That's why the shortcuts that produced this bug — public-data POD struct, no `Validate()`, no canonical form, plus the stubbed-out Quat→Euler conversion in `AddRotationKey` — slipped through on the tools side. In hindsight it's clear that at least the value-type conventions (explicit default constructor, `Validate()`, no public data) *should* have applied to the tools as well: tools are the first producer of every byte the runtime reads, and a tool bug that writes garbage to an on-disk struct is indistinguishable from a runtime bug that reads one. The enforcement asymmetry is a historical artifact — not a deliberate design choice to be preserved — and the Rust rewrites (`iffcomp-rs`, `levcomp-rs`, `oas2oad-rs`) are a good opportunity to close that gap.

### Not the only uninit-heap site: the `_RoomOnDisk` pad bytes are the same pattern

Update, 2026-04-19 later that day: while chasing the last 3 byte-diffs in snowgoons's `.lvl` (see `docs/plans/2026-04-19-levcomp-common-block-two-phase.md`), we found the SAME C-allocator-heap-garbage pattern in a different struct — `_RoomOnDisk` pads. iff2lvl allocates rooms via `new char[size]`, writes 34 bytes of fields into a `__attribute__((aligned(4)))` 36-byte footprint, and doesn't zero the 2-byte struct-header pad. It also doesn't zero the trailing-entries pad that brings `36 + 2×count` up to the next 4-byte boundary. Both regions end up carrying whatever bytes happened to be in the allocator bucket the OS handed out.

Concrete snowgoons witnesses (see `rooms.rs:61-65`):

- Room 0: struct-header pad = `00 00` (same as our zero-init), **trailing pad = `01 00`** (ours emits `00 00`).
- Room 1: **struct-header pad = `0B 08`** (ours emits `00 00`), trailing pad n/a (entries array lands on a 4-byte boundary).

Three bytes total, same class as `_PathOnDisk.base.rot`'s 8-byte Euler garbage. Both:

- **Uninitialized heap from `new char[size]`** (C allocator semantics — no zero-fill).
- **Deterministic within one run** (same process, same allocator state) but **not reproducible across platforms or implementations** (Rust `Vec::extend_from_slice` zero-fills; C's `new char[]` doesn't).
- **Not content** — the runtime doesn't read these bytes meaningfully. They're artifacts of the authoring tool's allocation pattern, preserved on disk because the authoring tool never overwrote them before committing bytes to the `.lvl` file.

The lesson: **any `new char[]` without explicit zero-init in iff2lvl is a potential byte-identity cliff.** `_PathOnDisk` and `_RoomOnDisk` are the two we've hit; `_ObjectOnDisk`'s type-field pad (2 bytes after the i16 type, before position) is a third, already mirrored consistently by levcomp-rs (`lvl_writer.rs:477` emits the same `0x0B 0x08` that iff2lvl produced — lucky in that case because iff2lvl always pulls the same allocator bin for object zero, so the bytes are consistent). Other on-disk structs are worth auditing if future byte-identity work turns up unexpected diffs.

**Mirror policy for these pad bytes**: zero-fill on the Rust side and accept the constant-width drift. Replaying the iff2lvl heap state exactly is infeasible, and the bytes are meaningless to the runtime — so the cheapest path is "don't chase." Document and move on. (The `mirror-oracle-first` rule has an explicit carve-out for indeterminate heap bytes: there's nothing to mirror.)

---

## Original investigation (as drafted before the resolution)

The rest of this doc is the email-framed investigation I had queued up for KTS before tracing `global.hp` turned up the POD struct. Kept for archaeology.

---

## Summary

I'm rebuilding the WF level-authoring pipeline (Blender → `levcomp-rs`
→ `.lvl` → `.iff`) and cross-checking every byte against the oracle
`snowgoons.iff` (the one compiled however-many-years-ago with the Max
plugin + `iff2lvl`).  Everywhere else I've been able to match the
oracle's bytes exactly.  One spot I can't explain: the 8-byte
`base.rot` field of the single `_PathOnDisk` record in snowgoons's
compiled LVL chunk.

The field is declared as `wf_euler` (u16×3 + u8 order + u8 pad = 8
bytes) and by the code in `QPath::Save` it should clearly end up all
zeros — but it doesn't.  Oracle contents:

```
base.rot bytes: b1 02 85 c6 00 00 20 4f
  → .a (u16 LE) = 0x02b1 = 689
  → .b (u16 LE) = 0xc685 = 50821
  → .c (u16 LE) = 0x0000
  → .order (u8) = 0x20
  → .pad   (u8) = 0x4f
```

5 of 8 bytes nonzero.  The nonzero-ness is deterministic between
runs of the oracle pipeline (I've re-dumped and they're identical).
So it's not pure heap garbage, but it's also not what the source
code appears to say.

---

## The code

### `wftools/iff2lvl/path.cc:268-295`

```cpp
void
QPath::Save(ostream& lvl)
{
    DBSTREAM3( cdebug << "QPath::Save" << endl; )

    _PathOnDisk* diskPath = (_PathOnDisk*)new char[SizeOfOnDisk()];
    assert(diskPath);

    diskPath->base.x = WF_FLOAT_TO_SCALAR(basePosition.x);
    diskPath->base.y = WF_FLOAT_TO_SCALAR(basePosition.y);
    diskPath->base.z = WF_FLOAT_TO_SCALAR(basePosition.z);
    Euler rotEuler;

    diskPath->base.rot.a = WF_FLOAT_TO_SCALAR(rotEuler.a);
    diskPath->base.rot.b = WF_FLOAT_TO_SCALAR(rotEuler.b);
    diskPath->base.rot.c = WF_FLOAT_TO_SCALAR(rotEuler.c);

    diskPath->PositionXChannel = positionXChannel;
    diskPath->PositionYChannel = positionYChannel;
    diskPath->PositionZChannel = positionZChannel;
    diskPath->RotationAChannel = rotationAChannel;
    diskPath->RotationBChannel = rotationBChannel;
    diskPath->RotationCChannel = rotationCChannel;

    lvl.write( (const char*)diskPath, SizeOfOnDisk() );
}
```

### On-disk struct (`wfsource/source/oas/levelcon.h`)

```c
struct _PathOnDisk
{
    struct pathBase { fixed32 x,y,z; wf_euler rot; } base;
    int32 PositionXChannel;
    int32 PositionYChannel;
    int32 PositionZChannel;
    int32 RotationAChannel;
    int32 RotationBChannel;
    int32 RotationCChannel;
} GNUALIGN;
```

and `wf_euler` is 8 bytes: three u16 axes (`a`, `b`, `c`) followed
by `order` and `pad` u8s.

### The stale header — suspicious [RESOLVED: red herring, see top]

`wftools/iff2lvl/euler.hp` starts with:

```cpp
#ifndef _EULER_HPP
#define _EULER_HPP

#error !!

class Euler { ... };
```

That `#error !!` at line 7 is unconditional.  Any TU that includes
this header would fail to compile.  So the `Euler` class being used
in `path.cc` is NOT this one — it has to be coming from a different
header in the include path.  Whichever `Euler` it is, it must have
public `.a`, `.b`, `.c` members (not getters) for
`rotEuler.a` to be a legal expression.

The only other `Euler`s I can find in the tree are:

- `wfsource/source/math/euler.hp` — private `_a`, `_b`, `_c`; public
  accessors `GetA()/SetA()`.  Doesn't fit the `rotEuler.a` syntax.
- Max SDK `Euler` — not in this tree, but the plugin built against
  it in `wfmaxplugins/max2lev/`.  In recent Max SDKs `Euler` is
  `Point3` with `.x/.y/.z`, not `.a/.b/.c`.

So either (a) `path.cc` used to compile against a different `Euler`
header that has since been deleted (the stale `wftools/iff2lvl/euler.hp`
minus the `#error`?), or (b) there's a preprocessor rabbit hole in
`global.hp` I haven't traced.

---

## Investigation to date

### 1. `new char[SizeOfOnDisk()]` is uninitialized

In C++, `new T[n]` value-initializes for class types with
non-trivial constructors but default-initializes for scalar types.
`char[]` is default-initialization, which for scalars is
"indeterminate value" — i.e. whatever was on the heap.

Every byte the `QPath::Save` code doesn't explicitly assign stays
as that indeterminate value.  So `.order` and `.pad` (never
assigned) are heap garbage, as expected.

### 2. But the u16 axes are *also* not zero

The code assigns `diskPath->base.rot.a = WF_FLOAT_TO_SCALAR(rotEuler.a)`.
If `rotEuler` is a freshly-constructed `Euler` with identity
rotation, `rotEuler.a` should be 0.  `WF_FLOAT_TO_SCALAR(0.0)` is 0.
Narrowing `int32 0` into `uint16` is 0.  So `.a`, `.b`, `.c` should
all be zero after the assignment.

Oracle has `.a = 689`, `.b = 50821`, `.c = 0`.  The last one matches
the expectation.  The other two don't.

Possibilities:

- **Maybe `WF_FLOAT_TO_SCALAR` isn't zero for 0.0 in the Max-side
  build.**  If it's something like `(int32)(x * 65536.0)` then
  compiler-specific float-to-int rounding at optimisation time could
  produce odd bits — but 0.0 → 0 is boringly deterministic on any
  IEEE-754 platform, so this is unlikely.
- **Maybe the `Euler` class whose declaration I can't find has
  non-zero default-constructed members.**  E.g. it initializes
  `_axes[3]` but `rotEuler.a` accesses something else that's
  uninitialized.  This would explain deterministic-looking garbage
  across runs (always the same heap state for a short-running
  plugin).
- **Maybe `base.rot` was being set to some other value in an
  earlier version and the assignments I'm reading were ported from
  there.**  Git history only goes back to the May 2010 "first
  commit" import, so anything before that is gone.

### 3. The values are deterministic across re-runs

I've dumped the oracle twice (once straight, once after an
unrelated byte patch to a different chunk).  The `base.rot` bytes
are identical both times.  So whatever produces them, it's not
purely "whatever was on the heap this second."

---

## Why I'm asking

I want to reproduce these bytes exactly in `levcomp-rs` so that
my compiled `.lvl` matches the oracle byte-for-byte — mirror-first,
deviate-later is the explicit policy for the round-trip work.  I
can of course just literal-copy the 8 bytes from the oracle and
emit them as a magic constant (that's what I'm going to do for now,
marked with a TODO referencing this doc).  But if you remember what
those bytes *meant*, that would be better — ideally I'd emit them
from the same recipe, not from a frozen snapshot.

Questions:

1. Do you remember what `Euler rotEuler;` was supposed to produce
   in iff2lvl's path.cc?  A specific `Euler` class, or just the
   Max SDK's?
2. Was `wftools/iff2lvl/euler.hp` the one being used, or was there a
   different `Euler` header that's no longer in the tree?  The
   `#error !!` makes me think it got deprecated at some point but
   wasn't fully removed.
3. Are the `base.x/y/z` / `base.rot` fields used by the runtime for
   anything meaningful?  `wfsource/source/anim/path.cc:55-61` reads
   them:
   ```cpp
   _base.SetX( Scalar( Scalar::FromFixed32(pathData->base.x) ) );
   // ... same for y, z
   _baseRot.SetA(Angle::Revolution(Scalar(0,pathData->base.rot.a)));
   _baseRot.SetB(Angle::Revolution(Scalar(0,pathData->base.rot.b)));
   _baseRot.SetC(Angle::Revolution(Scalar(0,pathData->base.rot.c)));
   ```
   — but the per-channel rotation channels overwrite the actor
   rotation every frame, so whatever `_baseRot` ends up as appears
   to be ignored in practice.  Was that always true, or was
   `_baseRot` meaningful in an earlier revision that got refactored
   away?

No urgency — the literal-bytes fix gets me unblocked today.  But
since "why does iff2lvl put mystery bytes in `base.rot`?" is the
kind of question only you could answer with certainty, figured it
was worth asking.

Thanks!
— Will

---

## Status

**Resolved 2026-04-19.** The `Euler` is the POD struct in `global.hp:68-73`;
`Euler rotEuler;` leaves `a/b/c` indeterminate; `WF_FLOAT_TO_SCALAR` then
narrows garbage floats into the three u16 axes. Combined with the
`new char[]` default-init of `.order`/`.pad`, all 8 bytes of `base.rot`
are uninitialized memory. Mirror-first stands: `levcomp-rs` emits the
literal 8-byte sequence `b1 02 85 c6 00 00 20 4f` for now; verification
plan below is how we drop the literal.

## Verification plan once the round-trip is fully working

Once `snowgoons-blender.iff` runs end-to-end without `swap_lvl.py`
and we're confident every other byte is correct, **flip these 8
bytes to `00 00 00 00 00 00 00 00`** and re-run.  If gameplay is
indistinguishable (snowman keeps walking its path, collisions
behave the same, nothing asserts over a 60-second soak), we've
empirically confirmed the bytes are dead heap garbage and the
mirror is purely cosmetic.  At that point we can drop the literal
constant and emit zeros from `levcomp-rs` — which is what the code
would do anyway if it matched the spec it clearly *wanted* to
match.

The only risk: some subtle Euler-angle-comparison edge case uses
the raw bits before the per-channel rotation channels overwrite
them.  Worth a single diff against the zero-bytes run to confirm
nothing changed in the first frame's output.
