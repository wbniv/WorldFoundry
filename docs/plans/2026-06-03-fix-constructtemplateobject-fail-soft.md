# Fix ConstructTemplateObject fail-soft

## Context

`SafelyConstructTemplateObject` (`wfsource/source/game/level.cc`) terminates the process
on two prerequisites rather than returning NULL:

1. **Outside-rooms path** (line 1692): `AssertMsg(containingRoom, "trying to spawn an object
   outside of all rooms")` — the `return (Actor*)NULL` on line 1694 is dead code; the assert
   fires first.
2. **NULL-return path** (line 1700): `assert(ValidPtr(retVal))` — fires whenever
   `ConstructTemplateObject` (objects.c) returns NULL, which it does legally for
   `Room_KIND`, `Disabled_KIND`, `Alias_KIND`, and `Shield_KIND`.

`ConstructTemplateObject` in `objects.c` also has `default: assert(0)` (line 317), which
terminates on any unrecognised type enum.

Because of these asserts, `wfmut::SpawnActor` (`engine/mutation/wfmut.cpp:362-369`) added
a preemptive kind-guard that blocks Room/Tool/StatPlat before reaching the engine. And
`RunSpawnConfirmTest` Part A (`engine/wf_edit/engine_bridge.cc:641-665`) was explicitly
parked—it finds a template entry but never calls SpawnActor because the engine would crash.

The fix removes the three terminating assert/AssertMsg calls so the engine fails cleanly
(NULL return) for any unsupported kind or bad position, updates the wfmut kind-guard
comment to reflect that it is now documentation rather than a crash-shield, and un-defers
`RunSpawnConfirmTest` Part A to actually exercise SpawnActor.

---

## Assert inventory

Every assert/AssertMsg in and around `ConstructTemplateObject` and its callers, with what fires it, current behaviour, and disposition.

| # | File:line | Expression | What triggers it | Current behaviour | Fix |
|---|-----------|------------|------------------|-------------------|-----|
| 1 | `level.cc:1615` | `assert(objectToGenerate > 0)` | Caller passes 0 or negative template index | terminate | **Keep** — `wfmut::SpawnActor` pre-validates (`templateIdx <= 0` check); reaching here with bad idx is a caller bug |
| 2 | `level.cc:1616` | `assert(parentObjectIndex > 0)` | Caller passes 0 or negative parent index | terminate | **Keep** — `wfmut::SpawnActor` pre-validates (`parentIdx == 0` check); same rationale |
| 3 | `level.cc:1618` | `assert(ValidPtr(startupData))` | `FindTemplateObjectData` returned NULL for an index that `HasTemplate` said was valid | terminate | **Keep** — this is an internal consistency check; if `HasTemplate` is true the data must exist |
| 4 | `level.cc:1692` | `AssertMsg(containingRoom, "trying to spawn an object outside of all rooms")` | `FindContainingRoom` returned NULL — spawn position falls outside every Room bbox | terminate (the `return NULL` below it is dead code) | **Remove AssertMsg**, keep `return NULL` — a runtime-positioned spawn (script-fired, editor drop) at a valid but unroomed coordinate should fail cleanly, not abort |
| 5 | `level.cc:1700` | `assert(ValidPtr(retVal))` | `ConstructTemplateObject` (objects.c) returned NULL — happens for `Room_KIND`, `Disabled_KIND`, `Alias_KIND`, `Shield_KIND` which have `object = NULL` cases | terminate | **Remove** — NULL is a valid "this kind isn't runtime-spawnable" signal; `Level::ConstructTemplateObject` already gates its post-construction block on `if(createdObject)` so NULL propagates cleanly |
| 6 | `objects.c:317` | `assert(0)` in `default:` of `ConstructTemplateObject` | `type` is not any known `Actor::*_KIND` enum value | terminate | **Remove** — unreachable with well-formed OAD data but safe to return NULL if somehow reached; `ConstructOadObject`'s identical default assert (line 170) is **kept** because that path is startup-only and an unknown type there is always a build/data error |

Asserts 1–3 are kept because their preconditions are enforced by the `wfmut::SpawnActor` validation layer above; they fire only if the engine is called directly with garbage inputs, which is a programmer error. Asserts 4–6 are removed because they fire on legitimate runtime conditions (bad spawn position, unsupported kind) that should produce a NULL return, not a crash.

---

## Changes

### 1. `wfsource/source/game/level.cc` — `SafelyConstructTemplateObject`

**Outside-rooms path (~line 1690–1694):**

Replace:
```cpp
      else
      {
         AssertMsg(containingRoom,"trying to spawn an object outside of all rooms");
         return (Actor*)NULL;
      }
```
With:
```cpp
      else
      {
         DBSTREAM3( cdebug << "SafelyConstructTemplateObject: position outside all rooms" << std::endl; )
         return (Actor*)NULL;
      }
```

**NULL-return path (line 1700):**

