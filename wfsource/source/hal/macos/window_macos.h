//=============================================================================
// hal/macos/window_macos.h: GLFW window host for macOS desktop
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 4 of docs/plans/2026-09-20-macos-metal-renderer.md, decision D5/O4:
// GLFW rather than a bespoke AppKit host, so wf_game and wf_edit share one
// windowing and input path on macOS and gamepad support comes for free.
//
// Pure C++ like gfx/metal/metal_offscreen.h, and for the same reason: the
// caller (hal/macos/display_macos.cc, #included into gfx/display.cc) compiles
// as plain C++. The CAMetalLayer lives behind an opaque void* and the
// Objective-C stays in window_macos.mm.
//
// EVERYTHING HERE IS FAIL-SOFT. Create() returning false is a supported
// outcome, not an error: a CI runner with no window-server session cannot make
// a window, and the headless --frame-step-smoke path must keep working exactly
// as it did in Phases 2-3. Callers check Exists() and fall back to the
// offscreen target; they never assume a window.
//=============================================================================

#ifndef _WF_WINDOW_MACOS_H
#define _WF_WINDOW_MACOS_H

namespace wf_macos_window
{

// Create the window and attach a CAMetalLayer to its content view. Returns
// false — without aborting — if GLFW cannot initialise or the window cannot be
// created, which is the expected result on a headless build machine.
bool Create(int width, int height, bool fullscreen, const char* title);

// True once Create() has succeeded. The renderer uses this to choose between
// presenting a drawable and rendering to the offscreen target.
bool Exists();

// The CAMetalLayer, as an opaque handle for gfx/metal. Null when !Exists().
void* MetalLayer();

// Pump the event queue once per frame. No-op when !Exists().
void PollEvents();

// Backing-store size in PIXELS, which on a Retina display is not the window
// size in points. This is what the Metal drawable and the viewport must use;
// mixing the two is the classic half-resolution / quarter-screen bug.
void GetDrawableSize(int& width, int& height);

// True once the user has asked to close (red button, Cmd-Q). Polled by the
// engine through HALWindowCloseRequested.
bool CloseRequested();

// Apply -width/-height/-fullscreen after creation (TODO.md:7).
void SetSize(int width, int height);
void SetFullscreen(bool fullscreen);

void Destroy();

}  // namespace wf_macos_window

//=============================================================================
#endif  // _WF_WINDOW_MACOS_H
//=============================================================================
