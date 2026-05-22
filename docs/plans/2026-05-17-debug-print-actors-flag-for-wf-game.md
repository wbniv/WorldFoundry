# `--debug-print-actors` flag for `wf_game`

## Context

Debugging WF levels via the engine + debug bridge currently requires correlating bridge `{"op":"state","idx":N,"pos":[…]}` events with WF actor identities by position alone — there's no built-in way to learn that `idx=19` is e.g. `Target02` or that `idx=9` is the player. On 2026-05-17 we spent meaningful time disambiguating two player-shaped indices in SMB W1-1 and only confirmed `idx=19` was the camera lookat target by matching its coordinates against `LOOKAT_POS` in the Blender script. A one-shot construction-time log that prints `idx → mesh/kind/mobility/pos` per actor would make every future bridge session legible.

The flag is **opt-in** (off by default) so it doesn't bloat production logs, and runs **once per actor at construction**, not per frame. It pairs naturally with `--debug-port` / `--debug-bind` — typical usage is `wf_game -Llevel.iff --debug-port 7777 --debug-print-actors`.

## Build-mode gating (must-have)

All of the new code must be excluded from production builds. Per [`docs/compile-time-switches.md:44`](../WorldFoundry.2026-new-level/docs/compile-time-switches.md), the right guard is **`DO_TEST_CODE`**:

| Switch | `debug` | `safe-fast` | `release` | `final` | What it controls |
|--------|---------|-------------|-----------|---------|-----------------|
| `DO_TEST_CODE` | `1` | `0` | `0` | `0` | Test/debug-only code paths |

Wrap the new global, the new flag parser, and the new fprintf block in `#if DO_TEST_CODE … #endif`. In `release`/`final`/`safe-fast`/`profile` builds — and especially the console target — the code, the global, the strncmp, and the per-actor branch all disappear from the binary entirely. Zero overhead, zero attack surface. (`build_game.sh` is hardcoded to a debug-like config per the doc note, so dev builds get the flag automatically.)

## Recommended approach

### 1. Add the CLI flag

In **[`wfsource/source/game/main.cc`](../WorldFoundry.2026-new-level/wfsource/source/game/main.cc)**, mirror the existing `--debug-port` / `--debug-bind` pattern:

- After `char gDebugBind[256] = "127.0.0.1";` (line 52), add (inside `#if DO_TEST_CODE`):
  ```cpp
  #if DO_TEST_CODE
  int  gDebugPrintActors = 0;             // 1 = print idx/class/mesh/pos per actor at construction
  #endif
  ```
- After the `--debug-bind` branch (around line 194), add (inside `#if DO_TEST_CODE`):
  ```cpp
  #if DO_TEST_CODE
  else if ( strcmp( argv[index]+1, "-debug-print-actors" ) == 0 )
  {
      gDebugPrintActors = 1;
      DBSTREAM1( cprogress << "Debug print actors enabled" << std::endl; )
  }
  #endif
  ```

### 2. Print at actor construction

In **[`wfsource/source/game/actor.cc`](../WorldFoundry.2026-new-level/wfsource/source/game/actor.cc)** `Actor::Actor` constructor (line 625), right after `_idxActor = startupData->idxActor;` at line 643, the whole block wrapped in `#if DO_TEST_CODE`:

```cpp
#if DO_TEST_CODE
extern int gDebugPrintActors;
if (gDebugPrintActors)
{
    static const char* kMobilityNames[] = {"Anchored","Physics","Path","Camera","Follow"};
    int mob = GetMovementBlockPtr()->Mobility;
    const char* mobStr = (mob >= 0 && mob < 5) ? kMobilityNames[mob] : "?";
    const char* meshStr = "(none)";
    int32 meshID = GetMeshName();
    if (meshID != 0) {
        const char* nm = theLevel->GetAssetManager().LookupAssetName(packedAssetID(meshID));
        meshStr = nm ? nm : "(unresolved)";
    }
    const Vector3& p = _physicalAttributes.Position();
    std::fprintf(stderr,
        "actor idx=%d kind=%d mesh=%s mobility=%s pos=(%.2f,%.2f,%.2f)\n",
        _idxActor, kind(), meshStr, mobStr,
        p.X().AsFloat(), p.Y().AsFloat(), p.Z().AsFloat());
}
```

