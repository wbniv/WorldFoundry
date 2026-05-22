# Fix `_oadHeader` long → int32 (LP64 serialization-width bug, F2)

## Context

`_oadHeader` in `wfsource/source/oas/oad.h` has three `long` fields that map 1:1 to on-disk 32-bit IFF header fields. On PSX/x86-32, `long` == 32 bits. On LP64 (x86-64 Linux / modern Android), `long` == 64 bits, so the C++ OAD reader misreads `.oad` files — each field consumes 8 bytes instead of 4. This is F2 of the systematic `long` audit in [`docs/plans/2026-05-20-runtime-long-audit.md`](../../docs/plans/2026-05-20-runtime-long-audit.md).

F1 (fixing `pigtool.h`'s `SYS_INT32`/`SYS_UINT32` LP64 guard) is being handled in parallel; once both land, `int32` in `_oadHeader` is correctly 32-bit.

## Change

**File:** `wfsource/source/oas/oad.h` lines 108–114

```c
// Before
typedef struct _oadHeader
{
    long chunkId;
    long chunkSize;
    char name[72-4];
    long version;
} oadHeader;

// After
typedef struct _oadHeader
{
    int32 chunkId;
    int32 chunkSize;
    char name[72-4];
    int32 version;
} oadHeader;
```

`int32` is already used throughout `oad.h` for 32-bit fields (e.g., `typeDescriptor` lines 137–139). `chunkId`, `chunkSize`, and `version` are all 32-bit IFF header fields.

Note: the `FIXED32(n)` macro at line 10 also casts via `(long)` but is a compile-time literal and harmless — leave it alone (noted as out-of-scope in audit plan).

## Verification

- `task build` (ASan default) green.
- `sizeof(oadHeader)` should be 80 bytes on LP64 after F1+F2 (3×4 + 68 = 80). Check with a static assert or manual `printf`.
- OAD reader (`oaddump` or editor property-panel path) reads a `.oad` file without misalignment.
