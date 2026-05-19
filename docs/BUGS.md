# BUGS

Genuine bugs that have laid dormant for years before something surfaced them. Not TODOs, not feature gaps — bugs that *worked anyway* due to luck, dead code paths, or the bug never being exercised in practice.

**Eligibility:** Only bugs whose buggy code was **authored before 2026-01-01** belong here. If the code was written in 2026 or later, it is fresh-author error, not a dormant bug, and does not qualify regardless of how interesting the failure mode is. Verify with `git log --follow --diff-filter=A -- <file>` (or `git blame` on the specific lines) before adding an entry.

**Ordering:** Entries are sorted **reverse-chronologically by the date the bug was finally surfaced/fixed** (the date in each entry's title — newest first, oldest last, ending at the `## Template` section). When adding a new entry, insert it at the position its surface-date dictates; do not append blindly. If two entries share a date, group them together (insertion order within the date is fine).

Format per entry:
- **Title** with the date it was finally surfaced (`YYYY-MM-DD`, used for sorting)
- **Status:** FIXED `<sha>` | OPEN | INVESTIGATING
- **Symptom**, **Root cause**, **Why dormant**, **Fix**, **Investigation** (link)

---

## `RenderObject3D::Render` `&&` short-circuit reads + side-effect-assert writes past end of `_faceList` — 2026-05-19

**Status:** FIXED commit `29d3613`.

**Symptom:** `wf_host_gl_e2e_test --cycles=2 --level=...snowgoons-standalone.iff` SIGSEGVs at frame ~2 inside `DrainDoneSounds()` (audio/linux/buffer.cc) with `sDoneHead = 0xffff000000000000` (non-canonical pointer). The `wf_game` makefile build (asserts ON) exited 0 on the same input — the bug only surfaces under specific static-data layouts.

**Root cause:** Two long-standing bugs in [`gfx/glpipeline/rendobj3.cc`](../wfsource/source/gfx/glpipeline/rendobj3.cc):

1. **Past-end READ at line 83.** `while(currentMaterial == ...currentRenderFace->materialIndex && faceIndex<_faceCount)` — C++'s `&&` evaluates the LEFT operand first. After the last inner iteration `currentRenderFace++` points one past the end of `_faceList`; the next loop-condition check reads `_faceList[_faceCount].materialIndex` (past end) BEFORE the bounds check has a chance to short-circuit. ASan caught it as a 2-byte READ at offset +246 of the 240-byte `static TriFace cubeFaceList[12]` in [`renderassets/rendacto.cc`](../wfsource/source/renderassets/rendacto.cc):147.

2. **Past-end WRITE at line 101.** `assert(_faceList[_faceCount].materialIndex = -1);` — single `=` (assignment, not comparison). With asserts enabled, this writes -1 to past-end memory each frame. Pure typo from the original author.

**Why dormant:** Both bugs date back to the 2010 first git commit (`a2784f6`) and likely predate that. The past-end read returns garbage, which is used as a `materialIndex` for comparison — the comparison outcome is moot because the outer `faceIndex<_faceCount` check exits the loop the next iteration regardless. The past-end write lands on whatever's adjacent in `.data` — for the makefile build's static layout, that was benign padding. The cmake build (with NDEBUG-disabled asserts, additional translation units from quickjs/wamr/fennel/wren, and a different `.data` order) happened to place `static std::atomic<PlayInstance*> sDoneHead` (audio buffer.cc) close enough that the past-end-read's downstream consumers eventually wrote a non-canonical pointer there; `DrainDoneSounds` crashed dereferencing it. Yesterday's [host-gl plan](plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) noted "multi-cycle snowgoons crashes" — that report was actually a frame-2 single-cycle crash in the cmake-built harness, mis-bucketed as multi-cycle.

**Fix:** Swap `&&` operand order at line 83 so `faceIndex<_faceCount` short-circuits BEFORE the past-end materialIndex read; delete the broken assert at line 101 (the line was either a typo for `==` sentinel-check or stale debug code — no other code reads or writes that sentinel value).

**Investigation:** [`docs/investigations/2026-05-19-snowgoons-rendobj3-overread.md`](investigations/2026-05-19-snowgoons-rendobj3-overread.md).

---

## `~Level::~Level` violated `HALLmalloc` LIFO across three sites — 2026-05-18

**Status:** FIXED Phase B of [host-gl-e2e plan](plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) (commit pending).

**Symptom:** `wf_game --frame-step-smoke=N -L<level>` asserts at [`memory/lmalloc.cc`](../wfsource/source/memory/lmalloc.cc):308 (`(_currentFree - fl->_size) == mem`) inside `~Level::deleting template objects` after the run completes and unload starts.

**Root cause:** Three independent caller-side LIFO violations in `~Level::~Level` and its dependencies:
1. `_theLevelRooms` outer object freed in [`level.cc`](../wfsource/source/game/level.cc):649 second, despite being allocated at :465 — *before* `_theAssetManager`, `_commonBlock`, `_templateObjects` array, per-template entries.
2. Per-template-object loop iterated forward (`for idxActor = 0; idxActor < _numTemplateObjects; ++idxActor`) instead of reverse.
3. `Animate::_channels` ([`anim/anim.cc`](../wfsource/source/anim/anim.cc):120) and `ActorMailboxes::_localMailboxes` (via [`mailbox/mailbox.cc`](../wfsource/source/mailbox/mailbox.cc):54) defaulted `Array<T>::SetMax`'s memory pool to `HALLmalloc` — per-actor data ended up on the HAL stack interleaved with per-template-object data; actor-iteration-order destruction freed them out of HAL-allocation order.

**Why dormant:** Standalone `wf_game` never ran the full in-process `LoadLevel → UnloadLevel` cycle until the `--frame-step-smoke=N` CLI added 2026-05-18 (editor Phase 0b sub-task 1). In every prior run, window-close / SIGTERM / fatal-error `exit()` killed the process mid-loop, never reaching `~Level::~Level`. The bug had been latent across multiple unload paths since the original 1999-era LevelCon-era code.

**Fix:** Reorder `~Level::~Level` body to reverse-LIFO; split `MEMORY_DELETE(_theLevelRooms)` into manual `~LevelRooms()` (early) + late `HALLmalloc.Free` of the outer; reverse the per-template-object loop; route `Animate::_channels` and `ActorMailboxes::_localMailboxes` through the per-level DMalloc pool; add `Array<T>::Clear()` so `_actors._items` can be freed at its LIFO position in `~Level` body instead of by the implicit `~Array()` afterward.

**Investigation:** [`docs/investigations/2026-05-18-unloadlevel-lifo-bug.md`](investigations/2026-05-18-unloadlevel-lifo-bug.md).

---

## `_PlatformSpecificUnInit` asserted on a never-initialised `stacks` allocator — 2026-05-16

**Status:** FIXED commit `c3f89a7`.

**Symptom:** Clean engine shutdown (`exit(0)` from `main`) asserted on `assert(stacks)` in `hal/linux/platform.cc` (now `platform_init.cc`).

**Root cause:** `stacks` is a vestigial PIGS-era tasker allocator that was never wired up on Linux. The assert `assert(stacks)` in `_PlatformSpecificUnInit` would have caught a legit double-init / out-of-order shutdown on other platforms, but on Linux `stacks` is always `NULL`.

**Why dormant:** Same as the LMalloc one — `_PlatformSpecificUnInit` was rarely reached in practice. Surfaced by the same Phase 0b work that surfaced the LMalloc bug.

**Fix:** `if (stacks) { delete stacks; stacks = NULL; }` — guard instead of assert. Investigation at [`docs/investigations/2026-05-16-stacks-assert-on-clean-exit.md`](investigations/2026-05-16-stacks-assert-on-clean-exit.md).

---

## `PhysicalAttributes::Validate()` used strict float-equality on a round-tripped delta — 2026-05-11

**Status:** FIXED `a56cd51` — `fix(physics): tolerate float-precision drift in PhysicalAttributes::Validate`.

**Symptom:** `wf_game` aborted intermittently during the qbert cam intro pan with `FATAL ERROR: PhysicalAttributes::Validate() failed.` X and Z components matched exactly; Y differed at the 7th decimal (~5e-7 drift) — e.g. `predictedMotionVector.Y = 7.949417114` vs `expansionVector.Y = 7.949417591`.

**Root cause:** [`wfsource/source/physics/physical.hpi`](../wfsource/source/physics/physical.hpi):37-82 asserts that the colSpace expansion delta (`max - unExpMax` or `min - unExpMin`) equals `PredictedPosition() - Position()`. The two quantities are the same delta in algebra, but computed by different float subtractions: `predictedMotionVector` is a fresh `PredictedPosition() - Position()`, while `expansionVector` is the round-trip `(origMax + delta) - origMax`. With `Scalar == SCALAR_TYPE_FLOAT` (the PC dev configuration), `A + B - A != B` exactly for `B` of small magnitude relative to `A`; with A ≈ 8 and B ≈ -5, the last ULP shifts ~5e-7 between the two computations. `Vector3::operator==` is strict bit-equality, so the assert fires.

**Why dormant:** On a **fixed-point** `Scalar` target (the real-target build per [[project_mailboxes_fixed_point]]) the two computations are bit-identical and the assert never fires — the strict-equality check is correct there. The bug is float-mode-only. PC dev (where Scalar is float) has always had this drift, but `Validate()` is only called in certain tick paths and the false positive requires the specific magnitude ratio that produces a >0-ULP-difference subtraction; gameplay rarely hit it. Surfaced reliably only when the qbert cam intro pan generated the exact coordinate magnitudes the round-trip drifts on. The 2010-vintage strict-equality check has been shipping ULP false-positive risk for the entire history of the float-mode PC dev build.

**Fix:** [`physical.hpi`](../wfsource/source/physics/physical.hpi):69 — replace `expansionVector == predictedMotionVector` with a per-axis `(a - b).Abs() < Scalar::FromDouble(1e-3)` tolerance check. Threshold is well above float drift (a few ULPs of the largest operand ≈ 1e-3 worst case at game-world coordinates) and well below any physically meaningful inaccuracy. No-op for fixed-point Scalar targets where the original strict comparison was always exact. `Vector3::operator==` deliberately untouched — lots of code uses exact equality for legitimate reasons (`v == Vector3::zero`).

**Investigation:** [`docs/plans/2026-05-11-physical-validate-float-tolerance.md`](plans/2026-05-11-physical-validate-float-tolerance.md).

---

## `iff2lvl` wrote uninitialized `Euler` into `_PathOnDisk.base.rot` — 2026-04-19

**Status:** OPEN in `wftools/iff2lvl/` (oracle-only, frozen); mirrored as a literal-byte constant in `levcomp-rs` pending the round-trip verification step that flips to zeros — see [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md) §Verification plan.

**Symptom:** Snowgoons' compiled `.lvl` contains 8 bytes (`b1 02 85 c6 00 00 20 4f`) in the single `_PathOnDisk` record's `base.rot` field that no straight reading of `QPath::Save` accounts for. The bytes are deterministic across re-runs of the oracle pipeline but don't match what the code appears to write (zeros).

**Root cause:** `QPath::Save` in [`wftools/iff2lvl/path.cc`](../wftools/iff2lvl/path.cc):268 declares `Euler rotEuler;` as a local — where `Euler` resolves to the constructor-less POD `typedef struct { float a,b,c; } Euler;` from [`wftools/iff2lvl/global.hp`](../wftools/iff2lvl/global.hp):68, **not** the proper class-Euler with a zero-initializing `ConstructIdentity()` default ctor in [`wftools/iff2lvl/euler.hp`](../wftools/iff2lvl/euler.hp). The class-Euler header is tombstoned by an unconditional `#error !!` at [`euler.hp`](../wftools/iff2lvl/euler.hp):8 — but that tripwire sits *inside* the `#ifndef _EULER_HPP / #define _EULER_HPP` guard and only fires if some TU `#include`s the header. `path.cc` never does: it includes `global.hp`, picks up the typedef silently, and the `#error` guarding the wrong file does nothing. Default-initialization of the POD leaves the three floats *indeterminate*; `WF_FLOAT_TO_SCALAR(rotEuler.a)` then runs `(int32)(garbage_float * 65536.0f)` and narrows the result into a `u16` for each axis. The surrounding `_PathOnDisk` was itself allocated via `new char[SizeOfOnDisk()]`, which leaves `.order` and `.pad` as raw heap bytes. All 8 bytes of `base.rot` are uninitialized memory; the class's own `QPath::baseRotation` (a `Quat` correctly defaulted to identity) is never consulted because the Quat→Euler conversion in `QPath::AddRotationKey` was stubbed `assert(0)` and never written. (Tangential preprocessor red flag in the same family: `wftools/iff2lvl/euler.hp` guards on `_EULER_HPP` while [`wfsource/source/math/euler.hp`](../wfsource/source/math/euler.hp):23 guards on `_EULER_HP` — one P apart; close enough to invite manual collision, distinct enough that the macros don't actually clash.)

