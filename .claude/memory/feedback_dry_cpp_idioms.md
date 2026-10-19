---
name: feedback_dry_cpp_idioms
description: "WF C++ — derive array bounds from the array (ARRAY_COUNT), pre-increment standalone ++/--, no magic-number constants"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04d549ec-9325-4a13-9b01-4ff5ec87f19c
---

Will wants WF C++ kept DRY and magic-number-free; these are codified in `docs/coding-conventions.md` §4:

- **Array bounds derive from the array, never a hardcoded literal.** Use `ARRAY_COUNT(arr)` (`wfsource/source/pigsys/pigsys.hp`, expands to `sizeof(arr)/sizeof((arr)[0])`) for any fixed-array bound — asserts, loop limits, capacity checks. The size then lives only at the declaration. (Origin: the pending-removal queue had `_toBeRemovedObjects[100]` with a separate `assert(< 99)` — a duplicated literal AND an off-by-one.)
- **Pre-increment for standalone steps.** A bare `i++;` statement or a `for`-loop step uses the *pre* form `++i` (post-increment specifies an unused old-value copy). Reserve `i++` for expressions that need the old value.
- **General:** "we generally almost always avoid hardcoded constants." When you see a magic number that mirrors something else (an array size, a mailbox index, an enum bound), reference the source instead.

**Why:** a literal next to its array drifts on a resize (off-by-one or overflow); post-increment carries a needless side effect; magic numbers hide the real relationship.

**How to apply:** proactively, when writing OR touching WF runtime C++ — don't wait to be told. If a new convention like this comes up, add it to `docs/coding-conventions.md` and log a codebase sweep in TODO.md (NAMING section) rather than only fixing the one site. See [[feedback_commit_freely]].
