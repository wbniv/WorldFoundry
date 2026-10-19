# Runtime `long` audit — complete per-occurrence review

**Date:** 2026-05-20 · companion to [plan](../plans/2026-05-20-runtime-long-audit.md)

Exhaustive sweep of **every** `long` in the first-party tree (`wfsource/source` + `engine/`, excluding vendored libs), done by 5 parallel subagents. **~468 matched lines / ~220 real `long`-type uses (CODE)** across 5 areas. Reproduce any slice with:

```sh
grep -rnE '\blong\b' <dir> --include='*.cc' --include='*.cpp' --include='*.c' \
  --include='*.hp' --include='*.hpi' --include='*.hpp' --include='*.h' \
  --include='*.ht' --include='*.mm' --include='*.inc' --include='*.s'
```

| Area | lines | CODE | comment/string | generated `.ht` | `long long` |
|---|---|---|---|---|---|
| `math` + `gfx` | 169 | 148 | 21 | 0 | 0 |
| `game`/`baseobject`/`movement`/`anim` | 24 | 14 | 10 | 0 | 0 |
| `pigsys`/`hal`/`memory`/`cpplib`/… | 39 | 31 | 8 | 0 | 0 |
| `mailbox`/`oas`/`physics`/`particle`/… | 197 | 9 | 30 | 158 | 0 |
| `engine/` | 39 | 18 | 0 | 0 | 17 |

> My **first pass surveyed only `wfsource/source` with a crude filter and missed:** all of `engine/`, the 158 generated `.ht` occurrences, the `.s` codegen inputs, and several `gfx`/`game` files. The sweep corrected that.

**Legend:** ✅ CHANGED · ⚠️ FLAGGED (suspect, **not** changed yet) · ⚪ KEPT (permitted) · 🏭 GENERATED (in `.ht`, fix at the generator) · 💬 comment/string.

---

## ✅ CHANGED — verify these against the diff

**F1 `oas/pigtool.h`** — `SYS_INT32`/`SYS_UINT32 signed long` → `__LINUX__`/`__ANDROID__`-guarded `int`.
**F2 `oas/oad.h:110-113`** — `_oadHeader` `long chunkId/chunkSize/version` → `int32`.
**F3 mailbox-index API (full chain, incl. the engine + game-member callers the sweep caught):**
- `mailbox/mailbox.{hp,cc}`, `game/mailbox.{hp,cc}`, `game/actor.{hp,cc}` — `ReadMailbox/WriteMailbox(long)`, ctors, `_mailboxBase` → `int32`.
- `engine/mutation/wfmut.cpp:411,422` — `WriteMailbox/ReadMailbox(static_cast<long>(mailboxIndex))` → pass `mailboxIndex` (int→int32). *(missed in pass 1)*
- `engine/stubs/scripting_lua.cc:77,93` — `long mailbox = static_cast<long>(…)` → `int` (+ `%ld`→`%d`). *(missed in pass 1)*
- `game/level.hp:252-253` (`_camRollMailBox`/`_camShotMailBox`), `game/generator.hp:62` (`_generateMailBox`), `game/tool.hp:104` (`_objectToGenerate`) — `long` index members → `int32`. *(missed in pass 1)*

**F4 `game/movecam.cc:477,675,802,825,889,933`** — `long idxShot/shotIndex` → `int32`.
**F5 `gfx/color.hpi`** (10 sites) — `long temp`/`long(Red())` → `int`.
**F6 collision payload** — `game/actor.cc:1701,1703` + `game/warp.cc:113` — read the pointer via `*(uintptr_t*)msgData` (kept the pointer optimization, fixed the buffer-as-Actor mis-cast; invalidate at `uintptr_t` width).

---

## ⚠️ FLAGGED — now FIXED (pass 2, per Will) — verify in the diff

| File:line | Fix | Was |
|---|---|---|
| `renderassets/rendcrow.cc:155` | `sizeof(long)` → **`sizeof(int32)`** | live count-halving bug under `#if USE_ASSET_ID` (8 vs 4 on LP64). |
| `anim/anim.cc:160-161` | `long*`/`(long*)` → **`int32*`** | 4-byte-word copy was striding 8 bytes on LP64 → overrun/wrong span. |
| `gfx/gl/rendobj3.hp` **+** `gfx/glpipeline/rendobj3.hp` | `long flags/zflag/sz[3]/ir0[3]` → **`int32`** (both copies) | render struct bloat. |
| `gfx/pixelmap.cc:149` | `long unsigned int *` → **`uint32 *`** | vestigial (immediately recast to `uint16*`); harmless cosmetic. |
| `hal/sjoystic.h:113,150` | `typedef long` → **`typedef uint32`** | button bitmasks 64-bit on LP64. (21 consumers via the typedef.) |
| `memory/lmalloc.cc:58`, `realmalloc.cc:49` | `long _state` → **`int32`** | header field holds 32-bit codes (`'ALOC'`/`'FREE'`/canary), adjacent `_size` is `int`. |
| `anim/path.cc:153-155` | `long(…)` → **`int32(…)`** | 16.16 fixed-point full-circle constant. |
| `game/main.cc:287` | `long value` → **`int32 value`** | `atoi` local. |

