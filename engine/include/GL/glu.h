/* Minimal GLU stub — provides declarations; links against libGLU.so.1 */
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
#include <GL/gl.h>
const GLubyte* gluErrorString(GLenum error);
void gluPerspective(GLdouble fovy, GLdouble aspect, GLdouble zNear, GLdouble zFar);
void gluLookAt(GLdouble eyeX,  GLdouble eyeY,  GLdouble eyeZ,
               GLdouble centX, GLdouble centY, GLdouble centZ,
               GLdouble upX,   GLdouble upY,   GLdouble upZ);
GLint gluBuild2DMipmaps(GLenum target, GLint components, GLsizei width, GLsizei height,
                        GLenum format, GLenum type, const void* data);
void gluOrtho2D(GLdouble left, GLdouble right, GLdouble bottom, GLdouble top);
#ifdef __cplusplus
}
#endif
