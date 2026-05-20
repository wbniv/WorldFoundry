//=============================================================================
// game/editor_hook.h — editor embedding hook (approach (a)).
//
// The external editor app (wf-edit) registers a per-frame UI callback before
// HALStart; PIGSMain's `--editor` mode then drives the engine via
// WFGame::RunEditor, which each frame renders the engine (StepFrame, no swap)
// and calls back so the editor composites its Dear ImGui UI on top and swaps.
//
// This keeps Dear ImGui out of the engine — the engine sees only an opaque
// "draw one frame" function pointer. (b) decomposing HALStart into
// HALInit/HALShutdown so the editor owns the loop outright is a TODO; see
// docs/plans/2026-05-20-editor-app-shell.md and TODO.md (COLLABORATIVE EDITOR).
//=============================================================================

#ifndef _GAME_EDITOR_HOOK_H
#define _GAME_EDITOR_HOOK_H

#if defined(__cplusplus)
extern "C" {
#endif

// Per-frame editor UI callback. Called after the engine has rendered the frame
// into the back buffer (StepFrame with do_swap=false); the editor composites
// its UI and performs the buffer swap. Return false to end the editor loop
// (e.g. the editor window was closed). `ctx` is the editor's opaque pointer.
typedef bool (*EditorFrameCallback)(void* ctx);

// Register the per-frame callback. Call before HALStart. Passing null fn
// makes WFGame::RunEditor a no-op loop body (engine still steps + swaps).
void SetEditorFrameCallback(EditorFrameCallback fn, void* ctx);

#if defined(__cplusplus)
}
#endif

#endif // _GAME_EDITOR_HOOK_H