**Why dormant:** For relative/hierarchical paths the runtime overwrites `_baseRot` every frame from the parent object's live rotation ([`wfsource/source/movement/movepath.cc`](../wfsource/source/movement/movepath.cc):109), so the saved garbage is clobbered before first use. For absolute paths (snowgoons' single `snowman01`) `_baseRot` *is* added to every sampled rotation, but the per-channel rotation channels authored for snowman01 produce visually correct motion regardless of the small offset — short path, low-res visuals, no second reference to compare against. The bug shipped undetected from 1995–2010 because nothing in the WF pipeline ever read these bytes meaningfully. Surfaced now only because `levcomp-rs` was diffing the oracle byte-for-byte.

**Fix:** `levcomp-rs` currently emits the 8-byte oracle constant verbatim (mirror-first); the planned flip to zeros plus a soak diff drops the literal once the round-trip is fully working. The iff2lvl side isn't being patched — the tool is oracle-only — but a correct rewrite would (a) make `Euler` a real class with a zero-initializing default ctor and a `Validate()`, (b) route `Save` through `baseRotation` with a real Quat→Euler conversion, and (c) zero-init the `_PathOnDisk` allocation. Investigation also notes this is exactly the bug class WF's `codingstandards.txt` was written to prevent (no public data, canonical form, `Validate()` on ctor exit) — all three skipped on the tools side.

