"""Compile and link every built-in desktop GL style variant on a real driver."""
import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "wfsource/source/gfx/glpipeline/backend_modern.cc"


def _shader(name, source):
    body = source.split(f"static const char* {name} =", 1)[1].split(";\n\n", 1)[0]
    # Shader literals occupy their own C++ lines; ignore surrounding comments.
    return "".join(ast.literal_eval(m.group(1)) for line in body.splitlines()
                   if (m := re.match(r'^\s*("(?:[^"\\]|\\.)*")', line)))


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires an X11 GL context")
def test_builtin_style_variants_compile_and_link(tmp_path):
    source = BACKEND.read_text()
    vertex, fragment = _shader("kVS", source), _shader("kFS", source)
    assert "void main()" in vertex and "void main()" in fragment
    assert "u_absorb" in vertex and "u_toon_bands" in fragment and "u_caustic" in fragment
    runner = tmp_path / "compile.cc"
    runner.write_text(r'''
#define GL_GLEXT_PROTOTYPES 1
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <fstream>
#include <iterator>
#include <iostream>
#include <string>
static GLuint compile(GLenum type, const char* path) {
    std::ifstream in(path); std::string src((std::istreambuf_iterator<char>(in)), {});
    const char* p = src.c_str(); GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &p, nullptr); glCompileShader(shader);
    GLint ok=0; glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[8192]={}; glGetShaderInfoLog(shader,sizeof log,nullptr,log); std::cerr << log; return 0; }
    return shader;
}
int main(int argc, char** argv) {
    if (argc != 3 && argc != 4) return 2;
    Display* d = XOpenDisplay(nullptr); if (!d) return 3;
    int attrs[] = {GLX_RGBA, GLX_DOUBLEBUFFER, None};
    XVisualInfo* v = glXChooseVisual(d, DefaultScreen(d), attrs); if (!v) return 4;
    XSetWindowAttributes a = {}; a.colormap = XCreateColormap(d, RootWindow(d,v->screen), v->visual, AllocNone);
    Window w = XCreateWindow(d,RootWindow(d,v->screen),0,0,16,16,0,v->depth,InputOutput,v->visual,CWColormap,&a);
    XMapWindow(d,w); XSync(d,False);
    GLXContext c = glXCreateContext(d,v,nullptr,True); if (!c || !glXMakeCurrent(d,w,c)) return 5;
    GLuint vs=compile(GL_VERTEX_SHADER,argv[1]), fs=compile(GL_FRAGMENT_SHADER,argv[2]);
    if (!vs || !fs) return 6;
    GLuint p=glCreateProgram(); glAttachShader(p,vs); glAttachShader(p,fs); glLinkProgram(p);
    GLint ok=0; glGetProgramiv(p,GL_LINK_STATUS,&ok);
    if (!ok) { char log[8192]={}; glGetProgramInfoLog(p,sizeof log,nullptr,log); std::cerr << log; return 7; }
    if (argc == 4) {
        glUseProgram(p);
        const float identity[] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
        for (auto name : {"u_mvp", "u_mv", "u_eye_to_world"})
            glUniformMatrix4fv(glGetUniformLocation(p,name),1,GL_FALSE,identity);
        const float positions[] = {-1,-1,-0.5f, 1,-1,-0.5f, 0,1,-0.5f};
        GLuint vao=0,vbo=0; glGenVertexArrays(1,&vao); glBindVertexArray(vao);
        glGenBuffers(1,&vbo); glBindBuffer(GL_ARRAY_BUFFER,vbo);
        glBufferData(GL_ARRAY_BUFFER,sizeof positions,positions,GL_STATIC_DRAW);
        glEnableVertexAttribArray(0); glVertexAttribPointer(0,3,GL_FLOAT,GL_FALSE,0,nullptr);
        glVertexAttrib4f(1,1,1,1,1); glVertexAttrib3f(3,0,0,1); glVertexAttrib1f(4,1);
        glViewport(0,0,16,16); glDisable(GL_DITHER); glDisable(GL_BLEND); glDisable(GL_DEPTH_TEST);
        glUniform1i(glGetUniformLocation(p,"u_use_tex"),0);
        glUniform1i(glGetUniformLocation(p,"u_fog"),1);
        glUniform1f(glGetUniformLocation(p,"u_fog_start"),0); glUniform1f(glGetUniformLocation(p,"u_fog_end"),10);
        glUniform3f(glGetUniformLocation(p,"u_fog_color"),0,0,0);
        glUniform3f(glGetUniformLocation(p,"u_absorb"),2,0.1f,0);
        glDrawArrays(GL_TRIANGLES,0,3); glFinish(); unsigned char rgba[4];
        glReadPixels(8,8,1,1,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
        // Absorption is evaluated at vertices then interpolated: vertices have
        // differing eye distances, so the centre is not exp(-k * 0.5).
        if (!(rgba[0] > 0 && rgba[0] < 60 && rgba[1] > 200 && rgba[1] < 250 && rgba[2] > 245)) {
            std::cerr << "absorption pixel " << int(rgba[0]) << ',' << int(rgba[1]) << ',' << int(rgba[2]); return 8;
        }
        glUniform3f(glGetUniformLocation(p,"u_absorb"),0,0,0);
        glUniform1i(glGetUniformLocation(p,"u_fog"),0);
        glUniform1i(glGetUniformLocation(p,"u_lighting"),1);
        glUniform3f(glGetUniformLocation(p,"u_ambient"),0.4f,0.4f,0.4f);
        glUniform1i(glGetUniformLocation(p,"u_toon_bands"),3);
        glDrawArrays(GL_TRIANGLES,0,3); glFinish(); glReadPixels(8,8,1,1,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
        if (!(rgba[0] >= 80 && rgba[0] <= 90)) { std::cerr << "toon pixel " << int(rgba[0]); return 9; }
        glUniform1i(glGetUniformLocation(p,"u_toon_bands"),0);
        glUniform1i(glGetUniformLocation(p,"u_fog"),1);
        glUniform3f(glGetUniformLocation(p,"u_caustic"),0.6f,1.0f,0);
        glDrawArrays(GL_TRIANGLES,0,3); glFinish(); glReadPixels(8,8,1,1,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
        if (rgba[0] < 130) { std::cerr << "caustic pixel " << int(rgba[0]); return 10; }
    }
    return 0;
}
''')
    binary = tmp_path / "compile"
    subprocess.run(["c++", "-std=c++17", str(runner), "-lGL", "-lX11", "-o", str(binary)], check=True, timeout=30)
    for style in (False, True):
        for defines in ("", "#define WF_OPAQUE 1\n", "#define WF_OPAQUE 1\n#define WF_TEX_MODE 1\n",
                        "#define WF_OPAQUE 1\n#define WF_TEX_MODE 1\n#define WF_NO_PALETTE 1\n"):
            prefix = "#version 330 core\n" + ("#define WF_STYLE 1\n" if style else "")
            vs, fs = tmp_path / "shader.vert", tmp_path / "shader.frag"
            vs.write_text(prefix + vertex)
            fs.write_text(prefix + defines + fragment)
            cmd = [str(binary), str(vs), str(fs)]
            if style and not defines:
                cmd.append("pixels")
            subprocess.run(cmd, check=True, timeout=30)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires an X11 EGL display")
