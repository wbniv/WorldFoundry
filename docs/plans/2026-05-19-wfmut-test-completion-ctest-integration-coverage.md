# Plan — wfmut test completion (CTest integration + coverage)

**Date:** 2026-05-19
**Status:** DONE (commit `b44601f1`) — wfmut smoke + bridge regression tests registered with CTest.
**Parent:** [docs/plans/2026-05-19-engine-mutation-api.md](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-engine-mutation-api.md) (the mutation API itself — **Done**; full Test matrix definitions live there). This plan finishes that plan's deferred test work.

---

## Context

The engine mutation API (`wfmut::`) landed today: 24 in-process smoke cases (`engine/mutation/wfmut_smoke.cpp`, driven by `wf-edit --wfmut-smoke`) + 8 live-bridge regression cases (`tests/verify_wfmut_bridge.py`) all pass. **But the suite has two gaps:**

1. **Integration gap** — neither the smoke nor the bridge regression is registered with CTest. They only run when I manually invoke them. The cycle-stability tests, by contrast, are `add_test()`-registered and run via `task test-cycle` (`CMakeLists.txt:692-735`). So nothing gates wfmut in CI.
2. **Coverage gap** — roughly half the [Test matrix](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-engine-mutation-api.md#test-matrix) is deferred: T5/T7/T8/T10, F13, happy-path spawn SR1/2/7/8/10 (+ SR3/4/5/9/12/13/14), M2/M3/M4/M6/M7/M8, X1/X2/X4/X5.

The user asked for **both**: wire the existing tests into CTest/CI *and* expand coverage, leaving wfmut with a complete, CI-gated suite.

Three findings from exploration shape the work:

- **Mailbox out-of-range writes fall through to the parent (global) bank** — `MailboxesWithStorage::ReadMailbox`/`WriteMailbox` (`wfsource/source/mailbox/mailbox.cc:79,96`) route to `_parent` when the index isn't local; they do **not** reject. So M4/M8 must *pin the actual fall-through behaviour*, not assume `false`.
- **`GLOBAL_USER_MAX` is now 1900** (bumped from 999 on 2026-05-09, `mailbox.inc:32`). The [project_followup_mailbox_999_crash](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md) memory is **stale** — M8's "999 aborts" premise needs re-verification at the new boundary, and the memory needs updating.
- **Runtime spawn aborts** on a direct `SpawnActor(coin, player-pos, vel=0)` but the engine's `Generator` spawns the same coin fine with an offset position + Z-velocity (`generator.cc:105-111`). Likely a collision-overlap path; retry with generator-like params before deferring.

---

## Approach

Six steps. Each is its own commit per [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md). Steps 1–2 are the high-value core (integration + cheap coverage); 3–5 add the harder cases; 6 is docs.

### 1. CTest + CI integration

The CMake-built `wf_game` (default `WF_DEBUG_BRIDGE=ON`) already carries `--wfmut-smoke` because wfmut sits at the bridge∪editor union. The smoke exits nonzero on failure (`std::_Exit(failures)` in `main.cc`), and `verify_wfmut_bridge.py` exits nonzero too — both are already CI-shaped.

- **CMakeLists.txt** (inside the existing `enable_testing()` block, ~line 700): register two entries mirroring the cycle-test pattern —
  - `wfmut_smoke`: `COMMAND $<TARGET_FILE:wf_game> -L${SMB_STANDALONE} --wfmut-smoke`, `WORKING_DIRECTORY ${WF_TEST_RUN_DIR}`, `LABELS "gl"`, `ENVIRONMENT "DISPLAY=:0"`. New `set(WF_TEST_SMB_LEVEL .../wflevels/smb_w1_1-standalone.iff)`.
  - `wfmut_bridge`: `COMMAND ${Python3_EXECUTABLE-python3} ${CMAKE_SOURCE_DIR}/tests/verify_wfmut_bridge.py`, `LABELS "gl"`, `ENVIRONMENT "DISPLAY=:0"`. (It launches its own `wf_game` subprocess + needs the binary built first — note this; the bridge script already points at `engine/wf_game`.)
- **Taskfile.yml**: add `test-wfmut` → `cd cmake-build-linux && ctest --output-on-failure -R "wfmut"`. Both are `gl`-labelled so `ctest -LE gl` (headless CI) still skips them, consistent with the host-GL tests.
- **Verify:** `task build-cmake && task test-wfmut` → `wfmut_smoke` + `wfmut_bridge` both green.

### 2. Cheap coverage wins (`engine/mutation/wfmut_smoke.cpp`)

No new fixtures needed; each is a few lines in the existing runner.

- **T5** — iterate `1..Size()` for a `GetObject(i)` that is non-null but `dynamic_cast<Actor*>` fails; if found, assert `SetActorPos→false` + lastError "is not an Actor". If smb has none, emit `[SKIP]` with a note.
- **T7** — after `SetActorPos(player, P)`, read the Jolt position back via `JoltCharacterGetPosition`/`JoltBodyGetPosition` (`jolt_backend.hp:48,111`) using the player's `JoltCharacterID()`/`JoltBodyID()`, assert it matches P. Confirms the Jolt sync `setCurrentPos` does.
- **T8** — `SetActorPos` with `NaN`/`+Inf` components → assert it returns `true` (write reached the actor) and the call itself doesn't crash; restore immediately. Document "don't do this" (engine may destabilize on the next physics step).
- **T10** — `SetActorOrientation` at rev=1.0 → read back, assert wraparound to ~0.0 (`Angle` is mod-1 revolutions).
- **M3** — `SetMailbox` at a mid-high *local* slot (e.g. 20) → round-trips.
- **M4** — `SetMailbox` past the actor's local count → **pin the actual fall-through-to-parent behaviour** (write + read-back round-trips through the global bank; not a rejection). Assert no crash + document.
- **M7** — `SetMailbox` with `NaN`/`Inf` value → document (round-trips the bit pattern or clamps; pin whichever).
- **M8** — `Set/GetMailbox` at the **current** `GLOBAL_USER_MAX` (1900) and 1899 → pin behaviour. If the off-by-one still aborts at the new max, that's a live bug → log to TODO.md + update the stale memory; if it's fixed by the bump, note that too.
- **X1/X2** — after a failing call then a succeeding call, assert `lastError()` is non-empty then `""`; never returns nullptr.

### 3. Cross-thread guard (X5) — implement + death-test

The API design promised a debug-build guard but it was never built. Implement it in `wfmut.cpp`:
- A file-scope `static std::thread::id g_gameThread` captured on the first wfmut entry (under a tiny first-call helper). On every subsequent entry, in `DO_ASSERTIONS` builds, `AssertMsg(std::this_thread::get_id() == g_gameThread, "wfmut must be called on the game thread")`. Zero release overhead (compiled out when assertions are off). Single shared check called at the top of each public function (fold into `resolve_actor` + the no-actor entry points).
- **Test:** a death-test — small path in the smoke (`--wfmut-thread-test` flag, or a dedicated tiny harness) that spawns a `std::thread` calling `wfmut::SetActorPos` and confirms the process aborts with the expected message. CTest supports this via `set_tests_properties(... PROPERTIES WILL_FAIL TRUE PASS_REGULAR_EXPRESSION "game thread")`. If a clean death-test proves fiddly, ship the guard + a manual-verification note and defer the automated death-test.

### 4. ASan sweep (X4)

- Build the editor/bridge config under `-DWF_ASAN=ON` (the repo has `task build-asan` → `cmake-build-asan`), run `wf_game --wfmut-smoke -L<smb-standalone>`, confirm zero ASan/UBSan reports. Add a `task test-wfmut-asan` convenience target (build-asan + run the smoke) and document it as the pre-merge gate. (Not a default CTest entry — ASan lives in its own build dir, matching how the repo treats ASan today.)

### 5. Happy-path spawn (SR1/SR2/SR7/SR8/SR10) — time-boxed

**The abort is documented** ([level-design-troubleshooting.md §569, §1035, §1081](/home/will/WorldFoundry.2026-new-level/docs/level-design-troubleshooting.md)), not a mystery — three distinct outcomes:
- **Collision overlap at spawn (§1035)** → `ConstructTemplateObject` returns **NULL**, which `wfmut::SpawnActor` already turns into `std::nullopt`. *Not* the abort. Author rule: spawn must clear the nearest collidable by ≥ the template's half-extent (coin half-Z = 0.3 → ≥ 1.0 m clearance).
- **`HasRunPredictPosition` assert (§1081, `actor.cc:869`)** → the "terminate called without an active exception" message (downstream of `_sys_assert → exit → joinable std::thread dtor`). **Already fixed** in `Level::AddObject` by commit `0adf1d4` (`HasRunPredictPosition(true)` + `HasRunUpdate(true)` on the new actor), so a spawned actor parks for one tick and enters the normal pipeline next frame.
- **Position not strictly inside a room (§569)** → "not in any room" → terminate at add/containment time.

So the earlier failure was almost certainly spawning **on top of the player at rest** (collision/boundary), not a fundamental block. Revised approach:
- Spawn the coin template (first `HasTemplate` hit, idx 2 in smb) at a position **strictly inside the player's room, offset to clear colliders by ≥ 1.0 m** (e.g. player-pos with a clear +Z and away from the ground/block), small velocity optional. Use `generator.cc:105-111` as the working reference for safe params.
- If clean: SR1 (returns idx + same-frame `GetActorPos`), SR2 (`GetObject(newIdx)->GetActorIndex()==newIdx`), SR7 (readable before frame step), SR8 (gone after `level.update(dt)` — relies on `0adf1d4`'s AddObject fix to not assert), SR10 (double-remove no crash).
- Only if it *still* aborts after a clean in-room, collider-clear position: file the bug in [docs/BUGS.md](/home/will/WorldFoundry.2026-new-level/docs/BUGS.md) + TODO.md with the repro and keep SR1/2/7/8/10 deferred. **Cap at ~30 min** — the groundwork above should make it pass.

### 6. Defer-with-rationale + docs

- Keep deferred with one-line rationales in the smoke: **F13** (no two smb actors share a `_Common` page), **M2** (slot-0 = LOCAL_SYSTEM side effects), **M6** (no mailbox-less actor in smb), **SR3/4/5/9/12/13/14** (parent variants / stale-idx / ASan-stress / identity / re-entrancy — need scripts or fixtures not present).
- Update the [parent plan](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-engine-mutation-api.md) Test matrix: mark each case **PASS** / **DEFERRED (reason)** / **PINNED**.
- [wf-status.md](/home/will/WorldFoundry.2026-new-level/wf-status.md): one-line note that wfmut tests are now CTest-gated + coverage count (24 → ~32+).
- Update [project_followup_mailbox_999_crash](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md) memory with the 999→1900 boundary move + whatever M8 pins.

---

## Critical files

- **Modify** `engine/mutation/wfmut_smoke.cpp` — new cases (T5/T7/T8/T10, M3/M4/M7/M8, X1/X2), happy-path spawn (step 5), thread death-test path (step 3).
- **Modify** `engine/mutation/wfmut.cpp` — cross-thread guard (step 3).
- **Modify** `CMakeLists.txt` — `wfmut_smoke` + `wfmut_bridge` CTest entries + optional `WILL_FAIL` thread death-test.
- **Modify** `Taskfile.yml` — `test-wfmut`, `test-wfmut-asan`.
- **Modify** `docs/plans/2026-05-19-engine-mutation-api.md` — matrix status; `wf-status.md`; `docs/BUGS.md`/`TODO.md` if spawn stays blocked.
- **Read (no edits):** `wfsource/source/mailbox/mailbox.cc` (fall-through), `wfsource/source/physics/jolt/jolt_backend.hp` (getters), `wfsource/source/game/generator.cc` (safe-spawn params), `CMakeLists.txt:692-735` (CTest pattern).

## Verification

1. `task build-cmake && task test-wfmut` → `wfmut_smoke` + `wfmut_bridge` green via CTest.
2. Smoke case count rises from 24 to ~32+ (new T/M/X cases), still 0 failures on `wf-edit --wfmut-smoke -Lwflevels/smb_w1_1-standalone.iff`.
3. `task test-wfmut-asan` → smoke runs ASan-clean.
4. Cross-thread death-test aborts with the expected message (CTest `WILL_FAIL`/`PASS_REGULAR_EXPRESSION`), or documented manual proof.
5. `ctest -LE gl` still excludes the wfmut tests (headless-safe), consistent with the host-GL suite.

## Out of scope

- Standalone `wfmut_test.cc` executable linking `libwfengine.a` (à la `wfcrdt_wrapper_test`). The embedded `--wfmut-smoke` flag already gives a CI-gateable entry without the engine-init boilerplate a free-standing harness needs; revisit only if we want wfmut tests to run without a GL context.
- COW / multi-level / DAP / CRDT-bridge integration tests — tracked in the parent plan's out-of-scope list.
