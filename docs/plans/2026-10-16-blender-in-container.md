# Blender asset generation in a container

16 October 2026 · **Plan: implemented; byte-identical proof waiting on the image build.** The image, routing, docs and the comparison script have landed on `blender-container`. The auto-mode permission check blocked the image build (a 375 MB download), so steps 3–5 of the verification are still open.

**In TODO.md** since 2026‑10‑16: "Run Blender asset generation in a container" (T3).

No visible surface: this changes how levels are built, not what they render. There are no mockups.

## Context

Will (2026‑10‑16): "we test and build in containers, not the host machine. we do this to maximize reproducability". The seven aquarium tanks are the last level builds that run the host's `blender`:

| Tank | Generator | Extra host steps |
|---|---|---|
| `aquarium_jellyfish`, `_lionfish`, `_betta` | `wflevels/aquarium_tanks/generate.py -- <tank>` | — |
| `aquarium_plants` | same | `cargo build` of `wf_attr_edit` and `oas2oad-rs`; `oas2oad` with `wftools/prep/prep`; `scripts/build-object-properties.py` |
| `aquarium_arowana` | `wflevels/aquarium_arowana/generate.py` | — |
| `aquarium_blue_shrimp` | `wflevels/aquarium_blue_shrimp/blender_create_aquarium_blue_shrimp.py` | — |
| `aquarium_tiger_barbs` | `wflevels/aquarium/blender_create_aquarium.py` (with `AQUARIUM_*` settings) | — |

Each one then runs `wftools/wf_blender/build_level_binary.sh <tank>` (iffcomp, levcomp and textile from `wftools/*/target/release/`).

The host route depends on several things that are not in the repository:

- **The host's Blender is Ubuntu's build, not Blender's.** `/usr/bin/blender` is the distribution package `blender 5.0.1+dfsg-1ubuntu1` (Ubuntu 26.04 "resolute"). It links the system Python 3.14. The official 5.0.1 Linux tarball bundles its own Python 3.11. Same Blender version, different build.
- **`addon_utils.enable('wf_blender')` loads `~/.config/blender/5.0/scripts/addons/wf_blender/`.** Its `.py` files are symlinks into the **main checkout** (`/home/will/WorldFoundry-wbniv/wftools/wf_blender/`), and its `wf_core.so` is a copy dated 2026‑09‑19. So a build in any worktree uses the main checkout's exporter. Blue shrimp, arowana and tiger barbs use this route.
- **`generate.py` imports the checkout's own `wftools/wf_blender`.** It then needs `wftools/wf_blender/wf_core.so`, a gitignored build of `wftools/wf_py` (PyO3, `abi3-py310`). It is absent from a fresh worktree, so jellyfish, lionfish, betta and plants fail there with `ModuleNotFoundError: No module named 'wf_core'`.
- **Plants passes `--prep=wftools/prep/prep`.** That is a gitignored C++ build, and it is also absent from a fresh worktree.

## Decisions

