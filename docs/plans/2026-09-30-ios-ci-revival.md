# iOS CI revival: `ios-simulator-debug` green on iPhone and iPad

**Date:** 2026‑09‑30 · **Branch:** `ios-ci-revival` · **TODO:** none (dispatched directly; `TODO.md` is not edited by this change)

## Problem

Codemagic build `6abd0e3181ab9efd16b331d6` (commit `2f0f0efb`) failed at **Configure CMake for iOS Simulator (arm64)** after about a minute. The workflow had no tee'd log artifact and Codemagic has no log API, so the error text was unknown. iOS has had no working CI since April 2026, and the workflow comments still describe Phase 0 ("no `if(IOS)` branch yet").

## Root cause (configure)

Commit `92b325a2` (2026‑05‑26) deleted the iOS-only override that forced `WF_PHYSICS_ENGINE=legacy`, so iOS now takes the default `jolt`. `CMakeLists.txt:674` does `include(${JOLT_DIR}/Jolt/Jolt.cmake)`, and `engine/vendor/jolt-physics-5.5.0/` exists only after extracting `engine/vendor/jolt-physics-5.5.0.tar.gz`. The macOS workflow has an **Extract Jolt vendor archive** step; the iOS workflow never did. Reproduced on Linux against a clean checkout:

```
CMake Error at CMakeLists.txt:674 (include):
  include could not find requested file:
    .../engine/vendor/jolt-physics-5.5.0/Jolt/Jolt.cmake
-- Configuring incomplete, errors occurred!
```

After extracting the archive exactly as the macOS step does, the same configure completes with no errors. The "Cannot specify compile options for target 'Jolt' which is not built by this project" message the deleted override cited is also what CMake prints when that `include()` fails and a later command refers to `Jolt`. Whether it was ever a separate Xcode problem is settled only by an iOS run.

## Design

- **Extract Jolt in the iOS workflow**, copying the macOS step verbatim. Rejected alternative: `-DWF_PHYSICS_ENGINE=legacy` on iOS. The CMake comment says legacy physics is being deleted, and it would make iOS the only target on a different physics engine.
- **Readable failures.** Every step starts with `exec > >(tee -a "$CM_BUILD_DIR/cm-build.log") 2>&1`, and `cm-build.log` is listed as an artifact. Configure output also goes to `ios-configure.log`. Full `xcodebuild` output goes to `xcodebuild.log` only (thousands of lines), with `-IDEBuildingContinueBuildingAfterErrors=YES` so one run reports every compile error. The `error:` lines and the `** BUILD … **` line are copied into `cm-build.log`.
- **Deterministic configure.** Delete the cached `CMakeCache.txt` and `CMakeFiles/` before configuring, as the macOS step does.
- **Find the `.app`; do not hardcode it.** The step searches `engine/` and `build-ios-sim/` for `wf_game.app`. With `-G Xcode` the per-config subdirectory may carry `$(EFFECTIVE_PLATFORM_NAME)`.
- **iPhone and iPad.** Choose the newest available iOS runtime that has both an iPhone and an iPad. For each device, in order: boot it, install the same `.app`, launch it with `--stdout` and `--stderr` sent to files, wait 8 s, take a screenshot, capture the unified log, check that the process is still alive, then shut the device down. Each device gets its own artifacts: `ios-{iphone,ipad}-screenshot.png` and `ios-{iphone,ipad}-launch.log` (stdout, stderr and the unified log in labelled sections). A crash report, if any, is copied as `ios-crash-*.ips`.
- **Non-blank check.** `Info.plist` sets `UIStatusBarHidden`, so an app that draws nothing gives a single-colour screen. The check downscales the screenshot with `sips`, decodes it with `read_png` from `tests/compare_renderer_frames.py` (no dependencies), and counts distinct colours in the central 60 % × 60 %, which leaves out the home indicator. More than one colour means non-blank.
- **Verdict.** A device is `OK` only if install, launch, non-blank screenshot and process-alive after 8 s all pass. The block prints `IOS IPHONE: OK|FAIL` and `IOS IPAD: OK|FAIL`, and the step exits non-zero if either is `FAIL`. If no runtime has an iPad, it prints the `simctl list` output and `IOS IPAD: FAIL (no iPad simulator)`.

## Visible surface

The only visible surface is CI log text. The verdict block is:

```
=== iOS simulator verdict ===
iphone: iPhone 16 Pro (com.apple.CoreSimulator.SimRuntime.iOS-18-5) colours=1234 alive=yes
ipad:   iPad Pro 13-inch (M4) (com.apple.CoreSimulator.SimRuntime.iOS-18-5) colours=987 alive=yes
IOS IPHONE: OK
IOS IPAD: OK
```

## Budget

This task may use at most 6 builds and 90 Mac-minutes. Before each build, `scripts/codemagic-budget.sh` (dry run) must show month-to-date usage below 300 minutes. Builds run on the `ios-ci-revival` branch only.

## Verification

1. `python3 -c "import yaml;yaml.safe_load(open('codemagic.yaml'))"` parses.
2. `python3 -m pytest tests/test_codemagic_aquarium_parity.py -q` still passes, so the macOS step is untouched.
3. `bash -n` passes on every script in `ios-simulator-debug`.
4. Codemagic `ios-simulator-debug` on `ios-ci-revival`: configure passes, build passes, and the verdict block prints `IOS IPHONE: OK` and `IOS IPAD: OK`. Both screenshots are downloaded and viewed.
