//=============================================================================
// gfx/metal/metal_offscreen.h: windowless Metal render target
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2 of docs/plans/2026-09-20-macos-metal-renderer.md: render a frame
// through real Metal with no window and no CAMetalDrawable, then read it back.
//
// Deliberately PURE C++ — no Metal, no Objective-C — because its caller,
// hal/macos/display_macos.cc, is #included into gfx/display.cc and compiles as
// plain C++. The implementation lives in backend_metal.mm alongside the device
// and pipeline that own the textures.
//
// This is NOT a throwaway CI harness. Plan O2: the editor's viewport embed
// needs exactly this surface — an engine-owned MTLTexture the host composites
// rather than a window the engine drives — and it replaces the GLX-typed
// gfx/host_gl_context.h on Apple. ColorTextureHandle() is in this interface for
// that reason and for no current consumer: --capture-frame goes through
// ReadbackRGBA8 instead. Keep the two separate; the editor must not have to go
// through a CPU readback to show a frame.
//
// Lifecycle, once per frame:
//     BeginFrame(w, h)   -> (re)creates the colour + depth textures on a size
//                           change, opens a command buffer + render encoder,
//                           and hands the encoder to the Metal backend
//     ... engine draws ... RendererBackendGet().EndFrame() flushes the batch
//     EndFrame()         -> ends encoding, commits, waits for completion
//     ReadbackRGBA8(...) -> optional; only the captured frame pays for it
//=============================================================================

#ifndef _WF_METAL_OFFSCREEN_H
#define _WF_METAL_OFFSCREEN_H

namespace wf_metal
{

// True once a device + pipeline exist. False on a machine with no Metal device,
// which is a legitimate outcome the caller must degrade gracefully on rather
// than abort — a headless CI box without a GPU should still run the smoke.
bool Available();

// Size (or resize) the offscreen attachments and open this frame's encoder.
// Returns false if Metal is unavailable or target creation failed; the caller
// should then skip the frame's draw calls rather than issue them into nothing.
bool BeginFrame(int width, int height);

// Close the encoder, commit, and block until the GPU is done. After this the
// colour attachment holds the finished frame.
void EndFrame();

// Copy the colour attachment into `dst` as tightly-packed RGBA8, top row first
// (`dst` must hold width*height*4 bytes). Metal renders BGRA, so this swizzles.
// Returns false if there is no completed frame of that size to read.
bool ReadbackRGBA8(unsigned char* dst, int width, int height);

// The live colour attachment as an opaque handle (an id<MTLTexture>). Null
// until BeginFrame has succeeded once. For the editor viewport handshake (O2);
// the frame capture does not use it.
void* ColorTextureHandle();

// Frame/triangle accounting, so a caller can report how many frames actually
// reached the backend versus how many the engine stepped. Phase 1 measured
// 1563 triangles/frame on the headless backend and found 29 rendered frames for
// 30 engine steps without being able to say which step was skipped; these let
// display_macos.cc report both numbers side by side.
unsigned long RenderedFrameCount();
unsigned long TrianglesLastFrame();
unsigned long TrianglesTotal();

}  // namespace wf_metal

//=============================================================================
#endif  // _WF_METAL_OFFSCREEN_H
//=============================================================================
