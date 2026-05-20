# Plan — Runtime `long` audit (PSX/x86-32 → LP64 width hardening)

**Date:** 2026-05-20
**Status:** **Acked (Will: "yes do that"). Implementing.**
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

WF started on **PSX (MIPS)** and **x86-32**, where `long` == 32 bits == `int32`. On **LP64** (x86-64 Linux / modern Android) `long` is 64 bits, so every WF-authored bare `long` that *meant* a 32-bit value is a latent width bug. Surfaced 2026-05-20 while building the editor's OAD reader: `oad.h`'s `_oadHeader` `long`s made the C++ `oaddump` reader misread `.oad` files on x86-64 (the Rust `wf_oad` reads field-by-field, so it's correct). Spot-fixes already landed piecemeal (`ba3bbcb` IFF chunk-size, `06373f5` COLLISION-msg pointer); this is the first **systematic** pass over `wfsource/source`.

Survey: ~240 `long` lines in runtime source. Most are **permitted** or **already-safe**; a small set are genuine bugs.

### Permitted / already-safe (leave alone)
- **`scalar.cc`/`scalar.hpi` + `vector2.cc`/`vector3.cc`** — intentional 64-bit intermediates for 16.16 fixed-point math (`(long)a*(long)b>>16`), redone in 2026 with explicit "long is 64-bit on Linux x86-64" comments. (Arguably clearer as `int64_t`; low-priority style, not in scope.)
- **`pigsys.cc`** — `sys_fseek(long off)` etc. match the C stdio `ftell`/`fseek` signatures. Correct interop.
- **`pigtypes.h`** — `SYS_ULONG`/`SYS_LARGEINT` *are* `long` by definition; `SYS_INT32 signed long` only in the non-LP64 else-branch (the `__LINUX__`/`__ANDROID__` branch already uses `signed int`). Correct.
- **`particle.cc`** — `long` only inside `/* … */` min/max comments.
- **`oad.h` `FIXED32(n)` macro** — compile-time literal cast; harmless (could be `int32` for tidiness).

---

## Fixes

| # | Site | Change | Notes |
|---|---|---|---|
| F1 | **`oas/pigtool.h`** `SYS_INT32`/`SYS_UINT32` | Add the `__LINUX__`/`__ANDROID__` LP64 guard (use `signed int`/`unsigned int`), mirroring `pigtypes.h`; or `#include`/defer to `pigtypes.h`. | **Systemic root cause** — unguarded `signed long` makes `int32` 8 bytes in any Linux TU that pulls `pigtool.h` (via `oad.h`) before `pigtypes.h`; that's the measured `typeDescriptor` 1503-vs-1491 bloat (3× `int32` × +4). Dormant in the full engine build (include order), latent landmine otherwise. |
| F2 | **`oas/oad.h` `_oadHeader`** | `long chunkId/chunkSize/version` → `int32`/`uint32`. | Serialized 32-bit IFF header fields; the bug that bit the OAD reader. |
| F3 | **Mailbox API** — `mailbox/mailbox.hp`, `game/mailbox.{hp,cc}`, `actor.cc` `ActorMailboxes` | `ReadMailbox(long)`/`WriteMailbox(long,…)` params, `long _mailboxBase`/`numberOfLocalMailboxes` → `int32`. | Mailbox **indices** (small ints ≤999). Touches a **virtual** interface — change base + every override consistently (`Mailboxes`, `MailboxesWithStorage`, `LevelMailboxes`, `GameMailboxes`, `ActorMailboxes`) + callers. |
| F4 | **`game/movecam.cc`** | `long idxShot`/`shotIndex = …WholePart()` → `int32`. | Index locals. |
| F5 | **`gfx/color.hpi`** | `long temp` (8-bit colour add/sub) → `int`/`int32`. | 64-bit unnecessary; 32-bit ample. |
| F6 | **`actor.cc:1703`** `*(long*)msgData = 0` | **NOT `int32`** → `*(Actor**)msgData = nullptr` (pointer-width). | `msgData` holds an `Actor*` (cast + deref); `06373f5` made the COLLISION msg carry a full pointer. `int32` would re-truncate it. Pointer-width write preserves intent. |
| F7 | **`gfx/gl/wfprim.h`** PSX-GPU-primitive `long x,y,z`/`tag`/`code[]` | **TODO, don't fix here** — this PSX `psxRECT`/primitive path should not still be live; add a TODO to **remove the dead path** rather than re-typing its `long`s. | Per Will. |

---

## Verification
- Full engine build (`task build`, ASan-default) green; **snowgoons + qbert boot and run** (the mailbox virtual-signature change is the delicate part — confirm scripts still read/write mailboxes correctly). Screenshot.
- OAD reader: after F1+F2, `sizeof(typeDescriptor)` is **1491** in a standalone `oad.h` compile (matches on-disk stride); the editor reader (explicit offsets) is unaffected either way.
- NDK/Android build green (LP64 there too).

## BUGS.md
Add an entry (per [feedback_bugs_md_pre2026_only](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_bugs_md_pre2026_only.md) — these `long`s originate in the 1995–99 PSX/x86-32 code, pre-2026; verify originating commit via `git blame`): the PSX/x86-32 `long`==32 assumption breaking on LP64, the systemic `pigtool.h` `int32`-width landmine, and the per-site fixes (F1–F6) + the `wfprim.h` dead-path TODO (F7).

## Cross-references
- Triggered by [editor property-panel plan](2026-05-20-editor-property-panel.md) (OAD reader). Prior spot-fixes: `ba3bbcb`, `06373f5`, `a743515`.
- Memory: [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md), [feedback_bugs_md_pre2026_only](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_bugs_md_pre2026_only.md), [feedback_log_discoveries_in_todo](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md), [project_mailboxes_fixed_point](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_mailboxes_fixed_point.md).
