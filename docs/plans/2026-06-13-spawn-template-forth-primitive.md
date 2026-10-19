# `spawn-template` Forth primitive (+ fix the wfmut orphan-spawn bug)

## Context

Today a script can only spawn a template-flagged actor by authoring a `Generator`
in the `.lev` and firing its activation mailbox — friction for runtime-positioned
spawns (drops, projectiles). Add a direct
`spawn-template ( vx vy vz x y z template_idx -- new_actor_idx )` Forth primitive
(sibling to the just-landed `read-actor-mailbox`). Full design is in
[the investigation](docs/investigations/2026-05-26-spawn-template-forth-primitive.md),
but **two of its premises are now stale** and the implementation is simpler than it
describes:
- Its "layering problem / inject a `SpawnTemplateFn` callback" is **obsolete**:
  `scripting_zforth.cc` already `#include "level.hp"` and calls
  `theLevel->ConstructTemplateObject` + `AddObject` **directly** (FSN's `fsn_spawn`,
  `scripting_zforth.cc:156-165`). So `spawn-template` calls the game layer directly —
  no callback indirection.
- Its syscall id (custom 4 / 132) is **stale** (FSN claimed custom 3-23). Use the
  next free id, **custom 25 / `153 sys`** (`read-actor-mailbox` took 24).

The investigation also surfaced a real latent bug: **`wfmut::SpawnActor`
(`wfmut.cpp:343`) calls `ConstructTemplateObject` but never `AddObject`** → an
orphan actor (`GetObjectIndex()==0`, in no room, never updates). The Generator path
(`generator.cc`) does both. Fix both spawn paths by routing through one shared helper.

## Design

### One shared spawn helper (fixes the orphan bug, kills the drift)
`Level::SpawnTemplate(int templateIdx, int idxCreator, const Vector3& pos, const
Vector3& vel) -> int` (declare `level.hp`, define `level.cc`) — the single place that
does the full Generator spawn sequence:
1. validate `templateIdx > 0` && `HasTemplate(templateIdx)` (`level.cc:1706`);
2. the unsafe-class fail-soft from `wfmut::SpawnActor` — `FindTemplateObjectData(idx)`
   kind-check rejecting `Room_KIND/Tool_KIND/StatPlat_KIND` (their OAS constructors
   `terminate()` rather than fail softly);
3. `idxCreator > 0`;
4. `Actor* a = ConstructTemplateObject(templateIdx, idxCreator, pos, vel)`; if null → `0`;
5. **`AddObject(a, pos)`** (the missing call) → `return a->GetActorIndex();`.

Returns `0` on any invalid/unsafe/blocked spawn (a legitimate outcome — blocked spawn
point or exhausted Poof chain). Route through it:
- **`wfmut::SpawnActor`** — keep its detailed `failopt` UX messages, but replace the
  inline `ConstructTemplateObject` + bare `return GetActorIndex()` with
  `int idx = level.SpawnTemplate(...)` (closes the orphan bug; the validations overlap
  harmlessly as a safety net).
- **`fsn_spawn`** (`scripting_zforth.cc:154`) — collapse its inline construct+add to
  `SpawnTemplate` (DRY; keeps its FSN bbox/budget guards).

### zForth `spawn-template` (custom 25 / `153 sys`)
Handler in the `default:` switch (after the `custom == 24` read-actor-mailbox block):
```cpp
} else if (custom == 25) {
    // spawn-template ( vx vy vz x y z template_idx -- new_actor_idx )
    int   tmpl = (int)zf_pop(ctx);
    float z=(float)zf_pop(ctx), y=(float)zf_pop(ctx), x=(float)zf_pop(ctx);
    float vz=(float)zf_pop(ctx), vy=(float)zf_pop(ctx), vx=(float)zf_pop(ctx);
    int idx = 0;
    if (theLevel)
        idx = theLevel->SpawnTemplate(tmpl, g_curObj,
                  Vector3(Scalar::FromFloat(x), Scalar::FromFloat(y), Scalar::FromFloat(z)),
                  Vector3(Scalar::FromFloat(vx),Scalar::FromFloat(vy),Scalar::FromFloat(vz)));
    zf_push(ctx, (zf_cell)idx);   // 0 if not spawned — script must guard
}
```
`g_curObj` (the running actor, always `>0` for a real actor script) is the parent.
Word def `: spawn-template 153 sys ;` after the `read-actor-mailbox` def; update the
syscall-map comment + `neural_forth.h` doc list.

