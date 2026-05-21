---
name: World Foundry engine project context
description: 3D World Foundry engine being modernized; scripting is being converted from legacy Scheme `.s` files to zForth; build pipeline is Blender→.lev→.iff via Rust tools.
type: project
originSessionId: 1bb8f4e2-9146-4504-8289-793c96be779b
---
World Foundry is a late-1990s 3D game engine being actively modernized in 2026 (legacy GL → modern OpenGL 3.3+ GLSL, custom physics → Jolt, single-script → router-dispatched scripting with Lua/zForth/Fennel/QuickJS/WAMR).

**Scripting language conversion is in flight.** The legacy `.s` files (`wflevels/cart.s`, `fury1.s`, `dumbfury.s`, `xyzrotate.s`, `shell.s`) are Lisp/Scheme dialect — pre-conversion samples. The post-conversion canonical path is **zForth** (sigil `\ wf`):
- Snowgoons (`wflevels/snowgoons-blender/snowgoons.lev`) embeds Forth Script blocks (e.g. `INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox`).
- Engine shell is `wfsource/source/game/shell.fth`.
- Level shell is `wflevels/shell.aib` (Forth) — `wflevels/shell.s` is the legacy Scheme version still on disk.
- `scripts/patch_shell_forth.py` exists to migrate.
- zForth plug at `engine/stubs/scripting_zforth.cc` ships `read-mailbox` / `write-mailbox` bridge words and pre-loads all `mailbox.def` symbols as zForth `constant`s.
- Bubba / Minecart / Babylon5 still ship Scheme `.s` files; conversion not yet complete.

**Current branch/work focus:** `party-games-platform` is a parallel branch for a different effort (cast-based couch party game, see `project_party_games.md`). The engine modernization happens elsewhere; new game work is on its own feature branch.

**Room graph — what it actually is:** "Rooms" are not literal rooms; they are named zones that partition the world. The mechanism was designed to manage **CD asset streaming** — as the player moves through a level, assets (geometry, textures, scripts, audio) are loaded and unloaded zone-by-zone against a streaming budget. The room/zone graph is the designer-controlled handle on that streaming. Camera rigs and actor scoping attach per-zone as a consequence of authoring, not as the primary purpose.

**Why this matters for me:** Don't take any single example as canonical. Always check multiple files (`.s`, `.aib`, `.fth`, `.lev`-embedded) before claiming "this is how WF scripts are written."

**No established Forth-script conventions yet.** Snowgoons has two one-liners; the engine shell has `shell.fth`. That's the entire corpus. When writing new Forth game scripts, design the style fresh; don't hallucinate prevailing patterns. Reasonable defaults: kebab-case word names, predicate words ending in `?`, ANS Forth `if/else/then` (zForth supports both `fi` and `then`; snowgoons uses `then`), `MB_*` prefix for user-defined mailbox slots, `SFX_*` prefix for sound IDs.

**zForth gotchas (verified in `engine/stubs/scripting_zforth.cc` and `engine/vendor/zforth-41db72d1/src/zforth/zforth.c`):**
- **`constant` is broken at runtime** in the embedding model (see comment block at scripting_zforth.cc:244). Use `: NAME VALUE ;` instead — that's how `AddConstantArray` registers `INDEXOF_*` constants too.
- **`negate` and `abs` aren't defined.** kCoreBootstrap stops at `<`, `>`, `<=`, `>=`, `<>`, `0<>`, `not`, `over`, `1+`, `1-`. Define negate/abs yourself: `: negate 0.0 swap - ; : abs dup 0 < if negate then ;`.
- **Mailbox names ship as `INDEXOF_<NAME>`** (e.g. `INDEXOF_HARDWARE_JOYSTICK1_RAW`, `INDEXOF_X_POS`), not the bare names from `mailbox.def`. Bridge words: `read-mailbox ( idx -- val )`, `write-mailbox ( val idx -- )`.
- **Cross-actor mailbox reads aren't exposed yet.** Single-arg `read-mailbox` only operates on the current actor (`g_curObj`). Lua plug exposes a 2-arg form; Forth parity (`read-mailbox-of`, `write-mailbox-of` as ZF_SYSCALL_USER+2/+3) is ~30 LOC and a known TODO.
- **Per-script compile cache by src pointer.** Definitions in any actor's Script field persist globally in the dictionary; call bodies are wrapped in `_wfsN` words and cached. Definitions in one Script are callable from another — but execution order matters, so put definitions in an actor that runs first (Director / Level / a hidden boot actor) or pre-load via engine init.