Delete the line:
```cpp
	assert(ValidPtr(retVal));
```
`Level::ConstructTemplateObject` already gates its post-construction block on `if(createdObject)`,
so the NULL propagates cleanly up through `wfmut::SpawnActor`'s existing null check.

---

### 2. `wfsource/source/oas/objects.c` — `ConstructTemplateObject` default case (~line 315–318)

Replace:
```cpp
		default:
			DBSTREAM1( cerror << "object " << type << " doesn't exist"; )
			assert(0);					// attempted to construct object not in list
			break;
```
With:
```cpp
		default:
			DBSTREAM1( cerror << "object " << type << " doesn't exist" << std::endl; )
			break;
```
Note: `ConstructOadObject`'s default case at line 169 keeps its assert — that code path
is startup-only and an unknown type there is always a build error, not a runtime condition.

---

### 3. `engine/mutation/wfmut.cpp` — `SpawnActor` kind-guard comment (~lines 355–369)

The guard (Room/Tool/StatPlat) was a crash-shield. After the engine fix it is purely
descriptive documentation — the engine now returns NULL cleanly for those kinds. Update the
comment block:

```cpp
    // Engine-side SafelyConstructTemplateObject returns NULL cleanly for kinds that
    // ConstructTemplateObject (objects.c) doesn't support at runtime (Room, Disabled,
    // Alias, Shield). This pre-check is retained for a more descriptive error message.
    // Historically it was a crash-shield; the engine asserts that triggered the crash
    // were removed in the ConstructTemplateObject fail-soft fix (2026-06-03).
    if (const SObjectStartupData* td = level.FindTemplateObjectData(templateIdx)) {
        const int32 kind = td->objectData->type;
        if (kind == Actor::Room_KIND || kind == Actor::Tool_KIND ||
            kind == Actor::StatPlat_KIND)
            return failopt<ActorIdx>(
                "wfmut::SpawnActor: template class is not runtime-spawnable "
                "(Room/Tool/StatPlat return null from ConstructTemplateObject)");
    }
```

---

### 4. `engine/wf_edit/engine_bridge.cc` — `RunSpawnConfirmTest` Part A (~lines 645–665)

Replace the parked "HasTemplate scan — NOT spawned" block with an actual SpawnActor call.
Find the first live startup actor as `parentIdx`, then attempt the spawn. The expected
outcome for snowgoons (where all templates are Room/LevelObj/Tool kinds) is a graceful
null; the test passes on either a successful spawn or a clean null.

```cpp
    // ── Part A: SpawnActor fail-soft ─────────────────────────────────────────
    // Engine-side SafelyConstructTemplateObject now returns NULL cleanly for any
    // kind it doesn't support (Room, Disabled, Alias, Shield) instead of calling
    // terminate(). SpawnActor is therefore safe to call on any template.
    int template_idx = -1;
    for (int i = 1; i < obj_list_size; ++i) {
        if (wfmut::HasTemplate(*theLevel, i)) { template_idx = i; break; }
    }
    if (template_idx < 0) {
        std::fprintf(stderr, "[spawn-test] A-SKIP: no templates in 1..%d\n", obj_list_size - 1);
    } else {
        int parent_idx = -1;
        for (int i = 2; i < std::min(obj_list_size, 40); ++i) {
            if (wfmut::HasTemplate(*theLevel, i)) continue;
            if (wfmut::GetActorPos(*theLevel, i)) { parent_idx = i; break; }
        }
        if (parent_idx < 0) {
            std::fprintf(stderr, "[spawn-test] A-SKIP: no live startup actor for parentIdx\n");
        } else {
            const auto result = wfmut::SpawnActor(*theLevel, template_idx,
                                                   Vector3::zero,
                                                   static_cast<wfmut::ActorIdx>(parent_idx));
            if (result) {
                std::fprintf(stderr, "[spawn-test] A-PASS: spawned idx %d from template %d\n",
                             static_cast<int>(*result), template_idx);
            } else {
                // Graceful null — expected for Room/LevelObj templates in snowgoons.
                std::fprintf(stderr,
                    "[spawn-test] A-PASS (fail-soft): SpawnActor(template=%d, parent=%d)"
                    " -> null cleanly: %s\n",
                    template_idx, parent_idx, wfmut::lastError());
            }
        }
    }
```

Remove the trailing "SpawnActor deferred" line from the final `[spawn-test] PASS` fprintf.

---

### 5. `TODO.md`

Mark the `(a)` sub-item of "Deeper fail-clean follow-ups" as done (date 2026-06-03).

---

## Verification

1. **Build the editor:**
   ```
   cmake --build build-editor/ -- -j$(nproc)
   ```

2. **Inspect spawn-test output in stderr:**
   Look for `[spawn-test] PASS (all parts)` with an `A-PASS` line and no "SpawnActor deferred" suffix.

3. **Smoke-test the game build** (confirms no regressions in `SafelyConstructTemplateObject`
   for the normal Generator→coin spawn path in SMB W1-1):
   ```
   task build && task run-debug -- wflevels/smb_w1_1-standalone.iff
   ```
   Coins should still pop from `?`-blocks.
