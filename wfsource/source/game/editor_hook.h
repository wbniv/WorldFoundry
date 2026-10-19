//=============================================================================
// game/editor_hook.h — editor embedding hook (approach (a)).
//
// The external editor app (wf-edit) registers two per-frame callbacks before
// HALStart; PIGSMain's `--editor` mode then drives the engine via
// WFGame::RunEditor, which each iteration runs:
//
//     build(ctx)         — editor polls input, builds its Dear ImGui UI, and
//                          applies pending edits to the live engine;
//     StepFrame(false)   — engine renders the (now up-to-date) scene, no swap;
//     present(ctx)       — editor composites its ImGui overlay and swaps.
//
// Build runs BEFORE the engine render so a same-frame edit is visible the same
// frame (no render-ahead-of-edit latency); present runs after so the ImGui
// overlay lands on top of the freshly rendered scene. This keeps Dear ImGui out
// of the engine — the engine sees only opaque function pointers. (b) decomposing
// HALStart into HALInit/HALShutdown so the editor owns the loop outright is a
// TODO; see docs/plans/2026-05-20-editor-app-shell.md and the latency reorder in
// docs/plans/2026-05-25-wf-edit-zero-latency-local-edits.md.
//=============================================================================

#ifndef _GAME_EDITOR_HOOK_H
#define _GAME_EDITOR_HOOK_H

#if defined(__cplusplus)
extern "C" {
#endif

// Build phase — runs at the TOP of each iteration, before StepFrame. The editor
// polls input, builds its Dear ImGui UI, and applies any pending edits to the
// live engine, so the StepFrame render that follows reflects them this frame.
// Return false to end the editor loop (e.g. the window was closed); on a false
// return the loop breaks before StepFrame/present, so the editor must NOT have
// opened an unbalanced ImGui frame (return before ImGui::NewFrame).
// `ctx` is the editor's opaque pointer.
typedef bool (*EditorBuildCallback)(void* ctx);

// Present phase — runs after StepFrame has rendered the scene into the back
// buffer (do_swap=false). The editor composites its ImGui overlay on top and
// performs the buffer swap. Called only when build returned true.
typedef void (*EditorPresentCallback)(void* ctx);

// Register the per-frame callbacks. Call before HALStart. Passing null build
// makes WFGame::RunEditor a no-op loop body (engine still steps + swaps).
void SetEditorFrameCallbacks(EditorBuildCallback build,
                             EditorPresentCallback present, void* ctx);

#if defined(__cplusplus)
}
#endif

#endif // _GAME_EDITOR_HOOK_H