**Investigation:** [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md).

---

## `iff2lvl` left `_RoomOnDisk` pad bytes uninitialized — 2026-04-19

**Status:** OPEN in `wftools/iff2lvl/` (oracle-only, frozen); `levcomp-rs` zero-fills and accepts the constant-width drift per the explicit "indeterminate heap bytes" carve-out of [[feedback_oracle_mirror_first]].

**Symptom:** Three bytes in snowgoons' compiled `.lvl` `_RoomOnDisk` records refused to match between the oracle and `levcomp-rs` zero-fill output, with no source-level explanation: Room 0 trailing-entries pad = `01 00` (Rust emits `00 00`); Room 1 struct-header pad = `0B 08` (Rust emits `00 00`). Witnessed in `wftools/levcomp-rs/.../rooms.rs:61-65`.

**Root cause:** `iff2lvl` allocates each room via `new char[size]`, writes 34 bytes of fields into the `__attribute__((aligned(4)))` 36-byte `_RoomOnDisk` footprint, and never zeroes either (a) the 2-byte struct-header pad that the aligned attribute inserts, or (b) the trailing-entries pad that brings `36 + 2×count` up to the next 4-byte boundary. C++'s `new char[size]` is default-init for `char` → indeterminate; the C allocator hands back whatever bytes happened to be in the bucket. Same class of bug as the `_PathOnDisk.base.rot` Euler garbage — uninitialized heap, deterministic within one run because the short-lived plugin's allocator state is reproducible.

