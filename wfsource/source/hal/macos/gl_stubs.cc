//=============================================================================
// hal/macos/gl_stubs.cc: no-op GL symbols for the headless macOS desktop build
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Clone of hal/ios/gl_stubs.cc. gfx/pixelmap.cc (and pixelmap.hpi) still call
// a handful of GL entry points directly during LoadLevel (texture upload). The
// renderer-agnostic macOS build does NOT link OpenGL.framework (rendering is a
// true no-op), so these stubs satisfy the link-time references. PixelMap
// textures end up as unused CPU-side allocations; the real texture-upload path
// lands with the Metal renderer later.
//
// We include <OpenGL/gl.h> only for the GL type/constant *vocabulary*
// (GLuint, GLenum, GL_NO_ERROR, …) so the stub signatures match what
// gfx/renderer.hp's macOS arm declares to pixelmap.cc. glGetError returns
// GL_NO_ERROR so AssertGLOK passes silently.
//=============================================================================

#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl.h>

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
