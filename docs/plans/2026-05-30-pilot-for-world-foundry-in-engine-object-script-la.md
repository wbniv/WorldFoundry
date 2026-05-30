# PILOT for World Foundry — in-engine object-script language + external bridge driver

## Context

World Foundry already runs scripts under a neutral dispatcher ([`ScriptRouter`](/home/will/WorldFoundry.2026-new-level/engine/stubs/scripting_stub.cc)) that selects one of several peer engines (Lua, Fennel, Wren, Forth, JS, Wasm) by an integer `language` index. The request is to add **PILOT** — the 1960s Computer-Assisted-Instruction language — as a new language type, and to also let PILOT drive the engine **from the outside**.

PILOT's native loop is *emit a stimulus → await a response → classify it → branch* (`T`ype / `A`ccept / `M`atch / `J`ump with `Y`/`N` conditioners). That maps two ways:

- **In-engine** — a per-actor `{Script}` that runs as a frame-resumable dialogue/cutscene/AI **state machine**.
- **External** — a PILOT program over the TCP **debug bridge** ([`engine/stubs/debug_server.cc`](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc)) for interactive **tutorials** (PILOT's original teaching purpose), **cutscene/demo direction**, and **headless verification** (the scenarios currently hand-written in Python).

This plan was designed, then adversarially reviewed against the shipping code; every review **blocker**/**major** is folded in and stale claims dropped (see [Corrections](#corrections-applied-from-review)).

### Decisions (from the user)
- **Scope:** both surfaces (in-engine + external), one shared core.
- **External-driver language:** **Python reference driver → C++ shared core** (phased — Python for language-design speed on the existing `BridgeClient`, then fold into the canonical C++ `pilot_core`; a shared `.pilot` conformance corpus prevents drift during the window).
- **Turtle graphics:** **deferred** to a follow-up phase — fully specified in [Deferred follow-ups](#deferred-follow-ups) so it isn't lost.
- **Turtle angle units (for that deferred phase):** **degrees by default**, with an opt-in revolutions marker.

## Constraints

- **Runtime stays light; never pull in the editor or its dependencies** (ImGui/ImGuizmo/CRDT/Yrs). Dependency direction is strictly one-way: editor & tools → engine-core, never the reverse. The `WF_PILOT_ENGINE` build block adds only new `.cc` files with **no `target_link_libraries`**.
- The interpreter is **from-scratch C++** (~500 lines, zero third-party code) — lighter than vendoring a historical PILOT, and the only way to get the WF-specific verbs + host-agnostic core. *(User relaxation noted: a small vendored C/C++ PILOT core would be an acceptable exception to "no new external libs"; we still recommend from-scratch.)*
- Honor existing conventions: timing in **seconds** via `LevelClock`; **named** mailbox constants (and call out the `INDEXOF_` prefix the user wants gone rather than propagate it); **no RTTI**, no `ptr != nullptr`; mailbox values are `Scalar` (float on PC dev, fixed-point on target).

## Architecture

**One shared, host-agnostic interpreter core (`pilot_core`), two thin backends behind a single `PilotHost` virtual interface.** The tokenizer, statement model, program counter, call stack, match flag, `#`numeric/`$`string variable store, `(expr)` evaluator, and `Y`/`N` conditioner logic are identical regardless of target. Only the **effect verbs** differ, and only in their tail.

```
                  pilot_core  (parser + PilotVM::Step(PilotHost&))
                  pure C++, no I/O, no blocking, mock-testable
                                   |
            +----------------------+-----------------------+
            |                                              |
    MailboxHost : PilotHost                       BridgeHost : PilotHost
  engine/pilot/host_mailbox.cc                  external driver (C++ Phase 3;
  in-process; verbs call                        Python reference Phase 1)
  MailboxesManager directly;                    JSON over TCP to debug_server;
  Await = COROUTINE (record                     Await BLOCKS the driver thread
  pending-await, yield, VM
  re-entered next frame)
            |
   in-engine pilot_engine (kDispatch slot 6) — {Script} PILOT runs in-level
```

The one genuine divergence — in-engine **cannot block** (it runs on the per-frame game thread), external **must block** — is contained entirely in `Await`: the core calls `host->Await(req, out)` and the backend decides. `MailboxHost::Await` returns `Pending` and parks the per-actor PC; `BridgeHost::Await` blocks the socket thread.

```cpp
// engine/pilot/pilot_host.hp — host-agnostic effect interface (no RTTI, Scalar-typed)
struct PilotHost {
    virtual ~PilotHost() = default;
    virtual void   Type(const char* text, bool newline) = 0;          // T: / TH:
    virtual void   SetMailbox(int actorIdx, int mailbox, Scalar v) = 0;
    virtual Scalar ReadMailbox(int actorIdx, int mailbox) = 0;
    virtual void   SetTransform(int actorIdx, Scalar x, Scalar y, Scalar z) = 0;
    virtual void   SetProp(int actorIdx, const char* key, Scalar v) = 0;
    virtual void   InjectInput(int slotId, int bits, int durationFrames) = 0;
    virtual void   Pause() = 0;  virtual void Resume() = 0;  virtual void Step(int frames) = 0;
    virtual bool   Screenshot(const char* filename) = 0;              // false on error
    virtual int    Pick(const Vector3& o, const Vector3& d) = 0;      // -1 = miss
    virtual void   ReloadScript(int actorIdx, const char* src) = 0;
    virtual void   Undo() = 0;  virtual void Revert() = 0;

    enum class AwaitKind { Mailbox, Broadcast, ClockSeconds };
    enum class RelOp     { Eq, Ne, Gt, Ge, Lt, Le };                  // NEW relational primitive
    struct AwaitReq { AwaitKind kind; int actorIdx; int mailbox; RelOp op;
                      const char* bcastOp; Scalar value; Scalar timeoutSecs; };
    enum class AwaitState { Satisfied, Pending, TimedOut };
    virtual AwaitState Await(const AwaitReq& req, Scalar& outValue) = 0;  // the ONLY divergence
};
```

## Integration points

| File | Add / edit | Specifics |
|---|---|---|
| `engine/pilot/pilot_core.{hp,cc}` | **add** | parser + `PilotVM`; pure, no I/O. |
| `engine/pilot/pilot_host.hp` | **add** | the vtable above. |
| `engine/pilot/host_mailbox.cc` | **add** | `MailboxHost : PilotHost`; coroutine `Await`. |
| `engine/stubs/scripting_pilot.{hp,cc}` | **add** | namespace `pilot_engine`, mirroring [`scripting_forth.hp:42-76`](/home/will/WorldFoundry.2026-new-level/engine/stubs/scripting_forth.hp). Plug ABI **confirmed**: `float RunScript(const char* src, int objectIndex)` (matches `scripting_forth.hp:57` + the `using RunFn = float(*)(const char*,int)` typedef at `scripting_stub.cc:196`). `.cc` gated `#ifdef WF_PILOT_ENGINE_BUILTIN`, module-static state paralleling [`scripting_zforth.cc:52-66`](/home/will/WorldFoundry.2026-new-level/engine/stubs/scripting_zforth.cc). |
| `engine/stubs/scripting_stub.cc` | **edit** | (1) add `/* 6 pilot */ pilot_engine::RunScript` to `kDispatch[]` (`:197-232`; `RangeCheck` max is exclusive per `assert.hp:203`, so slot 6 is safe). (2) `#ifdef WF_WITH_PILOT` Init/Shutdown/AddConstantArray/DeleteConstantArray in ctor/dtor/broadcast (mirror `WF_WITH_FORTH` at `:141,184,213,257`). |
| `wfsource/source/game/actor.cc` + `level.cc` | **edit** | **Language-selection obstacle (corrected).** `actor.cc:964` hardcodes `EvalScript(_pScript, idx, 3)` (Forth); `level.cc:283-286` forwards by integer `language` only — `ScriptRouter` **never sniffs content** (the header's "sigil dispatcher" wording was never implemented). **Fix A (chosen):** add a content-sniff inside `ScriptRouter::RunScript` when `language==3` — peek the first non-blank line for a PILOT shape (`R:pilot` sigil or a leading `<verb>:` from the known set) and re-route to slot 6; `3` stays the Forth fallback. Keeps `EvalScript` a thin forwarder. **Fix B (deferred):** restore the OAD `ScriptLanguage` field (the follow-up anticipated by the `actor.cc:960-962` comment; OAS-field policy = new fields after existing ones). |
| `engine/build_game.sh` | **edit** | **Critical — `task build` runs this script, not CMake.** Add `WF_PILOT_ENGINE="${WF_PILOT_ENGINE:-builtin}"` + validation; a CXXFLAGS case adding `-DWF_WITH_PILOT -DWF_PILOT_ENGINE_BUILTIN` (mirror `:199`); and `compile_stub` lines for `scripting_pilot.cc` + `pilot_core` + `host_mailbox` (mirror the zforth line at `:534`). **No vendored lib.** Without this, `task build` silently ships `kDispatch[6] == nullptr`. |
| `engine/CMakeLists.txt` | **edit** | `set(WF_PILOT_ENGINE "builtin" CACHE STRING "none | builtin")`; source-add block (`-DWF_WITH_PILOT -DWF_PILOT_ENGINE_BUILTIN`, no link lib); force-off in the `if(ANDROID OR IOS)` block (`:64-74`) to respect "mobile = Forth-only". (CMake is the secondary/editor path; `build_game.sh` is canonical.) |
| `Taskfile.yml` | **edit** | Add `WF_PILOT_ENGINE=builtin` to the `task build` env block (`:23-29`) so the default build/test loop actually exercises PILOT. |
| `debug_server.cc` reload sites | **edit (Phase 5)** | `:558,:711,:715,:757,:810` hardcode `forth_engine::ReloadActorScript/ClearActorScriptOverride(s)`. Make language-aware (sniff `source`) so PILOT hot-reload isn't dead code; phase with the in-engine reload trio. |

## In-engine execution model: **frame-resumable**

A persistent **per-actor program counter**; blocking verbs (`A:`, `PA:`, `WM`/`WT`) suspend until satisfied — turning a linear PILOT program into a per-actor state machine.

- `actor.cc:957-965` already calls `EvalScript` **once per actor per frame** with a **stable `_pScript` pointer** (set once from the OAD common block at `actor.cc:318`, read each frame at `:964`) — exactly the tick a resumable VM wants. Multiple actors sharing one `_pScript` blob is handled by keying the immutable parsed `Program` on the `src` pointer and the mutable `ActorState` on `objectIndex` (the two-map split zForth uses at `:58/:375`).
- A persistent PC *is* the state machine — authors don't hand-roll phase mailboxes.
- **Budget** `kMaxStmtsPerFrame = 256` bounds runaway loops by **suspending** (resume next frame), never aborting. Finished programs mark `Halted`; loops are explicit (`J:*top`).
- `ActorState` (pc, run-state, `matchFlag`, `waitUntil`, call stack, var maps, accept buffer) keyed by `objectIndex`; a program-pointer guard resets on index reuse after despawn.

Run-to-completion was rejected — it forces re-implementing, in mailbox state, the wait machine the VM should own.

## PILOT command table

**(A)** standard PILOT · **(B)** in-engine `MailboxHost` (game thread, frame-resumable) · **(C)** external `BridgeHost` (driver thread, blocking).

### Standard PILOT verbs

| Verb | A — standard PILOT | B — in-engine | C — external |
|---|---|---|---|
| **T:** | Type text (+newline) | `host->Type(...)`: **stderr-only on desktop** (mirrors zForth `EMIT`/`TELL`→stderr, `scripting_zforth.cc:98-117`), **no-op on target**. *No HUD-text mailbox exists* (HUD slots are numeric: `HUD_SCORE`=70, `HUD_TIMER`=71, `LIVES`=72) — on-screen text is deferred Phase 4. | print to operator console |
| **TH:** | Type-hang (no newline) | same, `newline=false` | console, no newline |
| **A:** | Accept student input | **Await the engine** — `host->Await({Mailbox,…})` coroutine: park PC, resume when the watched mailbox satisfies the relation → accept buffer + `#last`. | `Await` **blocks** on `watch` + the **relational poll** (below) → accept buffer + `#last` |
| **M:** | Match buffer vs list; set Y/N flag | compare accepted value/var vs literal list or relational form (`M #last > 40.0`); set `matchFlag` (survives frames). Pure VM-local. | identical, client-side over `mailbox_values`. `MN:` = failed assertion / wrong-action branch |
| **C:** | Compute / assign | bare `#`/`$` LHS → VM-local `Scalar`/`std::string` arithmetic. **Qualified LHS → engine write:** `C:$a.MBX=`→`SetMailbox`; `C:$a.pos=(x,y,z)`→`SetTransform`; `C:$a.cls.field=`→`SetProp`. `C:` **defines its own int-vs-`Scalar` division** (truncating int for index math; `Scalar::operator/` for measured quantities). | identical; qualified LHS → `set_mailbox`/`scene:set_transform`/`scene:set_prop` |
| **J:** | Jump to `*label` | PC jump (label pre-resolved to stmt index, O(1)) | client control flow |
| **U:** | Use (call subroutine) | push return addr, jump; **call-depth cap 64** | client call stack |
| **E:** | End / return | return from `U:`; top level → `Halted` (no auto-restart) | return; top level → optional `resume` + exit |
| **Y: / N:** | conditioner (run iff last Match Y/N) | gate line on persistent `matchFlag` (`TY:`, `JN:*again`) | identical |
| **R:** | Remark | comment; also the **`R:pilot` sigil** stripped like `\ wf` and used by fix A's sniff | comment |
| **PA:** | Pause (time/keypress) | `waitUntil = ReadMailbox(idx, TIME) + secs` (**seconds**; `TIME`=1906→`level.cc:1511`); coroutine-suspend | operator authoring breakpoint: sleep / getchar |
| **(expr):** | parenthetical conditioner | extra boolean AND-guard (`T(#x>5):big`), VM-local | identical |

### WF engine-control extension verbs

Two-letter PILOT-style mnemonics. Each external verb maps to **exactly one existing bridge op** (unknown ops are silently ignored at `debug_server.cc:452`, so v1 needs no engine C++ beyond the in-engine engine). In-engine, time-control verbs are no-ops/asserts (an actor can't pause itself from inside its own frame).

| Verb | Name | B — in-engine | C — external bridge op |
|---|---|---|---|
| **PS** | PauSe | no-op/assert | `{"op":"pause"}`, block for `paused` (`:334`) |
| **PR** | PRoceed | no-op/assert | `{"op":"resume"}` ⚠ dt-spike (see Verification) |
| **ST** | STep | no-op/assert | `{"op":"step","frames":n}` (default 1, `:346`) |
| **IN** | INput inject | (use `SM` on RAW slot) | `{"op":"inject_input","slot",…,"value","duration_frames"}` (`:385`); `held -1`=sticky, `0`=one frame |
| **WM** | WaitMailbox | `Await({Mailbox,op,val})` coroutine | `watch` + **relational poll** (NEW; not `wait_for_mailbox`) |
| **WB** | WaitBroadcast | n/a | `wait_for(op==…)` on `paused`/`screenshot_done`/`picked`/`error`/`reverted` |
| **WT** | WaiT seconds | `waitUntil = ReadMailbox(idx,TIME)+secs` | watch `TIME`(1906) **at idx=1** + relational `>=` poll. Seconds via LevelClock, not wall-clock. |
| **SP** | Set Position | `SetTransform` | `{"op":"scene:set_transform","idx","pos"}` |
| **SF** | Set Field | `SetProp` | `{"op":"scene:set_prop","idx","key","value"}` |
| **SM** | Set Mailbox | `SetMailbox` | `{"op":"set_mailbox","idx","mailbox","value"}` |
| **WA** | WAtch | n/a | `{"op":"watch"}` / `{"op":"unwatch"}` |
| **SH** | SHot | n/a (no GL in actor frame) | `{"op":"screenshot","filename"}` → `screenshot_done` (`:911`) |
| **SR** | ScRipt reload | n/a | `{"op":"reload_script","idx","source"}` — language-aware (Phase 5) |
| **SG** | Shader | n/a | `{"op":"set_shader","vert","frag"}` |
| **PK** | PicK | n/a | `{"op":"scene:pick",…}` → `picked` (`:689`) → accept buffer |
| **UN** | UNdo | n/a | `{"op":"undo_step"}` |
| **RV** | ReVert | n/a | `{"op":"revert_all"}` → `reverted` |
| **NW / DL / BT** | spawn / despawn / batch | (pooled-actor activate via `SM`) | **v2 — reserved.** No spawn/despawn/batch op over TCP today; don't fake them |

### Three review-critical semantics (load-bearing)

1. **New relational await primitive.** `wait_for_mailbox` is **exact-equality only** (`abs(cur-expected)<1e-3`, `debug_bridge_client.py:146`) — it cannot express the `>`/`>=`/`<` that `WM`/`WT` need. The `BridgeHost::Await` body must be a **new** poll over `mailbox_values[(idx,mbx)]` that evaluates the requested `RelOp`. A first-class Phase-1 deliverable, not the existing helper.
2. **Globals-at-idx-1 addressing.** `BroadcastMailboxes` only emits for a *valid Actor index* (`debug_server.cc:1007-1012`). Global/system mailboxes must be watched at a fixed valid actor (conventionally **idx=1**); per-actor mailboxes use the actor's own index. `WA`/`WM`/`$actor.MBX` must auto-route globals to idx=1, or `WM $P #SMB_STATE` silently gets nothing.
3. **`IN` targets exactly one slot.** `GetInputOverride` is keyed by `mailbox_id` (`debug_server.cc:1033`); injecting `joystick1_raw` (1909) does **not** populate `*_JUSTPRESSED` (1910), and sticky injection never returns to 0. Edge-sensitive gameplay needs injecting on the JUSTPRESSED slot too, or an explicit press→release pulse across stepped frames.

## Phase breakdown

- **Phase 0 — spec + conformance corpus.** Author the grammar (table above) + `tests/pilot/*.pilot` with expected stdout/exit/screenshot. The contract every backend must pass. *(No code.)*
- **Phase 1 — Python reference driver** `tests/pilot/pilot_driver.py` over `BridgeClient`. Standard verbs + external extensions, **including the relational poll, idx-1 rule, and per-scenario teardown** (clear sticky `inject_input`, `unwatch` all; re-issue `WA` after reconnect — `CLIENT_DISCONNECT` clears watches at `:883`). Collapses `verify_smb_fireball.py` to ~15 lines. *Commit.*
- **Phase 2 — C++ `pilot_core` + `MailboxHost` + in-engine `pilot_engine` (slot 6).** Wire `build_game.sh` (critical), `CMakeLists.txt`, `Taskfile.yml`, `scripting_stub.cc` dispatch, and the `actor.cc`/`level.cc` content-sniff (fix A). Run the same corpus against the in-engine path via the bridge to prove core parity. *Commit.*
- **Phase 3 — `BridgeHost` C++ host tool.** Same `pilot_core` drives the bridge; retire the Python dialect once parity holds. *Commit.*
- **Phase 4 — engine HUD-text path** (only if tutorials need on-screen `T:`). Real engine HUD-text, not a mailbox. *Commit.*
- **Phase 5 — language-aware hot-reload** at the `debug_server.cc` reload sites. *Commit.*
- **Phase 6 — turtle graphics** (see [Deferred follow-ups](#deferred-follow-ups)). *Commit.*

## Verification

- **Headless via the bridge:** boot a level under the bridge, stay **paused and drive with `ST`** (never `PR`) — `step` doesn't clamp dt, so resume-after-pause feeds one giant dt; frame-stepping is dt-stable (`DebugServer_IsPaused` lets exactly N frames through, `:563-572`; `DrainQueue` applies queued ops at frame top before `Level::update`). The compiler should **lint-warn if `PR` follows a blocking `WM`/`WB`/`PA`**.
- **`SH` one-frame lag:** the screenshot captures the *previous* frame (`debug_server.cc:887-892`); emit `SH` then `ST 1` to capture the exact asserted state.
- **Screenshot proof** (required for gameplay features): every scenario ends with `SH name.png` then `ST 1`; check PNGs into `tests/pilot/screenshots/`.
- **mp4 recording:** record a passing run with the engine's `-record_video` into `tests/recordings/` and link from this plan.

### Worked example — `tests/pilot/walk_right.pilot`

Verified constants: `X_POS=3009`, `BTN_RIGHT=0x2000`, string slot `"joystick1_raw"`. `$P` = player idx, bound at boot.

```pilot
R:pilot ── verify the player walks RIGHT under injected input
C:#THRESH = 40.0
C:#FRAMES = 30
PS                                          R: pause; block until {"op":"paused"}
WA $P #X_POS                                R: watch player X_POS at the actor's own idx
ST 8                                        R: settle on the ground (deterministic)
C:#x0 = ?($P, #X_POS)                       R: host->ReadMailbox
T:start X = $#x0  (need > $#THRESH)
IN joystick1_raw #BTN_RIGHT held #FRAMES    R: inject RIGHT sticky for 30 frames
ST 30                                       R: step exactly 30 frames
WM $P #X_POS > #THRESH timeout 5.0          R: RELATIONAL poll (NEW); value → #last
M #last > #THRESH
SH walk_right.png
ST 1                                        R: advance so the shot is the asserted state
TY:PASS — player reached X=$#last
TN:FAIL — player stalled at X=$#last
JN:*fail
E
*fail
E
```

The driver never sends `resume` — dt stays frame-stable by construction.

## Deferred follow-ups

These are committed roadmap items (specified now so the design isn't lost), not speculative extras.

### Phase 6 — Turtle graphics (2D `GR:` + 3D extension)

PILOT's classic `GR:` turtle command, extended to 3D. **The key insight:** WF stores every actor's transform as a `Matrix34` ([`wfsource/source/math/matrix34.hp`](/home/will/WorldFoundry.2026-new-level/wfsource/source/math/matrix34.hp)) whose rows 0–2 are the rotation basis — which *is exactly* a 3D turtle's orthonormal frame **H** (heading/forward, +X), **L** (left, +Y), **U** (up, +Z). `H×L = U` (right-handed), and yaw about U = WF Z = Euler `c`, matching `currentDir() = (cos c, sin c, 0)`. **The turtle is an actor; driving it drives the transform.**

- **State:** keep the turtle frame as a `Matrix34`/quaternion **source of truth**; convert to the stored `Euler (a,b,c)` only at the write boundary via existing `Euler` math (sidesteps gimbal-order issues; avoids asserting which label WF pins on `a`/`b`/`c` — verify before trusting).
- **Three intrinsic rotations** (the L-system operators): **YAW** about U (`+`/`−`), **PITCH** about L (`^`/`&`), **ROLL** about H (`\`/`/`).
- **Branching** — **PUSH `[` / POP `]`** save/restore the whole frame → spawn child actor / sub-path. This turns turtle graphics into an **L-system engine** (3D trees, ferns, fractals).

| 2D `GR:` | 3D extension | WF mapping |
|---|---|---|
| `DRAW n` | `F n` (pen down) | move +n along **H**; if pen down, render trail |
| `GO n` | `f n` (pen up) | move along **H**, no trail |
| `TURN n` | `YAW n` | rotate frame about **U** (→ Z / Euler `c`) |
| — | `PITCH n` | rotate about **L** (→ Y) |
| — | `ROLL n` | rotate about **H** (→ X) |
| `TURNTO h` | `ORIENT a,b,c` | absolute frame |
| `GOTO/DRAWTO x,y` | `…x,y,z` | absolute move (pen up/down) |
| — | `[` `]` / `PUSH` `POP` | branch (spawn child / sub-path) |
| `PEN UP/DOWN/c` | same | toggle trail; set material |
| `CLEAR` / `HOME` | same | clear trail / reset turtle |

- **Pen rendering (decision pending at Phase 6 — user leaned "decide later"):** native **`RenderObject3D` mesh extrusion** (engine-native, no deps; vertex caps already raised to 32000 — best for shapes/plants) and/or **breadcrumb actor spawning** (`wfmut::SpawnActor` — best for formations; in-engine only since the bridge lacks a spawn op). External-mode turtle drives `scene:set_transform` for camera/character paths.
- **Angle units (decided):** **degrees by default** (`TURN 90`), faithful to Logo/PILOT, converted to revolutions at the boundary. **Opt-in revolutions** via a literal suffix — `TURN 0.25r` (or `…rev`) — and a program-scope directive `GR:UNITS REVOLUTIONS|DEGREES`. (Direct rotation-mailbox writes via `C:` remain raw **revolutions** to match the engine's authored-angle convention.)
- **Use cases:** procedural geometry, L-system plants/fractals, patrol/cutscene/camera paths, spawn formations, teaching guide-arrows.

### Other deferred items
- **Fix B — restore OAD `ScriptLanguage` field** (supersedes the content-sniff; OAS-field policy).
- **HUD-text engine path** (Phase 4) — real on-screen `T:` for tutorials (no string mailbox exists today; `T:` is stderr/no-op until then).
- **Spawn/despawn bridge ops** (`NW`/`DL`) exposing `wfmut::SpawnActor/RemoveActor`; **batch op** (`BT`). Until then, pooled-actor activation via `SM` and pause+ordered-ops+`ST 1` atomicity.
- **Language-aware hot-reload** (Phase 5).

## Corrections applied from review

- `JOY_RAW=1009` **dropped** — truth is `HARDWARE_JOYSTICK1_RAW = 1909` (`mailbox.inc:95`); injection uses the string slot `"joystick1_raw"`.
- `mb()` range-check bound corrected to **`GLOBAL_USER_MAX = 1900`** (bumped 999→1900, 2026-05-09), not the literal 999.
- zForth float-`/` gotcha **dropped** as an inherited risk — doesn't transfer to a from-scratch interpreter; reframed as a `C:` design choice.
- "sigil dispatcher already routes by content" **dropped** — `ScriptRouter` dispatches purely by integer `language`; the content-sniff (fix A) is net-new code.
- "T: degrades to a HUD/text mailbox" **dropped** — no such mailbox; `T:`/`TH:` are stderr-only on desktop, no-op on target.
- "`WM` = `wait_for_mailbox`" **dropped** — that helper is exact-equality only; the relational poll is a new first-class deliverable.