| # | Decision | Choice | Why |
|---|---|---|---|
| B1 | Blender version | **The official Blender 5.0.1 Linux x64 tarball**, sha256 `8019580e…fb4afb6` (from `download.blender.org/release/Blender5.0/blender-5.0.1.sha256`), unpacked to `/opt/blender` | Pinned by version and hash, and the same everywhere. Ubuntu's package is tied to 26.04, and the archive drops old versions. The host build is the *distribution* build (see Context), so byte identity is a real question, and verification step 4 settles it |
| B2 | Which image | **A new image, `docker/Dockerfile.blender` → `wf-blender:local`, `FROM wf-linux-test:local`** | Its layers share the test image's, so the disk cost is only Blender's (~1.3 GB unpacked), while ctest runs keep the smaller image. Still one entry point: `scripts/in-linux-container.sh` selects it with `WF_CONTAINER_IMAGE=blender` and builds both images on first use |
| B3 | How the add-on reaches Blender | **From the mounted checkout.** The image links `/opt/wf-blender-scripts/addons/wf_blender → /src/wftools/wf_blender` and sets `BLENDER_SYSTEM_SCRIPTS=/opt/wf-blender-scripts`. Each container build compiles `wftools/wf_py` and copies `libwf_core.so` to `wftools/wf_blender/wf_core.so` if it changed | Editing the add-on needs no image rebuild, and the container builds with *this* checkout's exporter, never the main checkout's. `wf_core.so` is `abi3-py310` and needs glibc 2.34 or newer, so the copy also works for the host's Blender (3.14) |
| B4 | Routing | **A shared preamble, `scripts/level-build.sh`.** Each `build.sh` runs `source scripts/level-build.sh; wf_level_build "$0" "$@"` after its `cd`. Outside the container this execs `in-linux-container.sh bash wflevels/<tank>/build.sh`. Inside, it builds the tools and returns, so the rest of the script runs unchanged | One copy of the logic instead of seven. `bash wflevels/<tank>/build.sh` still works, and so do the `task aquarium-*-level` entries. `-h`/`--help` is handled in one place |
| B5 | Settings passed to the generators | Exported `TANK_*`, `AQUARIUM_*`, `LIONFISH_*`, `BETTA_*`, `PLANTED_*` and `SHRIMP_*` variables are forwarded by name (`WF_CONTAINER_ENV`) | `TANK_PROFILE=touch bash …/build.sh` keeps working |
| B6 | The other host steps | **They all move into the container.** The preamble builds `iffcomp-rs`, `levcomp-rs`, `textile-rs` and `wf_py` with `cargo --locked`. `CARGO_HOME` is `/build/cargo-home` (persistent), and the container uses host networking for a first crate fetch. Plants now runs `bash wftools/prep/build.sh` before `oas2oad` on both routes | A tool built on the host links against Ubuntu 26.04's libraries and may not load in the 24.04 image. Building in place keeps every hard-coded `wftools/*/target/release/` path valid (16 references) at the cost of a rebuild when switching between host and container cargo (1.97.1 against 1.85.1) |
| B7 | Host escape hatch | `WF_LEVEL_BUILD_HOST=1` runs the pre-container route | Needed for the byte-identical comparison, and as a fallback |
| B8 | Taskfile | The seven `aquarium-*-level` tasks drop `deps: [tools-build]`, because the container builds its own tools. New tasks: `blender-image` and `level-build-compare` | — |

## The byte-identical check

`scripts/compare-level-build-routes.sh [TANK …]` (`task level-build-compare`) builds each tank twice from the same commit: once with `WF_LEVEL_BUILD_HOST=1` (host Blender) and once in the container. After each build it records the sha256 of **every file** under `wflevels/<tank>/` (except `build.sh`) plus `wflevels/<tank>.iff` and `wflevels/<tank>-standalone.iff`. It then restores the committed files. It prints the `.lvl`, `.iff` and `-standalone.iff` hashes per tank and an "N/N identical" count of all files. It exits 1 on any difference, and it refuses to run on dirty level paths.

**Pass means** every file is identical across the two routes, for all seven tanks. The reference is the host build from the same commit, not the committed files: some committed outputs are stale (see verification step 2), and that is not this change's concern. Any difference gets a concrete cause before anything is committed. A cause in our code gets fixed. A cause in the Blender build (Ubuntu's Python 3.14 against the bundled 3.11) is reported to Will, with the choice between accepting the new bytes and pinning Ubuntu's build in an `ubuntu:26.04` image.

## Verification

