# Plan — Markdown rendering in the wf-edit chat sidebar (vendor imgui_markdown)

**Date:** 2026-05-25

## Context

The `wf-edit` collaborative chat sidebar already ships and works end-to-end (send/receive
over the relay `CHAT` channel), but it renders message bodies as **plaintext** via
`ImGui::TextWrapped`. This is the last open piece of the editor v1 chat item in `TODO.md`:
swap that to markdown so messages can use **bold**/_italic_/headings/lists/links. The wire
format stays plaintext (markdown is rendered client-side at display time — consistent with
the [realtime-coediting plan](../../WorldFoundry.2026-new-level/docs/plans/2026-05-21-realtime-coediting.md)
§ chat). The library is [`imgui_markdown`](https://github.com/juliettef/imgui_markdown)
(single header, zlib license), which the realtime-coediting Phase 5 plan intended to vendor
but never did.

Scope is **chat only**. The `SHOW_AS_TEXTEDITOR` Notes leaf in `property_panel.cc` is an
*editable* `InputTextMultiline`, not a rendered display, so it's a separate concern (left as
the second half of the TODO item).

## What exists (reuse, don't rebuild)

- **Chat render loop** — [`engine/wf_edit/main.cc:1011-1015`](../../WorldFoundry.2026-new-level/engine/wf_edit/main.cc):
  `ImGui::TextColored("%s:", name)` + `SameLine()` + `ImGui::TextWrapped("%s", text)`. Line
  1015 is the swap target. `ChatEntry { name; colour[3]; text }` at `main.cc:256-260`.
- **Includes** — `main.cc:22-26` use `"imgui.h"` / `"ImGuizmo.h"` style; `imgui_internal.h`
  (line 23) already pulls in the `ImVec2` math operators imgui_markdown needs.
- **Vendoring pattern** — [`third_party/imguizmo/`](../../WorldFoundry.2026-new-level/third_party/imguizmo)
  holds `ImGuizmo.h` + `ImGuizmo.cpp` + `LICENSE`. CMake wires it at
  [`CMakeLists.txt`](../../WorldFoundry.2026-new-level/CMakeLists.txt) ~934 (`IMGUIZMO_DIR`),
  source list ~949-956, include dirs ~964-973 (all inside `if(WF_ENABLE_EDITOR …)`).
- **Screenshot-proof hooks** — the `WF_EDIT_*_UI` env pattern (`WF_EDIT_ADD_UI`,
  `WF_EDIT_UNDO_UI`, …) seeds one action so `--screenshot` captures it; mirror it for chat.

## Approach

1. **Vendor the header.** Fetch `imgui_markdown.h` from a pinned upstream tag into
   `third_party/imgui_markdown/imgui_markdown.h`, plus the upstream `LICENSE` (zlib) beside
   it — mirroring `third_party/imguizmo/`. Single committed header (~38 KB; well under any
   vendor-size concern — the "no giant vendor" rule is about 100 MB+ toolchains).

2. **CMake (one line).** In the editor block of `CMakeLists.txt`: add
   `set(IMGUI_MARKDOWN_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui_markdown)` next to
   `IMGUIZMO_DIR`, and add `${IMGUI_MARKDOWN_DIR}` to `target_include_directories(wf_edit …)`.
   **No `.cpp`** — header-only. Include it from **only** `main.cc` (one TU), so even
   non-`inline` defs raise no ODR issue.

3. **Render swap + config** (`main.cc`):
   - `#include "imgui_markdown.h"` after line 26.
   - A file-scope `static ImGui::MarkdownConfig` built once (lazily): `linkCallback` = a tiny
     no-op static fn (links render styled; clicking does nothing in v1 — `xdg-open` is a
     noted follow-up), `imageCallback`/`tooltipCallback` = null, `headingFormats[0..2] =
     { nullptr, true }` (default font + underline separator — no custom fonts loaded), and
     `formatCallback = ImGui::defaultMarkdownFormatCallback`.
   - Rewrite the loop body (1012-1015): render the coloured **name on its own line**
     (`TextColored`), then the body **below** via
     `ImGui::Markdown(e.text.c_str(), e.text.size(), mdConfig)` (drop the `SameLine` —
     markdown is block-level: headings/lists need their own lines). Wrap each entry in a
     `PushID`/`PopID` so links/widgets in different messages don't collide.

4. **Screenshot-proof hook.** Add `WF_EDIT_CHAT_DEMO=1`: on first frame, push a couple of
   sample markdown `ChatEntry`s into `chat_log` (e.g. `**bold**`, `# heading`, a `- list`,
   `[a link](http://x)`) and force the Chat panel to render even without a relay (the panel
   is normally gated on relay-connected). Lets `--screenshot` capture rendered markdown
   headlessly — same pattern as `WF_EDIT_ADD_UI`.

## Critical files
- `third_party/imgui_markdown/imgui_markdown.h` + `LICENSE` (new, vendored).
- [`CMakeLists.txt`](../../WorldFoundry.2026-new-level/CMakeLists.txt) — `IMGUI_MARKDOWN_DIR` + one include-dir line (editor block).
- [`engine/wf_edit/main.cc`](../../WorldFoundry.2026-new-level/engine/wf_edit/main.cc) — include, `MarkdownConfig`, the 1011-1015 render swap, the `WF_EDIT_CHAT_DEMO` hook.

## Verification
- **Build:** `cmake --build build-editor --target wf_edit` (Debug dir used successfully this
  session; `wf-edit` is only the OUTPUT_NAME). Confirm exit 0 + binary mtime advances.
- **Screenshot proof** (per the screenshots-as-proof rule): `DISPLAY=:0
  WF_EDIT_CHAT_DEMO=1 ./build-editor/wf-edit --select=0 --screenshot
  tests/screenshots/chat_markdown.ppm --frames 40` (run backgrounded; PPM→PNG via PIL),
  then view it — expect the sample message rendering bold/heading/list, not literal `**`/`#`.
  Commit the PNG beside the diff.
- **Game runtime untouched:** editor-only; `git diff` shows no `wfsource/` change; `wf_game`
  still builds.

## Out of scope (noted follow-ups)
- `SHOW_AS_TEXTEDITOR` Notes-leaf markdown (it's an editor, not a display) — the other half
  of the TODO item.
- Custom heading fonts (bigger/bold H1) — needs a font atlas add; default font is fine v1.
- `xdg-open` on link click — v1 links render styled but inert.