**Why dormant:** The runtime doesn't read these pad bytes — they exist purely because of the `aligned(4)` struct attribute and the per-room trailing alignment. The bytes have been shipping in every compiled WF level since 1995 with zero functional impact. Surfaced only when `levcomp-rs` started byte-diffing against the oracle, because Rust's `Vec::extend_from_slice` zero-fills where C's `new char[]` doesn't.

**Fix:** `levcomp-rs` zero-fills (the explicit "indeterminate heap bytes" exception to `mirror-oracle-first`); the constant-width 3-byte drift is documented and accepted because mirroring the iff2lvl allocator state exactly is infeasible. The iff2lvl side isn't being patched. Investigation also flags `_ObjectOnDisk`'s post-type-field pad as a third candidate site already mirrored "luckily" because iff2lvl always pulls the same allocator bin for object zero — worth auditing if future byte-identity work turns up unexplained diffs in other on-disk structs.

**Investigation:** [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md) §"Not the only uninit-heap site: the `_RoomOnDisk` pad bytes are the same pattern".

---

## COLLISION/SPECIAL_COLLISION message truncated colliding-object pointer to `int32` — 2026-04-17

**Status:** FIXED `06373f5` — `fix(baseobject): COLLISION msg carries full pointer, not truncated int32`.

**Symptom:** Surfaced as a 64-bit Android (arm64) build crash in collision handlers: `SPECIAL_COLLISION` receivers in `enemy.cc` / `explode.cc` / `missile.cc` read 4 bytes out of a buffer holding a truncated pointer, cast to `Actor*`, and dereferenced garbage. 32-bit builds (Linux x86, the historical primary target) worked fine.