1. The routing works without Docker: `-h` prints usage. A fake `docker` on `PATH` shows `bash wflevels/aquarium_betta/build.sh` exec'ing `wf-blender:local` with the repo at `/src` and the generator settings forwarded. An unknown `WF_CONTAINER_IMAGE` exits 2.

    ```
    --- build.sh -h
    Usage: bash wflevels/aquarium_betta/build.sh [-h|--help]

    Builds this level: Blender generates the scene and exports the .lev, then
    rc=0
    --- level-build.sh --help
    Usage: bash wflevels/<level>/build.sh [-h|--help]
    rc=0
    --- level-build.sh (no args)
    level-build.sh is sourced by wflevels/<level>/build.sh; see --help
    rc=2
    --- in-linux-container.sh -h
    Usage: scripts/in-linux-container.sh [-h|--help] COMMAND [ARGS...]
    rc=0
    --- routing with fake docker
    DOCKER: [run] [--rm] [--user] [1000:1000] [--ulimit] [core=0] [--memory] [12g] [--network] [host] [-e] [CARGO_HOME=/build/cargo-home] [-e] [BETTA_FINS] [-e] [TANK_COUNT] [-v] [/home/will/WorldFoundry-wbniv/.claude/worktrees/agent-ac92094d13b63cb4c:/src] [-v] [/home/will/WorldFoundry-wbniv/.claude/worktrees/agent-ac92094d13b63cb4c/build-docker:/build] [-w] [/src] [wf-blender:local] [bash] [wflevels/aquarium_betta/build.sh]
    rc=0
    --- bad image
    in-linux-container.sh: unknown WF_CONTAINER_IMAGE 'nope' (linux-test|blender)
    rc=2
    ```

    **PASS** (2026‑10‑16). `NOT_FORWARDED=1` was set as well and is correctly absent.

2. The host route is deterministic, and `WF_LEVEL_BUILD_HOST=1` leaves it unchanged. All seven tanks were built twice from `2026-new-level` `06787e0d` with the unmodified scripts (host1, host2), then once more through the new preamble with `WF_LEVEL_BUILD_HOST=1` (host3). In a fresh worktree, `wftools/wf_blender/wf_core.so` (built from `wftools/wf_py`) and `wftools/prep/prep` first had to be built on the host; see Context.

    ```
    aquarium_jellyfish: 40 files, host1 vs host2: identical
        aquarium_jellyfish.lvl 5553a09acd00fd28 =HEAD · .iff 37096882148219a9 =HEAD · -standalone.iff d456dd55955ba655 =HEAD
    aquarium_blue_shrimp: 67 files, host1 vs host2: identical
        aquarium_blue_shrimp.lvl 591b5f50b74c28ca =HEAD · .iff 2e58a1c941b523a2 =HEAD · -standalone.iff b4e6325e8f3e0836 =HEAD
    aquarium_lionfish: 51 files, host1 vs host2: identical
        aquarium_lionfish.lvl abd9b4b7a5f40f5c =HEAD · .iff 7ea19e59de21ea31 =HEAD · -standalone.iff 0bb4924254ccf974 =HEAD
    aquarium_betta: 48 files, host1 vs host2: identical
        aquarium_betta.lvl b8159bcc6887f06f =HEAD · .iff 07dbd029887c6ce9 =HEAD · -standalone.iff 64ea80d81089f417 =HEAD
    aquarium_plants: 85 files, host1 vs host2: identical
        aquarium_plants.lvl 4c9415fae53eeabd =HEAD · .iff 49f58bba669410e5 !=HEAD(8fdef1b12decfd09) · -standalone.iff 9c4db4e7a081dda1 !=HEAD(ad0848403c83aeac)
    aquarium_arowana: 47 files, host1 vs host2: identical
        aquarium_arowana.lvl 462f92dc2f61c6ec =HEAD · .iff 730b2f308d504ab8 =HEAD · -standalone.iff f116a9604b00c7c6 =HEAD
    aquarium_tiger_barbs: 28 files, host1 vs host2: identical
        aquarium_tiger_barbs.lvl f7ce5228394b4005 !=HEAD(9fa39f1ffb87cb46) · .iff 29ea798d4e644291 !=HEAD(c03df0d51b1adaa5) · -standalone.iff e90796ca4819ae7f !=HEAD(6257ea59b9090b39)
    host1 vs host3 (WF_LEVEL_BUILD_HOST=1): every tank differs only in its edited build.sh
    ```

    **PASS** (2026‑10‑16): the host builds are repeatable, and the preamble does not change the host route. **Separately: the committed outputs are stale for three tanks.** The betta, jellyfish and lionfish `actor-map.json` files lack the `"seahorses": null` key that the current `generate.py` writes. The committed plants `.iff`, `-standalone.iff` and `seahorse_m_body.iff` and the tiger barbs `.lev`/`.lvl`/`.iff` predate their current sources. Nothing was committed for these; they were restored from HEAD.

