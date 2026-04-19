# Email: `_PathOnDisk.base.rot` mystery bytes in oracle `snowgoons.iff`

**Date:** 2026-04-19
**To:** Kevin T. Seghetti (cc: original WF team — this is about `wftools/iff2lvl/path.cc`)
**From:** Will, via Claude-assisted archaeology
**Subject:** Do you remember what `_PathOnDisk.base.rot` was supposed to contain? Oracle has mystery bytes.

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

### The stale header — suspicious

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

**Open.**  Awaiting reply from KTS.  In the meantime, `levcomp-rs`
emits the literal 8-byte sequence `b1 02 85 c6 00 00 20 4f` for
every `_PathOnDisk.base.rot`, matching snowgoons's oracle.  If/when
we build levels with non-zero authored base rotation (unclear from
the runtime code whether this is even possible), this will need to
be revisited.

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
