---
name: World Foundry engine project context
description: 3D World Foundry engine being modernized; level scripting is zForth (the legacy Scheme `.s` level scripts are gone); build pipeline is Blender→.lev→.iff via Rust tools.
type: project
originSessionId: 1bb8f4e2-9146-4504-8289-793c96be779b
---
World Foundry is a late-1990s 3D game engine being actively modernized in 2026 (legacy GL → modern OpenGL 3.3+ GLSL, custom physics → Jolt, single-script → router-dispatched scripting with Lua/zForth/Fennel/QuickJS/WAMR).

**Level scripting is zForth.** No Scheme `.s` level scripts remain (checked 2026‑11‑14: the only `.s` files left are OAS sources under `wfsource/source/oas/`). The canonical path is **zForth** (sigil `\ wf`):
- Snowgoons (`wflevels/snowgoons-blender/snowgoons.lev`) embeds Forth Script blocks (e.g. `INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox`).
- Engine shell is `wfsource/source/game/shell.fth`.
- Level shell is `wflevels/shell.aib` (Forth).
- `scripts/patch_shell_forth.py` exists to migrate.
- zForth plug at `engine/stubs/scripting_zforth.cc` ships `read-mailbox` / `write-mailbox` bridge words and pre-loads all `mailbox.def` symbols as zForth `constant`s.

**Current branch/work focus:** `party-games-platform` is a parallel branch for a different effort (cast-based couch party game, see `project_party_games.md`). The engine modernization happens elsewhere; new game work is on its own feature branch.

**Room graph — what it actually is:** "Rooms" are not literal rooms; they are named zones that partition the world. The mechanism was designed to manage **CD asset streaming** — as the player moves through a level, assets (geometry, textures, scripts, audio) are loaded and unloaded zone-by-zone against a streaming budget. The room/zone graph is the designer-controlled handle on that streaming. Camera rigs and actor scoping attach per-zone as a consequence of authoring, not as the primary purpose.

**Why this matters for me:** Don't take any single example as canonical. Always check multiple files (`.s`, `.aib`, `.fth`, `.lev`-embedded) before claiming "this is how WF scripts are written."

**Forth corpus is now large** (2026‑11‑14: 33 `.fth` files under `wflevels/`, plus Script blocks in 42 `.lev` files). Read an existing level's scripts and `docs/level-building.md` before inventing a style. Reasonable defaults: kebab-case word names, predicate words ending in `?`, ANS Forth `if/else/then` (zForth supports both `fi` and `then`; snowgoons uses `then`), `MB_*` prefix for user-defined mailbox slots, `SFX_*` prefix for sound IDs.

**zForth gotchas (verified in `engine/stubs/scripting_zforth.cc` and `engine/vendor/zforth-41db72d1/src/zforth/zforth.c`):**
- **`constant` is broken at runtime** in the embedding model (see comment block at scripting_zforth.cc:244). Use `: NAME VALUE ;` instead — that's how `AddConstantArray` registers `INDEXOF_*` constants too.
- **`negate` and `abs` are defined** in kCoreBootstrap since 2026‑06‑02 (`369d2ef8`, standard ANS CORE words); don't redefine them.
- **Mailbox names ship as `INDEXOF_<NAME>`** (e.g. `INDEXOF_HARDWARE_JOYSTICK1_RAW`, `INDEXOF_X_POS`), not the bare names from `mailbox.def`. Bridge words: `read-mailbox ( idx -- val )`, `write-mailbox ( val idx -- )`.
- **Cross-actor mailboxes:** `read-mailbox` / `write-mailbox` act on the current actor (`g_curObj`); `write-actor-mailbox ( val idx actor_idx -- )` (since 2026‑05‑10) and `read-actor-mailbox ( idx actor_idx -- val )` reach any actor.
- **Per-script compile cache by src pointer.** Definitions in any actor's Script field persist globally in the dictionary; call bodies are wrapped in `_wfsN` words and cached. Definitions in one Script are callable from another — but execution order matters, so put definitions in an actor that runs first (Director / Level / a hidden boot actor) or pre-load via engine init.
