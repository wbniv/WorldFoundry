# WorldFoundry developer workspace setup

## Context

`foundry-linux-setup/install.sh` (Phase 0 of the Foundry Linux distro plan) installs
system-level packages via the per-metapackage scripts. It currently also does
WF-engine-specific workspace setup: cloning `wbniv/WorldFoundry` and `wbniv/wf-games`,
installing Rust (needed only to build wftools pre-Phase-1), building wftools, and
registering the Blender addon from the cloned engine repo.

These belong in a separate script because:
- They require WF repos to exist (Foundry Linux infra should not depend on WF repos)
- Phase 1 deprecates Rust + wftools source build (wftools will ship as .debs from
  foundry-apt CI); the cloning and workspace parts survive Phase 1 but the build does not
- A new user installing Foundry Linux to port arcade ROMs doesn't need the WF engine repo

**This plan delivers** a standalone `foundry-linux-setup/setup-wf-workspace.sh` that
replaces the WF-specific steps removed from `install.sh`.

## What moved here from install.sh

| Removed from install.sh | Lives here |
|---|---|
| `WF_GITHUB_ORG`, `WF_ENGINE_REPO`, `WF_GAMES_REPO`, `PROJECTS_DIR` | config vars in the new script |
| `install_rust()` + `maturin` install | `install_rust()` |
| `clone_wf_repos()` + `clone_repo()` | `clone_wf_repos()` + `clone_repo()` |
| `build_wftools()` | `build_wftools()` |
| Blender addon registration (removed from `install-worldfoundry-blender.sh`) | `register_blender_addon()` |
| `.claude/` symlink setup between repos | inside `clone_wf_repos()` |
| `--skip-rust`, `--skip-clone`, `--skip-build` flags | same flags on the new script |
| Role-based repo selection (`game-dev`, `engine-dev`, `both`, `maintainer`) | `--role` flag |

## New script: `foundry-linux-setup/setup-wf-workspace.sh`

```
Usage: setup-wf-workspace.sh [--role ROLE] [--projects-dir DIR]
                              [--skip-rust] [--skip-clone] [--skip-build]
                              [--skip-addon] [--dry-run|-n] [-h|--help]

Roles: game-dev, engine-dev, both (default), maintainer
```

Steps in order:

1. `clone_wf_repos` — clone `wbniv/WorldFoundry` and/or `wbniv/wf-games` into `~/Projects/`
   with `--depth 1 --filter=blob:none`; sparse-checkout to exclude `engine/vendor/`
   on the engine repo; `.claude/` symlink between repos if both present
2. `install_rust` — rustup + cargo + maturin (pip --user); skip if cargo already present
3. `build_wftools` — `cargo build --release` in `~/Projects/WorldFoundry/wftools/`
4. `register_blender_addon` — `bash wftools/wf_blender/install.sh` from the engine repo

All steps are idempotent and individually skip-able.

## Changes to existing scripts

**`foundry-linux-setup/install.sh`** — remove:
- `WF_GITHUB_ORG`, `WF_ENGINE_REPO`, `WF_GAMES_REPO`, `PROJECTS_DIR` vars
- `install_rust()`, `clone_wf_repos()`, `clone_repo()`, `build_wftools()` functions
- `--skip-rust`, `--skip-clone`, `--skip-build` flags
- WF-specific next-steps from `summary()`
- Roles reduce to "which metapackages": play / game-dev / engine-dev / both / maintainer
  (role still controls metapackage selection; repo setup is now `setup-wf-workspace.sh`)

**`foundry-linux-setup/install-worldfoundry-blender.sh`** — remove:
- Addon registration block (`--skip-addon` flag, `ADDON_CANDIDATES` logic, `PROJECTS_DIR` ref)
- Script now only does `apt install blender python3`

## Verification

1. `bash install.sh --role both --dry-run --force` — no longer mentions Rust, no cloning,
   no wftools build; only prints metapackage install commands.

2. `bash setup-wf-workspace.sh --dry-run` — prints `git clone` for both repos, rustup
   install, `cargo build --release`, and addon installer invocation.

3. `bash setup-wf-workspace.sh --role engine-dev --dry-run` — clones engine repo only,
   no wf-games.

4. `bash setup-wf-workspace.sh --skip-rust --skip-build --dry-run` — clones repos,
   skips Rust + wftools build, attempts addon registration.

5. `bash install-worldfoundry-blender.sh --dry-run` — only shows `apt install blender python3`;
   no mention of addon installer or engine repo.
