# Fix LMalloc alignment warning spam

**Status:** DONE (commit `2e0b229a`) — `FileLine` padded to 12 bytes on 64-bit, silencing the alignment-warning spam.
**Effort:** ~30 min

## Context

Running any level produces a flood of `LMalloc of 172 not 8-byte aligned, rounding up`
messages.  They appear throughout gameplay, not just at startup.  The user also asked
_why so many_ — the answer is that the diagnostic check is structurally misplaced and
fires as a false positive for every well-aligned struct in the system.

---

## Root cause

`LMalloc::Allocate` (`wfsource/source/memory/lmalloc.cc:215–226`) adds overhead
**before** checking alignment:

```cpp
size += sizeof(FileLine);  // +8 bytes  (int32 _state + int _size)
size += sizeof(int32);     // +4 bytes  canary sentinel
                           // total overhead = 12 bytes
if (size & WF_POINTER_ALIGN_MASK) {          // ← checks AFTER adding overhead
    DBSTREAM1(cwarn << "LMalloc of " << size << " not 8-byte aligned…");
}
size = ALIGN_POW2(size, WF_POINTER_ALIGN);   // already rounds correctly
```

`12 ≡ 4 (mod 8)` — not itself 8-byte aligned.  
Any base size that **is** a multiple of 8 (e.g. 160 bytes) produces a total of
`160 + 12 = 172` which is **not** a multiple of 8 → warning fires.  
The rounding on the very next line already fixes the alignment; the warning is pure
noise for every well-typed struct.

---

## Why so many?

On 64-bit the check fires for **every** HALLmalloc allocation whose base size is
divisible by 8 — which is essentially every properly-aligned struct.  Level construction
alone makes 50+ such allocations (template-object pointer array, per-object
`SObjectStartupData`, room arrays, startup singletons, etc.).  
Additional warnings appear during gameplay from a source that could not be pinpointed
by static analysis alone — see [Investigation](#investigation-finding-the-per-frame-source) below.

---

## Fix — Part 1: pad FileLine to make overhead 8-byte aligned

The cleanest structural fix is to add a 4-byte pad to `FileLine` on 64-bit platforms
so that `sizeof(FileLine) + sizeof(int32) = 12 + 4 = 16`, a multiple of 8.
On 32-bit platforms the check uses `WF_POINTER_ALIGN = 4` and `12 % 4 = 0`, so no
change is needed there.

**File:** `wfsource/source/memory/lmalloc.cc` — the `FileLine` struct (~line 50)

```cpp
struct FileLine
{
    enum { ALLOCATED = 'ALOC', FREED = 'FREE', CANARY_VALUE = (int32)0xDEADBEEF };
    int32 _state;
    int   _size;
#if LMALLOC_TRACK_LINE_AND_FILE
    char* _file;
    int   _line;
#endif
    // On 64-bit, sizeof(FileLine)+sizeof(int32 canary) = 12, which is not a
    // multiple of 8.  This pad makes it 16 (= 2 × 8), eliminating false-positive
    // alignment warnings for correctly-aligned user allocations.
    // SIZE_MAX > 0xFFFFFFFFU is true for any 64-bit size_t; no change on 32-bit.
#if SIZE_MAX > 0xFFFFFFFFUL
    int32 _pad;
#endif
};
```

After this change:
- 64-bit: `sizeof(FileLine) = 12`, overhead = 16, any 8-byte-aligned base → clean total → no warning ✓  
- 32-bit: `sizeof(FileLine) = 8` (unchanged), `WF_POINTER_ALIGN = 4`, 12 % 4 = 0 → no warning ✓

The canary placement logic (`retVal + size - sizeof(int32)`) is unaffected because
it uses `size` (the ALIGN_POW2-rounded total), not a hard-coded offset.

### What about LMALLOC_TRACK_LINE_AND_FILE?

Currently hardcoded to 0 (line 37).  If ever enabled, `FileLine` on 64-bit grows to
`4 + 4 + 8 + 4 = 20 bytes` → overhead = 24 → 24 % 8 = 0 ✓ (no extra pad needed).
The `_pad` member under `SIZE_MAX > 0xFFFFFFFFUL` would then be dead weight (4 bytes
wasted).  A follow-up `static_assert((sizeof(FileLine) + sizeof(int32)) % WF_POINTER_ALIGN == 0)`
can guard this.

---

## Investigation — finding the per-frame source

After the padding fix the startup flood will disappear.  If warnings continue they
represent **genuine** per-frame HALLmalloc allocations.  To expose the call site,
enable call-site tracking:

1. In `lmalloc.cc` change `#define LMALLOC_TRACK_LINE_AND_FILE 0` → `1`  
   (also set `MEMORY_TRACK_FILE_LINE` as the error message at line 41 requires)
2. Rebuild and run — the `cmem` stream will print `size,file,line,addr,pool` for
   every allocation; the allocations that are still flagged will now show their source.
3. Revert after identification.

---

## Verification

1. `task build` — must succeed, no new errors
2. Run with the SMB level: `task run-debug -- wflevels/smb_w1_1-standalone.iff`
3. The `LMalloc of 172 not 8-byte aligned` flood must be gone from startup output
4. If any warnings remain post-fix, use the `LMALLOC_TRACK_LINE_AND_FILE` approach
   above to identify the per-frame allocator