### Other engines (optional parity, flagged)
`spawn_template` C closures in `scripting_lua.cc` + `scripting_quickjs.cc` (and
`scripting_wamr.cc`) calling the same `theLevel->SpawnTemplate`. zForth is the
canonical engine and the only one the SMB work needs — *can be dropped to keep this
zForth-only.*

## Files
`wfsource/source/game/level.{hp,cc}` (new `SpawnTemplate`), `engine/stubs/scripting_zforth.cc`
(handler + word def + comment + `fsn_spawn` refactor), `engine/mutation/wfmut.cpp`
(`SpawnActor` → `SpawnTemplate`, fixes the orphan bug), `engine/neural-forth/neural_forth.h`
(doc), `engine/mutation/wfmut_smoke.cpp` (test), optional `scripting_lua.cc`/`scripting_quickjs.cc`/`scripting_wamr.cc`.

## Regression test (same commit)

**What's deterministically testable** (a generic *happy-path* spawn is **not** — the
smoke already defers SR1/SR2/SR7/SR8/SR10 because smb_w1_1's first template has
content-specific spawn-point/collision requirements; honour that). In `wfmut_smoke`:
- **Forth dispatch + safe-fail:** eval `spawn-template` via `RunScript` (override-free
  context, like RA1) with a **bad** template index → returns `0` and **does not abort**
  the engine (the validation prevents the `SafelyConstructTemplateObject` assert). Bite:
  disable the word def → `ZF_ABORT_NOT_A_WORD`.
- **Shared helper safe-fail:** `level.SpawnTemplate(-1/99999, player, …) == 0` and an
  unsafe-class template (Room/Tool/StatPlat, found via `FindTemplateObjectData`) → `0`,
  no abort. This is the assertion that would crash before the kind-check guard.
- Existing `SpawnActor` input-validation cases (SR0/SR6/SR11) stay green through the
  refactor.

The **orphan-bug fix** (`AddObject`) and a real happy-path spawn stay content-specific:
covered by routing both spawn entry points through the one helper that always
`AddObject`s, plus the bridge `scene:live_create_node` path the suite already points to.
If a known-safe template+clear-position is identified at impl time, un-defer one SR
happy-path case to assert `GetObject(idx)` is registered post-spawn; otherwise leave it
as the documented manual/bridge case (don't fake a generic happy-path the suite already
judged unreliable).

## Verification
1. **Build**: `task build` (touch `scripting_zforth.cc` to force the stub recompile). Clean.
2. **Smoke**: `task test-wfmut` / `wf_game -L … --wfmut-smoke` → new spawn-template cases
   pass; SR0/SR6/SR11 still pass; no new aborts.
3. **Bite**: disable the `spawn-template` word def → its smoke case fails
   (`ZF_ABORT_NOT_A_WORD`); restore. Temporarily revert the `AddObject` line in
   `SpawnTemplate` → confirm a spawned actor is an orphan via the bridge spawn path (manual).

## Out of scope
- Template-name → constant authoring (investigation option 2) — separate follow-up when a
  2nd runtime-spawn site lands.
- Approach A (pooled-generator fireball) — already shipped; this is the orthogonal Approach B.
- Arbitrary-velocity / concurrent-burst consumers — this primitive enables them; wiring a
  specific consumer is separate.
