//=============================================================================
// hal/ios/gl_stubs.cc: no-op GLES symbols for the iOS Metal build
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2C-A: gfx/pixelmap.cc (and gfx/pixelmap.hpi) still call a handful of
// GLES 3 entry points directly. On iOS we render through Metal, not GL, so
// OpenGLES.framework is intentionally NOT linked. These stubs satisfy the
// link-time references so the binary can boot the engine thread.
//
// PixelMap textures end up as unused CPU-side allocations on iOS; the real
// Metal texture upload path lands when RendererBackend_Metal grows a
// PixelMap-aware binding in a later phase.
//
// glGetError returns GL_NO_ERROR so AssertGLOK passes silently.
//=============================================================================

#include <OpenGLES/ES3/gl.h>

extern "C" {

void glGenTextures(GLsizei n, GLuint* textures)
{
    for (GLsizei i = 0; i < n; ++i) textures[i] = 1;  // non-zero so asserts pass
}

void glDeleteTextures(GLsizei /*n*/, const GLuint* /*textures*/) {}
void glBindTexture(GLenum /*target*/, GLuint /*texture*/) {}
void glTexParameteri(GLenum /*target*/, GLenum /*pname*/, GLint /*param*/) {}

void glTexImage2D(GLenum /*target*/, GLint /*level*/, GLint /*internalformat*/,
                  GLsizei /*width*/, GLsizei /*height*/, GLint /*border*/,
                  GLenum /*format*/, GLenum /*type*/, const void* /*pixels*/) {}

void glEnable(GLenum /*cap*/) {}

GLenum glGetError(void) { return GL_NO_ERROR; }

}  // extern "C"
