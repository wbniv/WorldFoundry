# Fix: `task build-wf-edit` fails on fresh clone

## Context

`task build-wf-edit` fails in two ways on a fresh clone:

1. **Uninitialized submodules** — `cmake/Corrosion`, `wftools/y-crdt`, `third_party/glfw`, and `third_party/imgui` are declared in `.gitmodules` but not fetched. CMake aborts when it can't find `CMakeLists.txt` inside them.
2. **Missing apt packages** — `libvpx-dev` (VP8/VP9 for WebRTC video) was absent from `dev-setup-editor`. `libssl-dev` was already listed.

The `libvpx-dev` omission was already fixed in `Taskfile.yml` in the previous turn. The submodule init is not yet automated.

## What needs to change

### `Taskfile.yml` — two edits

**1. Add submodule init step to `build-wf-edit`**

Prepend a `git submodule update --init` call covering all four editor-required submodules. This makes `task build-wf-edit` self-sufficient from a fresh clone without requiring the user to know which submodules to fetch.

`git submodule update --init` is idempotent: if a submodule is already checked out it completes instantly with no network activity.

```yaml
build-wf-edit:
  desc: "Build the wf-edit GUI editor binary (WebRTC voice/video collab). First run: task dev-setup-editor."
  cmds:
    - git submodule update --init cmake/Corrosion wftools/y-crdt third_party/glfw third_party/imgui
    - cmake -S . -B build-editor -DWF_ENABLE_EDITOR=ON -DCMAKE_BUILD_TYPE=Debug
    - cmake --build build-editor --target wf_edit -j{{.NPROC}}
  vars:
    NPROC:
      sh: nproc
```

**2. Document the submodule requirement in `dev-setup-editor`** *(informational — the build step above handles actual init)*

No change needed here beyond the `libvpx-dev` fix already applied.

## Files to modify

- `Taskfile.yml` — add the `git submodule update --init …` line to `build-wf-edit`

## Verification

1. Wipe the build cache: `rm -rf build-editor`
2. Confirm submodules appear empty: `ls third_party/glfw/ third_party/imgui/`
3. Run: `task build-wf-edit`
4. CMake configure should complete without errors; `cmake --build` should produce `build-editor/wf_edit`