**Root cause:** [`wfsource/source/baseobject/msgport.hp`](../wfsource/source/baseobject/msgport.hp)'s `SMsg::_data` union was sized for a 4-byte payload (`int32 _message` / `char binary[sizeof(Scalar)] = 4`). [`wfsource/source/physics/collision.cc`](../wfsource/source/physics/collision.cc):222's `DispatchCollisionMessages` passes the colliding object's address as message data via `object1.sendMsg( msg1, int32(&object2) )`. On 32-bit the `int32` cast is a no-op identity; on 64-bit it silently truncates the high 32 bits of the pointer. Receivers then read 4 bytes back, cast to `Actor*` — on 32-bit, a valid object pointer; on 64-bit, a half-pointer that overflows the receive buffer and points into nonsense. COLLISION receivers that discard the data (`movement.cc`, `movepath.cc`, `movefoll.cc`, `movecam.cc`) silently swallowed the broken payload either way.

**Why dormant:** WF shipped 32-bit on every released target — original-target hardware was 32-bit, PSX/PS2 were 32-bit, Linux/Windows dev was 32-bit. `int32`-as-pointer-handle was a correctness-by-coincidence pattern that "worked anyway" because `sizeof(int32) == sizeof(void*)` held on every platform the engine had ever been built for. The 2010-vintage code has carried this latent UB for 15+ years. Adding a 64-bit target (Android arm64, 2026) was the first build where the platform invariant broke — and it broke immediately and loudly in collision dispatch.

**Fix:** Widen `SMsg::_data._message` from `int32` to `uintptr_t` and resize the `binary[]` companion to `sizeof(uintptr_t)`; propagate the type change through `PutMsg` / `sendMsg` signatures in [`msgport.hp`](../wfsource/source/baseobject/msgport.hp) + [`msgport.cc`](../wfsource/source/baseobject/msgport.cc) + [`baseobject.hp`](../wfsource/source/baseobject/baseobject.hp) + [`baseobject.cc`](../wfsource/source/baseobject/baseobject.cc); replace the truncating `int32(&object)` cast in collision.cc with `reinterpret_cast<uintptr_t>(&object)`; update receivers in `enemy.cc` / `explode.cc` / `missile.cc` to read `*(uintptr_t*)msgData`. Small-integer senders (`DELTA_HEALTH`, etc.) still work — they implicitly widen on send, and `*(int32*)msgData` on receive reads the low 4 bytes (little-endian) which equal the original value.

**Investigation:** [`docs/plans/2026-04-17-collision-message-pointer-fix.md`](plans/2026-04-17-collision-message-pointer-fix.md).

---

## `BungeeCameraHandler` / `SPECIAL_COLLISION` reinterpret_cast type confusion — 2026-04-14

**Status:** OPEN — bypassed by the in-progress physics-engine replacement (Jolt, [`project_jolt_physics_functional`]).

**Symptom:** Lua spike (multi-script-engine development) immediately hit a segfault in `movecam.cc:1007`; bisection showed a `reinterpret_cast` from `BungeeCameraHandler*` to `Actor*` (or similar) where the underlying object layout doesn't match.

**Root cause:** Hand-rolled vtable-style dispatch in old physics code uses `reinterpret_cast` between unrelated class hierarchies. Worked in practice because the receiving function only read fields that happened to be at compatible offsets in the original layouts; new code that added members to one side broke the assumption.

**Why dormant:** The crash only fires when SPECIAL_COLLISION dispatch hits a code path that touches the post-misaligned fields. Snowgoons' geometry happened to avoid that combination.

**Fix:** Wholesale replace the physics layer ([`project_followup_replace_physics`]) — Jolt is the chosen replacement, currently parity-tested on snowgoons ([`project_jolt_physics_functional`]).

---

## Template

```
## <Title with what failed> — YYYY-MM-DD

**Status:** FIXED `<sha>` | OPEN | INVESTIGATING

**Symptom:** What the user (or a test) sees.
**Root cause:** What's actually wrong, with file:line citations.
**Why dormant:** Which exercise path was missing, or what masked it.
**Fix:** Minimal description; link the commit / plan.
**Investigation:** Link to docs/investigations/<date>-<slug>.md if there was one.
```
