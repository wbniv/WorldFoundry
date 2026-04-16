# Context

`wftools/wf_engine/` is the actual game engine executable — not a dev tool. It should not live alongside `iffcomp`, `iffdump`, and friends. Similarly, `wftools/vendor/` contains ~145 MB of scripting/physics/runtime libraries that are consumed **exclusively** by the engine build; nothing in `wftools/` itself uses them. The stubs and backend implementations in `wftools/wf_viewer/stubs/` and `wftools/wf_viewer/include/` are also engine-only code that ended up there for historical reasons (the viewer build predated the engine rewrite). Moving all of these to a top-level `engine/` directory makes the repo's intent clear at a glance: `wfsource/` = original source, `wftools/` = dev tools, `engine/` = the runnable game.

---

# Target Structure

```
WorldFoundry/
├── engine/
│   ├── build_game.sh        # moved from wftools/wf_engine/
│   ├── wf_game              # (gitignored binary)
│   ├── objs_game/           # (gitignored build artifacts)
│   ├── libs/                # shared .so stubs
│   ├── vendor/              # moved from wftools/vendor/  (~145 MB)
│   ├── stubs/               # moved from wftools/wf_viewer/stubs/
│   └── include/             # moved from wftools/wf_viewer/include/
├── wfsource/                # unchanged
├── wftools/
│   ├── wf_viewer/           # now only: viewer.cc, build.sh, wf_viewer binary
│   └── ... (iffcomp-rs, iffdump-rs, lvldump-rs, etc. — unchanged)
└── ...
```

---

# Steps

## 1. Create `engine/` and move engine artifacts

```bash
mkdir engine
git mv wftools/wf_engine/build_game.sh engine/build_game.sh
git mv wftools/wf_engine/PLAN.md       docs/plans/2026-04-engine-start-snowgoons-directly.md
git mv wftools/wf_engine/libs          engine/libs
# wf_game and objs_game/ are gitignored — move manually, not via git mv
mv wftools/wf_engine/wf_game    engine/wf_game   2>/dev/null || true
mv wftools/wf_engine/objs_game  engine/objs_game 2>/dev/null || true
rmdir wftools/wf_engine
```

## 2. Move vendor tree

```bash
git mv wftools/vendor engine/vendor
```

## 3. Move stubs and include from wf_viewer

```bash
git mv wftools/wf_viewer/stubs   engine/stubs
git mv wftools/wf_viewer/include engine/include
```

`wftools/wf_viewer/` now contains only `viewer.cc`, `build.sh`, and the `wf_viewer` binary — the viewer does not reference these directories.

## 4. Update `engine/build_game.sh` — 4 lines

File: `engine/build_game.sh`

| Variable | Old value | New value |
|---|---|---|
| `STUBS` | `$REPO_ROOT/wftools/wf_viewer/include` | `$REPO_ROOT/engine/include` |
| `STUB_SRC` | `$REPO_ROOT/wftools/wf_viewer/stubs` | `$REPO_ROOT/engine/stubs` |
| `VENDOR` | `$REPO_ROOT/wftools/vendor` | `$REPO_ROOT/engine/vendor` |
| comment line 5 (run path) | `wftools/wf_engine/wf_game` | `engine/wf_game` |

## 5. Update `.gitignore`

```
# old
wftools/wf_engine/objs_game/
# new
engine/objs_game/
```

## 6. Update `Taskfile.yml`

Replace all occurrences of `wftools/wf_engine` with `engine` (5 occurrences across build/run/gdb tasks).

## 7. Update docs (bulk text replacement)

There are ~45 doc files with path references. Four substitutions cover all cases:

| Find | Replace |
|---|---|
| `wftools/wf_engine` | `engine` |
| `wftools/vendor` | `engine/vendor` |
| `wf_viewer/stubs` | `engine/stubs` |
| `wf_viewer/include` | `engine/include` |

Files affected: `docs/**/*.md`, `wf-status.md`, `TODO.md`.

## 8. Update memory

Update project memory notes that reference old paths:
- `project_wf_game_build.md` — run path and stubs reference

---

# Files Modified

| File | Change |
|---|---|
| `engine/build_game.sh` | 4 path variable/comment updates |
| `docs/plans/2026-04-engine-start-snowgoons-directly.md` | moved from `wftools/wf_engine/PLAN.md` |
| `.gitignore` | 1 pattern update |
| `Taskfile.yml` | 5 path updates |
| `docs/**/*.md` (~45 files) | bulk text replacement (4 patterns) |
| `wf-status.md`, `TODO.md` | bulk text replacement |

---

# Verification

1. Build succeeds: `cd engine && bash build_game.sh` — should compile and produce `engine/wf_game`
2. Run succeeds: `cd wfsource/source/game && LD_LIBRARY_PATH=../../../engine/libs DISPLAY=:0 ../../../engine/wf_game` — snowgoons loads
3. Viewer still builds: `cd wftools/wf_viewer && bash build.sh` — should still work (no deps on moved dirs)
4. `git status` shows no untracked vendor/stubs/include files (all moves tracked by git)
