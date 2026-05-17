# Per-metapackage install scripts (Phase 0 refactor)

## Context

`foundry-linux-setup/install.sh` is the Phase 0 setup script from the Foundry Linux distro proposal ([`docs/investigations/2026-05-16-foundry-linux-distro-proposal.md`](../investigations/2026-05-16-foundry-linux-distro-proposal.md)). It was supposed to install everything the Phase 1 APT metapackages will eventually install — including the retro-porting toolchain (MAME, `dasm`, `cc65` → ships `sim65` 6502 emulator + `da65` disassembler, `radare2`, etc., plus source-built Ghidra / f9dasm / vgmstream / libvgm / xa65). It currently doesn't: `install_apt_packages()` at [`install.sh:222-246`](../../foundry-linux-setup/install.sh) only mirrors `Taskfile.yml:dev-setup` (engine build deps). That's the gap behind the original "which script installs the 6502 emulator(s)" question — there isn't one.

Beyond just filling that gap, the shape is wrong: one monolithic 475-line script with mixed concerns (apt for engine, rustup for tooling, git clone, wftools build, Blender addon install) hides which Phase 0 step corresponds to which Phase 1 metapackage. When Phase 1 lands, the proposal says `install.sh` "collapses to ~20 lines" — but with the current structure, it's not obvious what collapses to what.

**Change:** mirror `foundry-apt/packages/` 1:1 with `foundry-linux-setup/install-<metapackage>.sh`. Each per-metapackage script does in Phase 0 what `apt install <metapackage>` will do in Phase 1; the Phase 1 collapse becomes a near-mechanical "replace body with a single `apt install` call." The top-level `install.sh` keeps only what doesn't belong to any metapackage (distro check, sudo bootstrap, role parsing, repo cloning, Rust toolchain) and dispatches to the per-metapackage scripts.

## Layout

```
foundry-linux-setup/
  lib.sh                                       (NEW — shared helpers)
  install.sh                                   (TRIM — orchestrator + non-meta Phase 0)
  install-worldfoundry-engine-build-deps.sh    (NEW)
  install-worldfoundry-blender.sh              (NEW)
  install-worldfoundry-retro-tools.sh          (NEW — answers the 6502 question)
  install-worldfoundry-android-dev.sh          (NEW)
  install-task.sh                              (NEW)
  install-worldfoundry-dev.sh                  (NEW — orchestrator for the umbrella metapackage)
```

Each per-metapackage script is the Phase 0 expansion of one metapackage's `Depends:` and source-build-sidecar `Recommends:`. The orchestrator (`install-worldfoundry-dev.sh`) calls the constituent scripts in dependency order, matching [`foundry-apt/packages/worldfoundry-dev/DEBIAN/control`](../../foundry-apt/packages/worldfoundry-dev/DEBIAN/control).

## Metapackage → script mapping

Confirmed from `foundry-apt/packages/*/DEBIAN/control`:

| Script | apt deps (from metapackage `Depends:`) | Source-build sidecars (from `Recommends:` not in Ubuntu) |
|---|---|---|
| `install-worldfoundry-engine-build-deps.sh` | `build-essential` `cmake (>=3.22)` `libx11-dev` `libgl1-mesa-dev` `libglu1-mesa-dev` `gdb` `xxd` `python3` `pkg-config` `git` `curl` `wget` `unzip` | — |
| `install-worldfoundry-blender.sh` | `blender (>=4.2)` `python3` `worldfoundry-engine-build-deps` | invokes `wftools/wf_blender/install.sh` for the addon (Phase 1 `Recommends: worldfoundry-blender-addon`) |
| `install-worldfoundry-retro-tools.sh` | `mame` `mame-tools` `dasm` `cc65` `z80dasm` `z80asm` `radare2` `binwalk` `sox` `binutils-m68k-linux-gnu` | `ghidra` → `~/opt/ghidra-*/`; `f9dasm` → `~/opt/f9dasm/`; `vgmstream-cli` → `~/opt/vgmstream/`; `libvgm` → `~/opt/libvgm/`; `xa65` → `~/opt/xa65/` (per [arcade-tooling investigation](../investigations/2026-05-15-claude-arcade-tooling.md) §2 + §1 note line 46) |
| `install-worldfoundry-android-dev.sh` | `openjdk-17-jdk` `adb` `google-android-ndk-r26c-installer` | — |
| `install-task.sh` | (no `Depends:` yet — `foundry-apt/packages/task/` has only a `build.sh`, the .deb wraps the `task` binary itself) | downloads `task` from taskfile.dev if no .deb available (current `install_task_runner()` at `install.sh:281-295`) |
| `install-worldfoundry-dev.sh` | composes the above in this order: engine-build-deps → task → blender → retro-tools → android-dev (optional) | calls each script as `bash install-<name>.sh "$@"` |