**Reclassified as permitted after checking (NOT changed — would be a regression / are correct):**
- `memory/memory.hp:98` `long* count = ((long*)classptr)-1` — **correct, leave**. It reads the C++ **array-new cookie**, whose size is the platform word (4 on ILP32 / 8 on LP64); `long` tracks that, so `Free(count)` lands on the real base. `int32` would compute `classptr-4` on LP64 → free a wrong pointer (same trap as `actor.cc:1703`). *(Could be `size_t*` for clarity.)*
- `pigsys/pigtypes.h:58,67` / `oas/pigtool.h:65,77` `SYS_ULONG`/`SYS_LARGEINT = (unsigned) long` — **leave**. These *are* the "wide type" abstraction by name; their only consumers found are `ulong u/v` **computation locals** for texture-coord math (`rendgtp`/`rendgtl`/`display`/`rendmatt`/`rendftl`) — values fit, no 32-bit storage/serialization misuse. Not a width bug.
- `baseobject/commonblock.hpi:32` `((long)_commonBlockBase & 3)` pointer-alignment check — **correct, leave** (initially "fixed" to `uintptr_t`, then reverted). `long` is pointer-width on every ABI WF targets (ILP32 PSX/x86-32; LP64 Linux/Android/iOS), so the check works; `uintptr_t` would be cleaner but needs `<cstdint>` in this core header for zero behavioural gain.
- `gfx/camera.cc:100,126` — Scalar fixed-point round-trips through the `Scalar(long)` ctor / `AsLong()` API; permitted like the math core.
- `anim/animtest.cc:324` loop counter + the `long unsigned int* buffer[]` test framebuffers — test scaffolding (pointer arrays, width-neutral).

---

## ⚪ KEPT — permitted (correct/harmless; reproducible by file via the grep above)
- **Fixed-point 64-bit math intermediates** (intentional; `(long)a*(long)b>>16`, 2026 portable-C rework — `scalar.hpi` even comments "long is 64-bit on Linux x86-64"): `math/scalar.cc`, `math/scalar.hpi`, `math/scalar.hp`, `math/linux/scalar.{cc,hpi}`, `math/vector2.cc`, `math/vector3.cc`, `math/mathtest.cc` — ~140 CODE. *(Arguably clearer as `int64_t`; not bugs.)*
- **C-stdlib interop** (`long` is the standard signature): `pigsys/pigsys.cc`+`pigsys.hp` (`fseek`/`atol`/`strtol`/`strtoul`), `pigsys/scanf.cc` (`%l`), `pigsys/assert.hp` (`(int)(long)` truthiness), `engine/stubs/scripting_zforth.cc:172` (`strtol`), `scripting_pforth.cc` (`(long)r` for `%ld`).
- **Platform-width by definition:** `gfx/host_gl_context.h:40` `unsigned long win` (Xlib `XID`), `engine/wf_edit/main.cc:273` + `wf_host_gl_test/*` `(unsigned long)` X11 `Window` casts.
- **Wall-clock ticks** (64-bit intentional — `tv_sec*100` overflows int32 in ~248 days): `hal/time.{cc,hp}`.
- **Type-width definitions** (the `signed long` is the non-LP64 `#else` branch; Linux uses `int`): `pigsys/pigtypes.h:33,41`, `oas/pigtool.h:40,48`.
- **`long long` (intentional 64-bit, FFI):** `engine/crdt/*` (Yrs i64 ABI — 17 occurrences), `engine/stubs/debug_server.cc:86`, `engine/wf_edit/level_doc.cc:165`.
- **Test scaffolding:** `*test.cc` loop vars / framebuffers / hex prints.

## 🏭 GENERATED — `.ht` files (158 occurrences, all in `/* */` comments)
34 `.ht` files carry `long` only inside generated comments (the `"maximum/minimum value of a long int"` boilerplate + `FIXED32(N)` → `((long) N * 65536.0)` range annotations). **Root: the `FIXED32` macro in the codegen inputs** `oas/oadtypes.s:15`, `oas/oaddef.s:10`, `oas/types3ds.s:13` (`@define FIXED32(num) ((long) num * 65536.0)`). The cast is float arithmetic (numerically harmless), but any normalization belongs in those `.s` templates, never in the `.ht`. → TODO if we want it clean.

---

**Bottom line:** F1–F6 (now incl. the engine + game-member mailbox callers) are the *concentrated, fixed* bugs. The ⚠️ section is the honest "found but not yet changed" list — **`rendcrow.cc:155` (`sizeof(long)`), `anim.cc:160-161`, `pixelmap.cc:149`, `rendobj3.hp`×2, `sjoystic.h`, `memory/*`, the unconditional `SYS_ULONG`/`SYS_LARGEINT`** are the priorities. The ⚪/🏭 bulk is permitted or generated.