3. The image builds and Blender runs in it: `task blender-image && WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background --python-expr "import addon_utils, bpy; print(bpy.app.version_string, addon_utils.enable('wf_blender', default_set=False, persistent=False) is not None)"` prints `5.0.1 True`.

    ```
    $ task blender-image && WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background --python-expr "…"
    #8 unpacking to docker.io/library/wf-blender:local 0.0s done
    #8 DONE 0.2s
    5.0.1 True
    Blender 5.0.1 (hash a3db93c5b259 built 2025-12-16 01:30:59)
    Blender quit
    ```

    **PASS** (2026‑10‑16, after Will's go-ahead for the download). Getting there took two fixes:
    - `download.blender.org` answers Python's default `User-Agent` with HTTP 403, so the first build failed after 0.6 s (`urllib.error.HTTPError: HTTP Error 403: Forbidden`). A HEAD request with the default agent gets 403; with any ordinary agent it gets 200 and `Content-Length: 374154072`. The Dockerfile now sends one.
    - `blender-image` had `deps: [linux-test-image]`, which runs `docker build` on the test image every time. Once disk hygiene had pruned the build cache, that rebuilt `wf-linux-test:local` from scratch, re-downloading every package and swapping an apt-updated image in under other sessions. That rebuild was stopped, and the task now builds the test image only when it is missing.
    The image adds 1.03 GB (`docker image inspect wf-blender:local`: 1030559731 bytes).

4. Byte-identical for all seven tanks: `task level-build-compare` exits 0 and prints `N/N identical` for every tank.

    ```
    $ task level-build-compare
    task: [level-build-compare] scripts/compare-level-build-routes.sh 
    tank                   file                          host             container        result
    aquarium_jellyfish     aquarium_jellyfish/aquarium_jellyfish.lvl 5553a09acd00fd28 5553a09acd00fd28 same
    aquarium_jellyfish     aquarium_jellyfish.iff        37096882148219a9 37096882148219a9 same
    aquarium_jellyfish     aquarium_jellyfish-standalone.iff d456dd55955ba655 d456dd55955ba655 same
    aquarium_jellyfish: all files: 39/39 identical
    aquarium_blue_shrimp   aquarium_blue_shrimp/aquarium_blue_shrimp.lvl 591b5f50b74c28ca 591b5f50b74c28ca same
    aquarium_blue_shrimp   aquarium_blue_shrimp.iff      2e58a1c941b523a2 2e58a1c941b523a2 same
    aquarium_blue_shrimp   aquarium_blue_shrimp-standalone.iff b4e6325e8f3e0836 b4e6325e8f3e0836 same
    aquarium_blue_shrimp: all files: 66/66 identical
    aquarium_lionfish      aquarium_lionfish/aquarium_lionfish.lvl abd9b4b7a5f40f5c abd9b4b7a5f40f5c same
    aquarium_lionfish      aquarium_lionfish.iff         7ea19e59de21ea31 7ea19e59de21ea31 same
    aquarium_lionfish      aquarium_lionfish-standalone.iff 0bb4924254ccf974 0bb4924254ccf974 same
    aquarium_lionfish: all files: 50/50 identical
    aquarium_betta         aquarium_betta/aquarium_betta.lvl b8159bcc6887f06f b8159bcc6887f06f same
    aquarium_betta         aquarium_betta.iff            07dbd029887c6ce9 07dbd029887c6ce9 same
    aquarium_betta         aquarium_betta-standalone.iff 64ea80d81089f417 64ea80d81089f417 same
    aquarium_betta: all files: 47/47 identical
    aquarium_plants        aquarium_plants/aquarium_plants.lvl 4c9415fae53eeabd 4c9415fae53eeabd same
    aquarium_plants        aquarium_plants.iff           49f58bba669410e5 49f58bba669410e5 same
    aquarium_plants        aquarium_plants-standalone.iff 9c4db4e7a081dda1 9c4db4e7a081dda1 same
    aquarium_plants: all files: 82/84 identical
    aquarium_arowana       aquarium_arowana/aquarium_arowana.lvl 462f92dc2f61c6ec 462f92dc2f61c6ec same
    aquarium_arowana       aquarium_arowana.iff          730b2f308d504ab8 730b2f308d504ab8 same
    aquarium_arowana       aquarium_arowana-standalone.iff f116a9604b00c7c6 f116a9604b00c7c6 same
    aquarium_arowana: all files: 46/46 identical
    aquarium_tiger_barbs   aquarium_tiger_barbs/aquarium_tiger_barbs.lvl f7ce5228394b4005 f7ce5228394b4005 same
    aquarium_tiger_barbs   aquarium_tiger_barbs.iff      29ea798d4e644291 29ea798d4e644291 same
    aquarium_tiger_barbs   aquarium_tiger_barbs-standalone.iff e90796ca4819ae7f e90796ca4819ae7f same
    aquarium_tiger_barbs: all files: 27/27 identical
    task: Failed to run task "level-build-compare": exit status 1
    ```

    The two plants files that differ, with each route built once more and diffed:

    ```
    $ diff host/actor-map.json container/actor-map.json      # entry[2] of an actor
    <           0.0282079251617939
    >           0.028207925161793903
    $ diff host/aquarium_plants.lev container/aquarium_plants.lev   # 3 more JSON-style floats, then EULR b angles
    < { 'EULR' … 0.2630222141742706(1.15.16) …
    > { 'EULR' … 0.2630221843719482(1.15.16) …
    < { 'EULR' … -0.1202898845076561(1.15.16) …        (×4 actors)
    > { 'EULR' … -0.1202898919582367(1.15.16) …
    ```

    **FAIL as written** (2026‑10‑16): the task exits 1, because plants is 82/84. Everything the engine loads is identical for all seven tanks: every `.lvl`, `.iff` and `-standalone.iff`, and every other file of six tanks. Plants' `aquarium_plants.lev` and `actor-map.json` differ only in the last digits of a few floats. The `actor-map.json` values are one double ULP apart, and the `EULR` angles are adjacent float32 values, 2.98e‑8 apart. levcomp quantises angles to 1.15.16 fixed point, a step of 1.5e‑5, so the `.lvl` is identical.

    The cause is the two Blenders' maths stacks. Host Blender is Ubuntu's package `5.0.1+dfsg-1ubuntu1` on Python 3.14.4 with numpy 2.3.5. The official build is Python 3.11.13 with numpy 1.26.4. One-ULP differences in trigonometry and float formatting between them change the last digit of these generated values.

    Earlier failures, fixed before this run:
    - Five tanks could not build in the container at all: no Pillow in Blender's bundled Python, and the add-on's schema search not following the image's symlink (`ecd65ae0`).
    - The script had compared the leftover committed files and still printed `identical`. It now reports `BUILD FAILED` and skips the tank.

    Decision for Will: accept the container's rounding, so this step's bar becomes "every shipped file identical; intermediates may differ only in float rounding" (recommended, because the official tarball is sha256-pinned while Ubuntu's package moves with apt), or pin Ubuntu's Blender in an `ubuntu:26.04` image to get bit-for-bit `.lev` text.

5. Disk: `df -h /` after the image build still shows at least 5 GB free (9.7 GB before it).

    ```
    $ df -h /
    /dev/nvme0n1p2  469G  438G  6.9G  99% /
    ```

    **PASS** (2026‑10‑16): 6.9 GB free after the image (1.03 GB) and two full seven-tank comparisons.