def test_builtin_style_variants_compile_and_link_gles3(tmp_path):
    source = BACKEND.read_text()
    vertex, fragment = _shader("kVS", source), _shader("kFS", source)
    assert "u_absorb" in vertex and "u_toon_bands" in fragment and "u_caustic" in fragment
    runner = tmp_path / "compile-es.cc"
    runner.write_text(r'''
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <fstream>
#include <iterator>
#include <iostream>
#include <string>
static GLuint compile(GLenum type, const char* path) {
    std::ifstream in(path); std::string src((std::istreambuf_iterator<char>(in)), {});
    const char* p=src.c_str(); GLuint shader=glCreateShader(type);
    glShaderSource(shader,1,&p,nullptr); glCompileShader(shader);
    GLint ok=0; glGetShaderiv(shader,GL_COMPILE_STATUS,&ok);
    if(!ok) { char log[8192]={}; glGetShaderInfoLog(shader,sizeof log,nullptr,log); std::cerr << log; return 0; }
    return shader;
}
int main(int argc, char** argv) {
    if(argc!=3) return 2;
    EGLDisplay d=eglGetDisplay(EGL_DEFAULT_DISPLAY); EGLint major,minor;
    if(d==EGL_NO_DISPLAY || !eglInitialize(d,&major,&minor) || !eglBindAPI(EGL_OPENGL_ES_API)) return 3;
    EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_NONE};
    EGLConfig cfg; EGLint count=0; if(!eglChooseConfig(d,attrs,&cfg,1,&count) || count<1) return 4;
    EGLint ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE}; EGLContext c=eglCreateContext(d,cfg,EGL_NO_CONTEXT,ca);
    EGLint pa[]={EGL_WIDTH,16,EGL_HEIGHT,16,EGL_NONE}; EGLSurface s=eglCreatePbufferSurface(d,cfg,pa);
    if(c==EGL_NO_CONTEXT || s==EGL_NO_SURFACE || !eglMakeCurrent(d,s,s,c)) return 5;
    GLuint vs=compile(GL_VERTEX_SHADER,argv[1]), fs=compile(GL_FRAGMENT_SHADER,argv[2]); if(!vs || !fs) return 6;
    GLuint p=glCreateProgram(); glAttachShader(p,vs); glAttachShader(p,fs); glLinkProgram(p);
    GLint ok=0; glGetProgramiv(p,GL_LINK_STATUS,&ok);
    if(!ok) { char log[8192]={}; glGetProgramInfoLog(p,sizeof log,nullptr,log); std::cerr << log; return 7; }
    return 0;
}
''')
    binary = tmp_path / "compile-es"
    subprocess.run(["c++", "-std=c++17", str(runner), "-lEGL", "-lGLESv2", "-o", str(binary)], check=True, timeout=30)
    for style in (False, True):
        for defines in ("", "#define WF_OPAQUE 1\n", "#define WF_OPAQUE 1\n#define WF_TEX_MODE 1\n",
                        "#define WF_OPAQUE 1\n#define WF_TEX_MODE 1\n#define WF_NO_PALETTE 1\n"):
            prefix = "#version 300 es\nprecision highp float;\nprecision highp int;\n" + ("#define WF_STYLE 1\n" if style else "")
            vs, fs = tmp_path / "shader.vert", tmp_path / "shader.frag"
            vs.write_text(prefix + vertex)
            fs.write_text(prefix + defines + fragment)
            subprocess.run([str(binary), str(vs), str(fs)], check=True, timeout=30)