Notes:
- `kind()` is virtual — at construction time the Actor subclass's vtable may not yet be in place. **Verify call safety**; if the C++ rule that "during base ctor, virtual calls resolve to base impl" causes us to always get Actor's `kind()` instead of the subclass's, move the print to a post-construction hook (`Validate()` at line 649 is one option; a one-shot call from `level.cc` after all actors are constructed is cleaner). Fallback if `kind()` is unreliable: skip the kind field and rely on `mesh`+`mobility`+`pos` (already enough to identify in practice).
- `kMobilityNames` size 5 matches `MOBILITY_MAX=5` in [`oas/movement.h`](../WorldFoundry.2026-new-level/wfsource/source/oas/movement.h) (values 0..4 = Anchored, Physics, Path, Camera, Follow).
- `LookupAssetName` is inline in [`asset/assets.hpi`](../WorldFoundry.2026-new-level/wfsource/source/asset/assets.hpi) and returns `const char*` from the asset string map; null on miss.

### 3. Mention in `Taskfile.yml` + docs

- **[`Taskfile.yml`](../WorldFoundry.2026-new-level/Taskfile.yml)** `run-debug` task — append `--debug-print-actors` to the default arg list (the task is already opt-in by the user explicitly running it).
- **[`docs/level-building.md`](../WorldFoundry.2026-new-level/docs/level-building.md)** "Debug bridge" subsection — add a one-line mention with the flag and a sample line of output, so future debug sessions know the flag exists.

## Files to modify

| File | Change |
|---|---|
| `wfsource/source/game/main.cc` | new global + flag parser branch |
| `wfsource/source/game/actor.cc` | extern decl + conditional fprintf in `Actor::Actor` |
| `Taskfile.yml` | append `--debug-print-actors` to `run-debug` |
| `docs/level-building.md` | one-line mention in the "Debug bridge" subsection |

## Verification

1. `bash engine/build_game.sh` — clean compile.
2. `LD_LIBRARY_PATH=engine/libs DISPLAY=:0 engine/wf_game -Lwflevels/smb_w1_1-standalone.iff --debug-print-actors 2>&1 | grep '^actor idx='` — expect one line per actor.
3. Confirm `idx=19` line shows the camera lookat target at `pos=(4.50,0.00,1.50)` — closing the 2026-05-17 mystery.
4. Confirm Mario's player actor shows `mobility=Physics mesh=player.iff` at `pos=(4.50,0.00,1.50)` (spawn before settling).
5. Without the flag, no `actor idx=` lines appear — proves it's off by default.
6. Run the same against `wflevels/qbert_practice-standalone.iff` for a regression smoke — should produce ~28+ cube actors plus infrastructure.
7. Build-mode gating verification: `grep -c DO_TEST_CODE wfsource/source/game/{main,actor}.cc` ≥ 2 in each file (open/close `#if/#endif`). Even though `build_game.sh` is hardcoded to a debug-like config so we can't easily flip to release locally, the source-level gate is the contract.

## Open questions

These are worth raising before implementation but won't block:

- **Mesh-name miss case** — if the asset hasn't been loaded yet at `Actor::Actor` time, `LookupAssetName` returns null. Plan prints `(unresolved)`. OK?
- **StatPlat coverage** — StatPlats inherit Actor but their construction may take a slightly different path. Need to verify the print fires for them too; if not, add a sibling print to the StatPlat branch.
- **`kind()` reliability** — if it's unreliable at base-ctor time, fall back to `mesh+mobility+pos`-only output (still solves the original problem; `kind` is nice-to-have).
