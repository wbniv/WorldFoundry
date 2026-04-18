//=============================================================================
// gfx/glpipeline/backend_modern.cc: VBO + shader backend for renderer seam
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// GLES-3.0-compatible replacement for backend_legacy.cc. Accumulates triangles
// into a host-side buffer, uploads + draws on state change (matrix, texture)
// or at EndFrame. MVP is computed CPU-side and passed as a uniform.
//
// Works on desktop OpenGL 3.3+ and Android GLES 3.0; shader preamble is
// conditional on the platform.
//============================================================================

// On Linux/Mesa, GL 3.3+ function prototypes are gated behind this macro in
// <GL/glext.h>. Define before any header that might pull in <GL/gl.h>, or
// the prototypes go missing once gl.h's include-guard fires.
#if !defined(__ANDROID__)
#  define GL_GLEXT_PROTOTYPES 1
#endif

#if defined(__ANDROID__)
#  include <GLES3/gl3.h>
#else
#  include <GL/gl.h>
#  include <GL/glext.h>
#endif

#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#include <math/matrix34.hp>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace
{

#if defined(__ANDROID__)
static const char* kShaderHeader = "#version 300 es\nprecision highp float;\n";
#else
static const char* kShaderHeader = "#version 330 core\n";
#endif

static const char* kVS =
    "layout(location=0) in vec3 a_pos;\n"
    "layout(location=1) in vec3 a_color;\n"
    "layout(location=2) in vec2 a_uv;\n"
    "layout(location=3) in vec3 a_normal;\n"
    "out vec3 v_color;\n"
    "out vec2 v_uv;\n"
    "out vec3 v_lit;\n"
    "uniform mat4 u_mvp;\n"
    "uniform mat4 u_mv;\n"
    "uniform int  u_lighting;\n"
    "uniform vec3 u_ambient;\n"
    "uniform vec3 u_light_dir[3];\n"
    "uniform vec3 u_light_color[3];\n"
    "void main()\n"
    "{\n"
    "    gl_Position = u_mvp * vec4(a_pos, 1.0);\n"
    "    v_color = a_color;\n"
    "    v_uv = a_uv;\n"
    "    if (u_lighting != 0) {\n"
    "        vec3 N = normalize((u_mv * vec4(a_normal, 0.0)).xyz);\n"
    "        vec3 lit = u_ambient;\n"
    "        for (int i = 0; i < 3; ++i) {\n"
    "            lit += u_light_color[i] * max(0.0, dot(N, u_light_dir[i]));\n"
    "        }\n"
    "        v_lit = lit;\n"
    "    } else {\n"
    "        v_lit = vec3(1.0);\n"
    "    }\n"
    "}\n";

static const char* kFS =
    "in vec3 v_color;\n"
    "in vec2 v_uv;\n"
    "in vec3 v_lit;\n"
    "out vec4 frag;\n"
    "uniform sampler2D u_tex;\n"
    "uniform int u_use_tex;\n"
    "void main()\n"
    "{\n"
    "    vec4 c = vec4(v_color * v_lit, 1.0);\n"
    "    if (u_use_tex != 0) c = c * texture(u_tex, v_uv);\n"
    "    frag = c;\n"
    "}\n";

struct Vert
{
    float x, y, z;
    float r, g, b;
    float u, v;
    float nx, ny, nz;
};

// ---- matrix helpers (all column-major, GL convention) -----------------------

static void Mat4Identity(float m[16])
{
    std::memset(m, 0, sizeof(float) * 16);
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

static void Mat4Perspective(float fovDegY, float aspect, float nz, float fz,
                            float out[16])
{
    const float f = 1.0f / std::tan((fovDegY * 0.5f) * (3.14159265358979323846f / 180.0f));
    std::memset(out, 0, sizeof(float) * 16);
    out[0]  = f / aspect;
    out[5]  = f;
    out[10] = (fz + nz) / (nz - fz);
    out[11] = -1.0f;
    out[14] = (2.0f * fz * nz) / (nz - fz);
}

// out = a * b, column-major.
static void Mat4Multiply(const float a[16], const float b[16], float out[16])
{
    float r[16];
    for (int c = 0; c < 4; ++c)
        for (int rr = 0; rr < 4; ++rr)
            r[c*4+rr] = a[0*4+rr]*b[c*4+0] + a[1*4+rr]*b[c*4+1]
                      + a[2*4+rr]*b[c*4+2] + a[3*4+rr]*b[c*4+3];
    std::memcpy(out, r, sizeof(r));
}

// Convert Matrix34 (WF's 3x4 row-major-ish) to GL 4x4 column-major. Same
// mapping as display.cc's LoadGLMatrixFromMatrix34 helper.
static void Matrix34ToFloat16(const Matrix34& matrix, float out[16])
{
    out[0]  = matrix[0][0].AsFloat();
    out[1]  = matrix[0][1].AsFloat();
    out[2]  = matrix[0][2].AsFloat();
    out[3]  = 0.0f;

    out[4]  = matrix[1][0].AsFloat();
    out[5]  = matrix[1][1].AsFloat();
    out[6]  = matrix[1][2].AsFloat();
    out[7]  = 0.0f;

    out[8]  = matrix[2][0].AsFloat();
    out[9]  = matrix[2][1].AsFloat();
    out[10] = matrix[2][2].AsFloat();
    out[11] = 0.0f;

    out[12] = matrix[3][0].AsFloat();
    out[13] = matrix[3][1].AsFloat();
    out[14] = matrix[3][2].AsFloat();
    out[15] = 1.0f;
}

// ---- shader compile helpers -------------------------------------------------

static GLuint CompileShader(GLenum type, const char* src)
{
    const char* parts[2] = { kShaderHeader, src };
    GLuint s = glCreateShader(type);
    glShaderSource(s, 2, parts, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok)
    {
        char log[2048] = { 0 };
        glGetShaderInfoLog(s, sizeof(log) - 1, nullptr, log);
        std::fprintf(stderr, "modern backend: shader compile failed:\n%s\n", log);
        glDeleteShader(s);
        std::abort();
    }
    return s;
}

static GLuint LinkProgram(GLuint vs, GLuint fs)
{
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok)
    {
        char log[2048] = { 0 };
        glGetProgramInfoLog(p, sizeof(log) - 1, nullptr, log);
        std::fprintf(stderr, "modern backend: program link failed:\n%s\n", log);
        glDeleteProgram(p);
        std::abort();
    }
    glDetachShader(p, vs);
    glDetachShader(p, fs);
    return p;
}

// ---- the backend ------------------------------------------------------------

class ModernRendererBackend : public RendererBackend
{
public:
    ModernRendererBackend()
    {
        Mat4Identity(_proj);
        Mat4Identity(_mv);
        Mat4Identity(_mvp);
        _ambient[0] = _ambient[1] = _ambient[2] = 0.0f;
        for (int i = 0; i < RB_MAX_LIGHTS; ++i)
        {
            _lightDir[i][0] = _lightDir[i][1] = 0.0f;
            _lightDir[i][2] = 1.0f;
            _lightColor[i][0] = _lightColor[i][1] = _lightColor[i][2] = 0.0f;
        }
    }

    void SetProjection(float fovDegY, float aspect,
                       float nearZ, float farZ) override
    {
        Flush();
        Mat4Perspective(fovDegY, aspect, nearZ, farZ, _proj);
        _mvpDirty = true;
    }

    void SetModelView(const Matrix34& m) override
    {
        Flush();
        Matrix34ToFloat16(m, _mv);
        _mvpDirty = true;
    }

    void ResetModelView() override
    {
        Flush();
        Mat4Identity(_mv);
        _mvpDirty = true;
    }

    void SetAmbient(float r, float g, float b) override
    {
        Flush();
        _ambient[0] = r;
        _ambient[1] = g;
        _ambient[2] = b;
    }

    void SetDirLight(int index,
                     float dirX, float dirY, float dirZ,
                     float r, float g, float b) override
    {
        if (index < 0 || index >= RB_MAX_LIGHTS) return;
        Flush();
        // Transform world-space direction into eye space using current mv's
        // upper 3x3 (GL fixed-function does this via glLightfv GL_POSITION).
        const float ex = _mv[0]*dirX + _mv[4]*dirY + _mv[8]*dirZ;
        const float ey = _mv[1]*dirX + _mv[5]*dirY + _mv[9]*dirZ;
        const float ez = _mv[2]*dirX + _mv[6]*dirY + _mv[10]*dirZ;
        const float len = std::sqrt(ex*ex + ey*ey + ez*ez);
        const float inv = (len > 1e-6f) ? (1.0f / len) : 1.0f;
        _lightDir[index][0] = ex * inv;
        _lightDir[index][1] = ey * inv;
        _lightDir[index][2] = ez * inv;
        _lightColor[index][0] = r;
        _lightColor[index][1] = g;
        _lightColor[index][2] = b;
    }

    void SetLightingEnabled(bool enabled) override
    {
        Flush();
        _lightingEnabled = enabled;
    }

    void DrawTriangle(const RBVertex& v0,
                      const RBVertex& v1,
                      const RBVertex& v2,
                      float nx, float ny, float nz,
                      const PixelMap* texture) override
    {
        if (texture != _curTexture && !_cpu.empty())
            Flush();
        _curTexture = texture;

        Vert tri[3];
        Pack(tri[0], v0, nx, ny, nz);
        Pack(tri[1], v1, nx, ny, nz);
        Pack(tri[2], v2, nx, ny, nz);
        _cpu.push_back(tri[0]);
        _cpu.push_back(tri[1]);
        _cpu.push_back(tri[2]);
    }

    void EndFrame() override
    {
        Flush();
    }

private:
    bool   _inited   = false;
    GLuint _vao      = 0;
    GLuint _vbo      = 0;
    GLuint _prog     = 0;
    GLint  _uMvp        = -1;
    GLint  _uMv         = -1;
    GLint  _uTex        = -1;
    GLint  _uUseTex     = -1;
    GLint  _uLighting   = -1;
    GLint  _uAmbient    = -1;
    GLint  _uLightDir   = -1;
    GLint  _uLightColor = -1;

    float _proj[16];
    float _mv[16];
    float _mvp[16];
    bool  _mvpDirty  = true;

    bool  _lightingEnabled = false;
    float _ambient[3];
    float _lightDir  [RB_MAX_LIGHTS][3];
    float _lightColor[RB_MAX_LIGHTS][3];

    const PixelMap* _curTexture = nullptr;
    std::vector<Vert> _cpu;

    static void Pack(Vert& dst, const RBVertex& v,
                     float nx, float ny, float nz)
    {
        dst.x = v.x; dst.y = v.y; dst.z = v.z;
        dst.r = v.r; dst.g = v.g; dst.b = v.b;
        dst.u = v.u; dst.v = v.v;
        dst.nx = nx; dst.ny = ny; dst.nz = nz;
    }

    void LazyInit()
    {
        if (_inited) return;

        GLuint vs = CompileShader(GL_VERTEX_SHADER,   kVS);
        GLuint fs = CompileShader(GL_FRAGMENT_SHADER, kFS);
        _prog = LinkProgram(vs, fs);
        glDeleteShader(vs);
        glDeleteShader(fs);

        _uMvp        = glGetUniformLocation(_prog, "u_mvp");
        _uMv         = glGetUniformLocation(_prog, "u_mv");
        _uTex        = glGetUniformLocation(_prog, "u_tex");
        _uUseTex     = glGetUniformLocation(_prog, "u_use_tex");
        _uLighting   = glGetUniformLocation(_prog, "u_lighting");
        _uAmbient    = glGetUniformLocation(_prog, "u_ambient");
        _uLightDir   = glGetUniformLocation(_prog, "u_light_dir");
        _uLightColor = glGetUniformLocation(_prog, "u_light_color");

        glGenVertexArrays(1, &_vao);
        glGenBuffers(1, &_vbo);
        glBindVertexArray(_vao);
        glBindBuffer(GL_ARRAY_BUFFER, _vbo);

        const GLsizei stride = sizeof(Vert);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride,
                              (void*)offsetof(Vert, x));
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride,
                              (void*)offsetof(Vert, r));
        glEnableVertexAttribArray(2);
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride,
                              (void*)offsetof(Vert, u));
        glEnableVertexAttribArray(3);
        glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, stride,
                              (void*)offsetof(Vert, nx));

        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);

        _inited = true;
    }

    void UpdateMvp()
    {
        if (!_mvpDirty) return;
        Mat4Multiply(_proj, _mv, _mvp);
        _mvpDirty = false;
    }

    void Flush()
    {
        if (_cpu.empty())
        {
            _curTexture = nullptr;
            return;
        }
        LazyInit();
        UpdateMvp();

        glUseProgram(_prog);
        glUniformMatrix4fv(_uMvp, 1, GL_FALSE, _mvp);
        glUniformMatrix4fv(_uMv,  1, GL_FALSE, _mv);
        glUniform1i(_uLighting, _lightingEnabled ? 1 : 0);
        glUniform3fv(_uAmbient, 1, _ambient);
        glUniform3fv(_uLightDir,   RB_MAX_LIGHTS, &_lightDir[0][0]);
        glUniform3fv(_uLightColor, RB_MAX_LIGHTS, &_lightColor[0][0]);

        if (_curTexture)
        {
            glActiveTexture(GL_TEXTURE0);
            _curTexture->SetGLTexture();
            glUniform1i(_uTex, 0);
            glUniform1i(_uUseTex, 1);
        }
        else
        {
            glUniform1i(_uUseTex, 0);
        }

        glBindVertexArray(_vao);
        glBindBuffer(GL_ARRAY_BUFFER, _vbo);
        glBufferData(GL_ARRAY_BUFFER,
                     GLsizeiptr(_cpu.size() * sizeof(Vert)),
                     _cpu.data(),
                     GL_STREAM_DRAW);
        glDrawArrays(GL_TRIANGLES, 0, GLsizei(_cpu.size()));

        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glUseProgram(0);

        _cpu.clear();
        _curTexture = nullptr;
    }
};

ModernRendererBackend sModernBackend;

}  // namespace

RendererBackend* ModernBackendInstance()
{
    return &sModernBackend;
}