## Role → script mapping in top-level `install.sh`

Existing roles preserved. Dispatch table:

| Role | Calls |
|---|---|
| `play` | (none today — no `worldfoundry-runtime` metapackage exists yet; warn and continue) |
| `game-dev` | `install-worldfoundry-engine-build-deps.sh`, `install-task.sh`, `install-worldfoundry-blender.sh`, `install-worldfoundry-retro-tools.sh`, then clone `wf-games`, build wftools |
| `engine-dev` | `install-worldfoundry-engine-build-deps.sh`, `install-task.sh`, `install-worldfoundry-retro-tools.sh`, then clone `WorldFoundry.2026-new-level`, build wftools |
| `both` (default) | `install-worldfoundry-dev.sh` (= engine-build-deps + blender + retro-tools + task), then clone both repos, build wftools |
| `maintainer` | `both` + `install-worldfoundry-android-dev.sh` |

Existing `--skip-rust`, `--skip-blender`, `--skip-clone`, `--skip-build`, `--dry-run`, `--force`, `--allow-24.04`, `-h` flags retained. New flag: `--skip-retro` (so a host without disk for Ghidra can opt out).

## Per-metapackage script contract

Every `install-*.sh` script:

1. `#!/usr/bin/env bash` + `set -euo pipefail` at the top.
2. Handles `-h` / `--help` — prints "Installs the worldfoundry-X metapackage's Phase 0 equivalent" + flag list + exits 0. Per `~/SRC/CLAUDE.md`: `-h` must short-circuit before any arg parsing or apt calls.
3. Sources `lib.sh` if present, falls back to a tiny inline `info()`/`die()`/`run_sudo()` shim if run standalone. The shim is ~10 lines so the script also works when copied to a clean machine before the rest of the repo is there.
4. Idempotent — `apt-get install -y` is naturally idempotent; source-build sidecars guard with `[[ -d ~/opt/<tool> ]] && info "<tool> already installed" && exit 0` (or `--force` to re-run).
5. Respects `FOUNDRY_LOG_FILE` env var (set by top-level `install.sh`) so all per-script output lands in the same `~/.local/state/foundry-install.log`.
6. Phase 1 collapse path: each script's body shrinks to a single `run_sudo apt-get install -y <metapackage>` line once `apt.worldfoundry.org` is published. The source-build sidecars disappear (they ship as `.deb`s from the foundry-apt CI per proposal §483).

## Critical files

**New:**

