# Investigation: `Array<T>::operator[]` off-by-one in `_num` tracking

**Date:** 2026-05-20  
**Status:** Fixed — `>` → `>=` in [`wfsource/source/cpplib/array.hpi`](../../wfsource/source/cpplib/array.hpi):195  
**Surfaced by:** SMB `?`-block Generator crash on first script tick

---

## Symptom

Running `wf_game -L wflevels/smb_w1_1-standalone.iff` crashed immediately after the level finished loading, with:

```
terminate called without an active exception
Aborted (core dumped)
```

GDB stack trace:

```
#9  std::thread::~thread (this=<gListenerThread>)   ← joinable thread in dtor
#10 __run_exit_handlers
#11 __GI_exit
#12 _sys_assert (expr="0", file="mailbox.cc", line=90)
#13 MailboxesWithStorage::ReadMailbox (mailbox=2012) at mailbox.cc:90
...
#20 zf_host_sys (ZF_SYSCALL_USER)
#23 forth_engine::RunScript (src="INDEXOF_SMB_QBLOCK_USED read-mailbox …", objectIndex=13)
#26 Actor::update (this=<Generator ?-block>)
```

The assert on `mailbox.cc:90` calls `exit()`, which runs atexit handlers including the destructor of the static `gListenerThread` (`std::thread`). Destroying a joinable thread calls `std::terminate()` — producing the misleading "terminate called without an active exception" message.

---

## Root cause

`Array<T>::operator[]` (non-const, `array.hpi`:189) tracks the highest-written index in `_num` to gate `const operator[]` reads:

```cpp
// array.hpi — original since a2784f6 (2010 git import, code predates that)
template<class T> INLINE T&
Array<T>::operator[](int32 index)
{
    assert(index < _max);
    assert(index >= 0);
    assert(ValidPtr(_items));
    if(index > _num)        // ← BUG: should be >=
        _num = index+1;
    return(_items[index]);
}
```

The condition `index > _num` should be `index >= _num`. When writing to element `[N]` after `_num` has been set to exactly `N` (by the previous odd-indexed write), the condition `N > N` is FALSE and `_num` stays at `N` instead of advancing to `N+1`.

**Pattern for sequential initialization `[0..N-1]`:**

| N (slots) | `_num` after full init | `Size()` | last slot reachable |
|---|---|---|---|
| even | N (correct) | N | ✓ |
| odd | N−1 (off by one) | N−1 | last slot **missed** |

The off-by-one only fires for odd-sized arrays, and only the last element is affected.

---

## Why it was dormant

`MailboxesWithStorage::ReadMailbox` uses `Size()` for its range check since the 2010 import:

```cpp
if(mailbox >= _mailboxBase && mailbox < _localMailboxes.Size() + _mailboxBase)
    return _localMailboxes[mailbox - _mailboxBase];
```

Every actor in every pre-SMB level (snowgoons, Q✱bert) had `NumberOfLocalMailboxes = 0`. With an empty array, `Size()` returns 0 and the range is empty — every mailbox delegates up to the level/game chain, which works correctly. **Local mailbox storage was allocated but never meaningfully accessed**, so the incorrect `Size()` was never tested.

The 2026-05-18 Phase 0b commit (`254c1d4`, "fix UnloadLevel LIFO chain — six dormant bugs") audited and fixed `Array::SetMax`'s allocator misuse, but did not revisit `operator[]`.

---

## How it was surfaced

SMB `?`-block actors (class `Generator`) require local mailbox state for the multi-coin window:

```
MAILBOXENTRY( SMB_QBLOCK_ACTIVATE, 2010 )   — index 10 in the 13-slot array
MAILBOXENTRY( SMB_QBLOCK_USED,     2011 )   — index 11
MAILBOXENTRY( SMB_QBLOCK_DIE,      2012 )   — index 12  ← the off-by-one victim
```

`NumberOfLocalMailboxes = 13` (odd). The init loop writes `[0..12]`; `_num` ends at **12** instead of 13. `Size()` = 12, so the range is `[2000, 2012)`. Mailbox 2012 (`SMB_QBLOCK_DIE`) is just outside — `2012 < 2012` is false — and the read delegates all the way to `GameMailboxes`, which has no parent, hitting `assert(0)`.

The player (`NumberOfLocalMailboxes = 6`, even) was unaffected.

---

## Fix

One character in `array.hpi`:195:

```cpp
-   if(index > _num)
+   if(index >= _num)
        _num = index+1;
```

This makes `_num` correctly track the first-unwritten high-water mark for all sequential and in-order initializations. Writing to an already-tracked index (index < _num) still leaves `_num` unchanged.

---

## Archaeology

CVS source (SourceForge `wf-gdk` snapshot, `wfsource/source/cpplib/Attic/array.hpi,v`):

| Rev | Date | Log message |
|---|---|---|
| 1.1 | 2000-02-12 | Initial revision — no `operator[]` non-const yet |
| 1.2 | 2003-03-17 | Updated copyright, cleanup |
| **1.3** | **2003-05-23** | **"added an operator[] which is non-const and allows writting to objects in the Array, added begin & end functions which return iterators"** |
| 1.4–1.6 | 2003-05–06 | Allocator, iterator, ostream additions |
| 1.7 | 2010-04-30 | GCC 4.3 compat |
| 1.8 | 2010-05-21 | dead — moved to git |

The `if(index > _num)` bug was **born with the feature** — Rev 1.3, **2003-05-23**, is the commit that introduced the non-const `operator[]`. The git import (`a2784f6`, 2010-05-01) carried rev 1.7 of the file, which already had the bug. The bug was 23 years old at the time of the fix.

---

## BUGS.md

See entry: `Array<T>::operator[]` `_num` high-water off-by-one — odd-sized arrays under-report `Size()` — 2026-05-20.
