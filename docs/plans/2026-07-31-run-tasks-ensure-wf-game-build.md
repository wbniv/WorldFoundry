# Plan: Make every `wf_game` run task ensure a fresh binary

**Status:** Complete — implemented and dependency-path verified 2026-07-31;
desktop `task run-moon` launch confirmed by the user 2026-08-05.

## Context

The game runners invoke `engine/wf_game` directly. On a fresh checkout,
`task run-moon` therefore fails with `engine/wf_game: No such file or directory`
until the user separately runs `task build`. An existing but stale binary is
worse: the level starts successfully while silently omitting newer engine
changes.

`run-wf-edit` already expresses the desired interface by depending on its build
task. The `wf_game` runners should offer the same one-command workflow without
paying for a full build on every launch.

## Outcome

These commands build `wf_game` when necessary, then launch it:

```bash
task run
task run-level -- wflevels/snowgoons.iff
task run-moon
task run-debug -- wflevels/snowgoons.iff
```

When the binary is current, the added work is only three cheap filesystem
checks: an executable test, a build-script timestamp test, and a `find` that
stops at the first newer relevant input.

## New-computer quick start

The distributable bootstrap and run instructions now live in
[WorldFoundry Moon Level: New-Computer Quick Start](../moon-level-quickstart.md).

## Design

### 1. Add an `ensure-build` task

Add a private prerequisite-style task to `Taskfile.yml`:

```yaml
ensure-build:
  desc: "Build wf_game only when the binary is missing or older than engine sources"
  cmds:
    - task: build
  status:
    - test -x engine/wf_game
    - test engine/build_game.sh -ot engine/wf_game
    - test -z "$(find engine wfsource/source ... -newer engine/wf_game -print -quit)"
```

Go Task skips `cmds` when every `status` command succeeds. The freshness scan
examines only compilation inputs and build descriptions:

- C/C++ sources and headers;
- included fragments, assembly, and scripting source compiled into the engine;
- `CMakeLists.txt`, `Makefile`, and `*.mk` build descriptions.

The separate timestamp check covers the canonical `engine/build_game.sh` driver
itself.

`-print -quit` makes the freshness scan stop on its first stale input. Generated
media, logs, documentation, levels, and unrelated repository files do not force
an engine rebuild.

If either freshness check fails, `ensure-build` delegates to the canonical `build` task;
it does not duplicate build flags or create a second build configuration.

### 2. Attach it to every native game runner

Add `deps: [ensure-build]` to each task that launches `engine/wf_game`:

- `run` and `gdb`;
- `run-level`;
- `run-filesys`, `run-filelight`, `run-treemap`, and `run-dome`;
- `run-snowgoons`, `run-qbert`, `run-smb`, and `run-moon`;
- `run-debug` and `run-debug-remote`.

Do not attach it to `build-level`: that task produces level data and does not
launch the engine. Do not replace `run-wf-edit`'s existing dependency because
that task launches a different binary with a different build configuration.

## Files changed

| File | Change |
|------|--------|
| `Taskfile.yml` | Add `ensure-build`; make all native `wf_game` runners depend on it |

## Verification

### Missing binary schedules a build

With `engine/wf_game` absent:

```bash
task --dry run-moon
```

Expected ordering:

1. `vendor-unpack`
2. `build`
3. `run-moon`

Then run the real command and confirm the Moon level opens:

```bash
task run-moon
```

### Current binary skips the build

Immediately repeat:

```bash
task --dry run-moon
```

Expected: Task reports `ensure-build` up to date and schedules only
`run-moon`.

### Newer source schedules a rebuild

Use a temporary timestamp change on a tracked engine source, check the dry run,
then restore the original timestamp or file state:

```bash
touch wfsource/source/pigsys/pigsys.cc
task --dry run-moon
```

Expected: `build` appears before `run-moon`.

### Runner coverage

Parse the Taskfile and confirm every task that executes `engine/wf_game` either
has `deps: [ensure-build]` or, in the case of `run-wf-edit`, launches a different
binary under its existing build dependency.

### Verification record — 2026-07-31

**PASS** — dependency scheduling, current-binary skipping, runner coverage, and
the final desktop launch were all confirmed; individual evidence follows.

- Current binary: `task --dry run-moon` reports `ensure-build` up to
  date and schedules only `run-moon`.
- Missing binary: temporarily moving `engine/wf_game` aside schedules
  `vendor-unpack`, `build`, then `run-moon`; the binary was restored afterward.
- Newer source: temporarily touching the tracked
  `wfsource/source/pigsys/pigsys.cc` schedules the same dependency chain; its
  original timestamp was restored afterward.
- Runner coverage: every native task invocation of `engine/wf_game` has the
  `ensure-build` dependency.
- Launch smoke reached engine and Jolt initialization. The canonical
  `engine/build_game.sh` defaults to `WF_ASAN=1`; its first run stopped when
  LeakSanitizer could not inspect the constrained environment. Repeating with
  leak detection disabled reached display creation and stopped because the
  environment cannot open `DISPLAY=:0`. These were environment limitations, not
  freshness failures. The user subsequently confirmed `task run-moon` works on
  the desktop on 2026-08-05.

## Non-goals

- Rebuilding level IFF files before launch. Level freshness belongs in a
  separate `ensure-level` design because named and arbitrary level runners have
  different inputs.
- Replacing the canonical build script with Task's timestamp mechanism.
- Hashing inputs. Filesystem modification times are sufficient for this local
  developer convenience guard and keep the check cheap.