- `foundry-linux-setup/lib.sh` — extracted helpers: color codes, `log_to_file`, `info`, `ok`, `warn`, `err`, `die`, `step`, `run`, `run_sudo`, `init_logging`. Source these from current `install.sh:50-93`.
- `foundry-linux-setup/install-worldfoundry-engine-build-deps.sh` — body extracted from `install.sh:222-246` (`install_apt_packages`).
- `foundry-linux-setup/install-worldfoundry-blender.sh` — `apt install blender python3` + invoke `wftools/wf_blender/install.sh` (current `install.sh:394-415` `install_blender_addon`).
- `foundry-linux-setup/install-worldfoundry-retro-tools.sh` — apt block from `docs/investigations/2026-05-15-claude-arcade-tooling.md:34-42` + `xa65` source-build fallback from line 46 + Ghidra/f9dasm/vgmstream/libvgm source-builds from §2 of the same doc. **This is the script that installs the 6502 emulator(s)** (`sim65` via `cc65`; full 6502 system emulation via MAME).
- `foundry-linux-setup/install-worldfoundry-android-dev.sh` — extracted from `Taskfile.yml:dev-setup` lines 249-251 (`openjdk-17-jdk adb google-android-ndk-r26c-installer`).
- `foundry-linux-setup/install-task.sh` — body from `install.sh:281-295` (`install_task_runner`).
- `foundry-linux-setup/install-worldfoundry-dev.sh` — sequential calls to the constituent scripts.

**Modified:**

- `foundry-linux-setup/install.sh` — replace the 14 step functions with: arg parsing, distro check (162-199), sudo check (201-217), `init_logging` (now in `lib.sh`), role-based dispatch to the per-metapackage scripts, then the non-metapackage Phase 0 steps that stay: `install_rust` (248-279), `clone_wf_repos` (297-365), `build_wftools` (367-392), `summary` (420-448). Net length: estimated 200-220 lines down from 475.

**Reused (no changes):**

- `wftools/wf_blender/install.sh` — invoked by `install-worldfoundry-blender.sh`.
- `wftools/wf_blender/install_blender_mcp.sh` — optional, invoked by same.
- `Taskfile.yml:dev-setup` (236-251) — left as-is; it's a developer convenience that overlaps with `install-worldfoundry-engine-build-deps.sh` + `install-worldfoundry-android-dev.sh` but doesn't need to be a single canonical source anymore.

## Verification

1. **6502 emulator install works in isolation.** On a fresh Ubuntu 26.04 VM:

    ```
    bash foundry-linux-setup/install-worldfoundry-retro-tools.sh
    sim65 --version          # cc65's 6502 simulator
    da65 --version           # cc65's 6502 disassembler
    mame -listcrc qbert      # full-system 6502 emulator
    radare2 -v
    ls ~/opt/                # ghidra-*/  f9dasm/  vgmstream/  libvgm/  xa65/
    ```

    Expect: all five binaries report versions; all five `~/opt/` dirs exist.

2. **Dry-run is clean.** `bash install-worldfoundry-retro-tools.sh --dry-run` prints every `apt-get install` and every source-build `git clone` + `make` without executing. Same for each other per-meta script.

3. **Orchestrator wiring.** `bash install-worldfoundry-dev.sh --dry-run` prints calls to each constituent script in the documented order.

4. **Role dispatch.** `bash install.sh --role engine-dev --dry-run` prints calls to engine-build-deps + task + retro-tools (skips blender, skips android-dev). `--role both --dry-run` calls `install-worldfoundry-dev.sh`.

5. **`-h` short-circuits everywhere.** Every new script: `bash install-<name>.sh -h` prints usage and exits 0 without sudo prompt, apt update, or any side effects (per `~/SRC/CLAUDE.md`).

6. **Phase 1 collapse rehearsal.** Manually inspect each per-meta script and confirm the body could be replaced with `run_sudo apt-get install -y <metapackage>` once `apt.worldfoundry.org` ships, with no remaining Phase 0 leftovers. (Source-build sidecars disappear because foundry-apt CI builds them as `.deb`s per proposal §483.)

7. **Existing install.sh behavior preserved.** On a machine where the old `install.sh` succeeded, re-running the new `install.sh` with the same `--role` flag produces the same end state: same packages installed, same repos cloned, same wftools binaries built, same Blender addon registered. Diff the apt history and `~/Projects/` listing before vs after.
