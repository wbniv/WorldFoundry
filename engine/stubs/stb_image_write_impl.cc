//==============================================================================
// engine/stubs/stb_image_write_impl.cc — the single translation unit that
// instantiates the vendored stb_image_write single-header PNG encoder.
//
// It used to live inside debug_server.cc, whose entire body is wrapped in
// `#ifdef WF_DEBUG_BRIDGE`. That made the PNG encoder silently disappear
// whenever the bridge was off — fine while the bridge was its only consumer,
// wrong as soon as a second one appeared: the macOS offscreen frame capture
// (--capture-frame, Phase 2 of docs/plans/2026-09-20-macos-metal-renderer.md)
// needs stbi_write_png with or without the bridge.
//
// So the implementation moves here, unconditionally compiled, and every
// consumer just includes the header. Exactly one TU may define
// STB_IMAGE_WRITE_IMPLEMENTATION — this one.
//==============================================================================

#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STBI_WRITE_NO_STDIO_FILESYSTEM 0
#include "../vendor/stb/stb_image_write.h"
