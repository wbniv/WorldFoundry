#include <game/runtime_profile.hp>
//=============================================================================
// gfx/glpipeline/backend_modern.cc: VBO + shader backend for renderer seam
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// VBO + GLSL backend. Accumulates triangles into a host-side buffer, uploads
// + draws on state change (matrix, texture) or at EndFrame. MVP is computed
// CPU-side and passed as a uniform.
//
// Works on desktop OpenGL 3.3+ and Android GLES 3.0; shader preamble is
// conditional on the platform. Only backend as of Phase 0 step 4c(f) —
// the fixed-function legacy path was retired after visual parity.
//============================================================================

// On Linux/Mesa, GL 3.3+ function prototypes are gated behind this macro in
// <GL/glext.h>. Define before any header that might pull in <GL/gl.h>, or
// the prototypes go missing once gl.h's include-guard fires.
#if !defined(__ANDROID__) && !defined(__EMSCRIPTEN__)
#  define GL_GLEXT_PROTOTYPES 1
#endif

#if defined(__ANDROID__) || defined(__EMSCRIPTEN__)
#  include <GLES3/gl3.h>
#else
#  include <GL/gl.h>
#  include <GL/glext.h>
#endif

#include <gfx/renderer_backend.hp>
#include <gfx/static_mesh.hp>
#include <gfx/backface_cull.hp>
#include <hal/phonepad/phonepad_overlay.h>
#include <cstdint>   // uintptr_t for the RBTextureHandle cast
#include <gfx/pixelmap.hp>
#include <math/matrix34.hp>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace
{

#if defined(__ANDROID__) || defined(__EMSCRIPTEN__)
// GLES 3.0 requires explicit precision on `int` in the fragment shader (there
// is no default), but the vertex shader gets `highp` implicitly. If we set
// int precision in only one stage, the link fails with
// "fragment integer variable foo does not match the vertex variable".
// Declare highp for both float and int so u_fog / u_lighting / u_use_tex
// match across stages. WebGL 2 (Emscripten) is GLSL ES 3.00 — same rules.
static const char* kShaderHeader =
    "#version 300 es\n"
    "precision highp float;\n"
    "precision highp int;\n";
#else
static const char* kShaderHeader = "#version 330 core\n";
#endif

static const char* kVS =
    "layout(location=0) in vec3 a_pos;\n"
    "layout(location=1) in vec3 a_color;\n"
    "layout(location=2) in vec2 a_uv;\n"
    "layout(location=3) in vec3 a_normal;\n"
    "layout(location=4) in float a_opacity;\n"
    "layout(location=5) in vec4 a_palette_dark;\n"
    "layout(location=6) in vec3 a_palette_light;\n"
    "out vec3  v_color;\n"
    "out vec2  v_uv;\n"
    "out vec3  v_lit;\n"
    "out float v_fog_factor;\n"
    "out float v_opacity;\n"
    "out vec4 v_palette_dark;\n"
    "out vec3 v_palette_light;\n"
    "uniform mat4 u_mvp;\n"
    "uniform mat4 u_mv;\n"
    "uniform int  u_lighting;\n"
    "uniform vec3 u_ambient;\n"
    "uniform vec3 u_light_dir[3];\n"
    "uniform vec3 u_light_color[3];\n"
    "uniform int   u_fog;\n"
    "uniform float u_fog_start;\n"
    "uniform float u_fog_end;\n"
    "void main()\n"
    "{\n"
    "    gl_Position = u_mvp * vec4(a_pos, 1.0);\n"
    "    v_color = a_color;\n"
    "    v_uv = a_uv;\n"
    "    v_opacity = a_opacity;\n"
    "    v_palette_dark = a_palette_dark;\n"
    "    v_palette_light = a_palette_light;\n"
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
    "    if (u_fog != 0) {\n"
    "        float eye_dist = -(u_mv * vec4(a_pos, 1.0)).z;\n"
    "        v_fog_factor = clamp((u_fog_end - eye_dist) /\n"
    "                             (u_fog_end - u_fog_start), 0.0, 1.0);\n"
    "    } else {\n"
    "        v_fog_factor = 1.0;\n"
    "    }\n"
    "}\n";

static const char* kFS =
    "in vec3  v_color;\n"
    "in vec2  v_uv;\n"
    "in vec3  v_lit;\n"
    "in float v_fog_factor;\n"
    "in float v_opacity;\n"
    "in vec4 v_palette_dark;\n"
    "in vec3 v_palette_light;\n"
    "out vec4 frag;\n"
    "uniform sampler2D u_tex;\n"
    "uniform int u_use_tex;\n"
    "uniform int u_alpha_cutout;\n"
    "uniform int u_fog;\n"
    "uniform vec3 u_fog_color;\n"
    "void main()\n"
    "{\n"
    "    vec4 c = vec4(v_color * v_lit, 1.0);\n"
    "    if (u_use_tex != 0) {\n"
    "        float is_white = step(0.99, min(v_color.r, min(v_color.g, v_color.b)));\n"
    "        vec4 texel = texture(u_tex, v_uv);\n"
    "#ifndef WF_OPAQUE\n"
    "        if (u_alpha_cutout != 0 && (is_white > 0.5 || (u_use_tex & 2) != 0) && texel.a < 0.5) discard;\n"
    "#endif\n"
    "        vec3 albedo = v_palette_dark.a > 0.5 ? mix(v_palette_dark.rgb, v_palette_light, clamp((texel.r - 0.08) / 0.85, 0.0, 1.0)) : ((u_use_tex & 2) != 0 ? texel.rgb * v_color : mix(v_color, texel.rgb, is_white));\n"
    "        c = vec4(albedo * v_lit, 1.0);\n"
    "    }\n"
    "    if (u_fog != 0) c.rgb = mix(u_fog_color, c.rgb, v_fog_factor);\n"
    "    c.a = v_opacity;\n"
    "    frag = c;\n"
    "}\n";

struct Vert
{
    float x, y, z;
    float r, g, b;
    float u, v;
    float nx, ny, nz;
    float opacity;
    float paletteDark[4]; // RGB endpoints plus enabled flag.
    float paletteLight[3];
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

// Matrix34 (WF's 3x4) to GL 4x4 column-major is WfMatrix34ToGL in
// gfx/backface_cull.hp, shared with the static-mesh cull so both see the same
// bits.

// One vertex as the shader sees it. Used by the streaming path (per triangle,
// from the backend's current state) and by CreateStaticMesh (from the state
// recorded with each triangle), so the two paths produce identical bytes.
static void PackVert(Vert& dst, const RBVertex& v, float nx, float ny, float nz,
                     float opacity, bool paletteEnabled, unsigned paletteDark, unsigned paletteLight)
{
    dst.x = v.x; dst.y = v.y; dst.z = v.z;
    dst.r = v.r; dst.g = v.g; dst.b = v.b;
    dst.u = v.u; dst.v = v.v;
    dst.nx = nx; dst.ny = ny; dst.nz = nz;
    dst.opacity = opacity;
    for (int i=0;i<3;++i) {
        const int shift=16-8*i;
        dst.paletteDark[i]=float((paletteDark>>shift)&255)/255.f;
        dst.paletteLight[i]=float((paletteLight>>shift)&255)/255.f;
    }
    dst.paletteDark[3]=paletteEnabled ? 1.f : 0.f;
}

// Vertex attribute layout for the currently bound VAO + GL_ARRAY_BUFFER.
// Shared by the streaming VAO and every static-mesh VAO.
static void SetupVertexAttribs()
{
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
    glEnableVertexAttribArray(4);
    glVertexAttribPointer(4, 1, GL_FLOAT, GL_FALSE, stride,
                          (void*)offsetof(Vert, opacity));

    glEnableVertexAttribArray(5);
    glVertexAttribPointer(5, 4, GL_FLOAT, GL_FALSE, stride,
                          (void*)offsetof(Vert, paletteDark));
    glEnableVertexAttribArray(6);
    glVertexAttribPointer(6, 3, GL_FLOAT, GL_FALSE, stride,
                          (void*)offsetof(Vert, paletteLight));
}

// A static mesh (E3 phase 1): one VBO of packed Verts (3 per triangle, in the
// order given to CreateStaticMesh), and a VAO that binds it and an index buffer
// re-filled per draw with the surviving triangles. Normally all mesh VAOs
// share the backend's index buffer; the measurement switch restores per-mesh
// ownership. `generation` is the GL
// context generation it was created in: after an Android surface loss the
// names are dead and the handle only frees its bookkeeping.
struct StaticMeshGL
{
    GLuint vao = 0, vbo = 0, ibo = 0;
    unsigned generation = 0;
    int triangles = 0;
    bool index32 = false;       // more than 65536 vertices
    bool sharedIndex = false;  // backend owns ibo; mesh only holds a reference
    size_t vboBytes = 0;
    size_t iboBytes = 0;        // largest index upload so far
};

// ---- shader compile helpers -------------------------------------------------

// TryCompileShader / TryLinkProgram: non-aborting variants. Return 0 on
// failure and write the GL log into `log_out`. The aborting wrappers below
// keep the original startup-fatal behavior for LazyInit.
static GLuint TryCompileShader(GLenum type, const char* src, std::string& log_out)
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
        log_out = log;
        glDeleteShader(s);
        return 0;
    }
    return s;
}

static GLuint TryLinkProgram(GLuint vs, GLuint fs, std::string& log_out)
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
        log_out = log;
        glDeleteProgram(p);
        return 0;
    }
    glDetachShader(p, vs);
    glDetachShader(p, fs);
    return p;
}

static GLuint CompileShader(GLenum type, const char* src)
{
    std::string log;
    GLuint s = TryCompileShader(type, src, log);
    if (!s)
    {
        std::fprintf(stderr, "modern backend: shader compile failed:\n%s\n", log.c_str());
        std::abort();
    }
    return s;
}

static GLuint LinkProgram(GLuint vs, GLuint fs)
{
    std::string log;
    GLuint p = TryLinkProgram(vs, fs, log);
    if (!p)
    {
        std::fprintf(stderr, "modern backend: program link failed:\n%s\n", log.c_str());
        std::abort();
    }
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
        WfMatrix34ToGL(m, _mv);
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

    void SetFog(float r, float g, float b,
                float start, float end) override
    {
        Flush();
        _fogColor[0] = r;
        _fogColor[1] = g;
        _fogColor[2] = b;
        _fogStart = start;
        _fogEnd   = end;
    }

    void SetTexturePalette(bool e,unsigned dark,unsigned light) override
    {
        // Palette belongs to each vertex, so sorted translucent fish can share
        // a draw call even when their palettes alternate in depth order.
        _paletteEnabled=e;_paletteDark=dark;_paletteLight=light;
    }
    void SetOpacity(float opacity) override
    {
        if (_opacity == opacity) return;
        // Different translucent materials can share one sorted batch. Alpha
        // is per vertex; only switching the blend/depth policy needs a flush.
        if ((_opacity < 1.0f) != (opacity < 1.0f)) Flush();
        _opacity = opacity;
    }

    void SetTextureModulation(bool enabled) override
    {
        if (_modulateTexture == enabled) return;
        Flush();
        _modulateTexture = enabled;
    }

    void SetAlphaCutout(bool enabled) override
    {
        if (_alphaCutout == enabled) return;
        Flush();
        _alphaCutout = enabled;
    }

    void SetFogEnabled(bool enabled) override
    {
        Flush();
        _fogEnabled = enabled;
    }

    void DrawTriangle(const RBVertex& v0,
                      const RBVertex& v1,
                      const RBVertex& v2,
                      float nx, float ny, float nz,
                      const PixelMap* texture,
                      bool cullExempt,
                      bool prelit) override
    {
        wf_profile::count(wf_profile::FacesSubmitted);   // E3 phase 0: before the cull
        // Software backface cull (winding-independent). The renderer never
        // enables GL_CULL_FACE, and mesh winding is inconsistent across asset
        // sources, so we cull from the already-correct per-face normal instead
        // (the same normal one-sided lighting uses). Work in eye space, where
        // the camera sits at the origin looking down -Z: transform the
        // object-space normal by _mv's upper 3x3 (as SetDirLight does) and the
        // face centre by the full _mv. The view vector from eye to face is just
        // its eye-space position, so a face points away from the camera when
        // dot(Ne, Pe) > 0 — cull it. DOUBLE_SIDED materials and the matte pass
        // cullExempt=true.
        //
        // ON BY DEFAULT since 2026-09-21; WF_CULL=0 opts OUT. 15 of the 20
        // shipped wflevels/*-standalone.iff render frame 20 byte-identical
        // with culling on and off; the other five differ only in 93-167 px of
        // back-face bleed the cull correctly removes (qbert_practice 93,
        // condo_639_640 143, condo_639_640_tour 167, snowgoons 98,
        // snowgoons-blender 97 — silhouettes unchanged, mostly *brighter*
        // after). Per-level numbers: the plan's "Effort 2" table. So the cull
        // is a no-op on correct content and a correctness fix on the rest.
        // Getting here took rewinding the dome and the qbert cubes, making
        // LIGHTING_PRELIT faces genuinely unlit, deduping + relighting
        // marble-madness, and righting mm_practice_blender's ground quad.
        // Keep WF_CULL=0 for A/B-ing a suspect mesh: a face that vanishes when
        // culling is on is wound backwards for the view it is authored for.
        // Guard: tests/test_backface_cull_invariant.py.
        // See docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md
        // and docs/level-design-troubleshooting.md "Mesh face normals & backface culling".
        //
        // The test itself is WfFaceIsBackfacing (gfx/backface_cull.hp), shared
        // with the static-mesh path so both make bit-identical decisions; the
        // WF_CULL switch is WfBackfaceCullEnabled there (default ON; opt out
        // with WF_CULL=0).
        if (WfBackfaceCullEnabled() && !cullExempt
            && WfFaceIsBackfacing(_mv, nx, ny, nz,
                                  v0.x, v0.y, v0.z, v1.x, v1.y, v1.z, v2.x, v2.y, v2.z))
        {
            wf_profile::count(wf_profile::FacesCulled);
            return;   // back-facing — skip
        }

        // Batch key = (texture, prelit, static mesh). A LIGHTING_PRELIT run
        // must be drawn with the lighting uniform off, which is per-draw state,
        // so a change breaks the batch the same way a texture change does.
        // Faces are material-sorted by RenderObject3D::Render, so this costs at
        // most one extra draw call per material run, not one per triangle. A
        // pending static-mesh batch (DrawStaticTriangles) is a different source
        // and breaks the batch too.
        if ((texture != _curTexture || prelit != _curPrelit || _curMesh) && !BatchEmpty())
            Flush();
        _curTexture = texture;
        _curPrelit  = prelit;
        _curMesh    = nullptr;

        Vert tri[3];
        Pack(tri[0], v0, nx, ny, nz);
        Pack(tri[1], v1, nx, ny, nz);
        Pack(tri[2], v2, nx, ny, nz);
        _cpu.push_back(tri[0]);
        _cpu.push_back(tri[1]);
        _cpu.push_back(tri[2]);
    }

    void DrawOverlay(const PhonepadRect* rects, int count, int width, int height) override
    {
        if (width <= 0 || height <= 0 || count <= 0) return;
        Flush();
        float projection[16], modelview[16];
        std::memcpy(projection, _proj, sizeof(_proj));
        std::memcpy(modelview, _mv, sizeof(_mv));
        const bool lighting = _lightingEnabled, fog = _fogEnabled;
        const float opacity = _opacity;
        Mat4Identity(_proj);
        Mat4Identity(_mv);
        _mvpDirty = true;
        _lightingEnabled = _fogEnabled = false;
        GLint viewport[4], program, vao, buffer, srcRGB, dstRGB, srcAlpha, dstAlpha;
        GLboolean depthMask;
        glGetIntegerv(GL_VIEWPORT, viewport);
        glGetIntegerv(GL_CURRENT_PROGRAM, &program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);
        glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &buffer);
        glGetIntegerv(GL_BLEND_SRC_RGB, &srcRGB);
        glGetIntegerv(GL_BLEND_DST_RGB, &dstRGB);
        glGetIntegerv(GL_BLEND_SRC_ALPHA, &srcAlpha);
        glGetIntegerv(GL_BLEND_DST_ALPHA, &dstAlpha);
        glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);
        const GLboolean depth = glIsEnabled(GL_DEPTH_TEST), blend = glIsEnabled(GL_BLEND);
        const GLboolean cull = glIsEnabled(GL_CULL_FACE), scissor = glIsEnabled(GL_SCISSOR_TEST);
        glViewport(0, 0, width, height);
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_CULL_FACE);
        glDisable(GL_SCISSOR_TEST);
        for (int i = 0; i < count; ++i)
        {
            const PhonepadRect& r = rects[i];
            SetOpacity(float(r.rgba & 255) / 255.0f);
            const float red = float((r.rgba >> 24) & 255) / 255.0f;
            const float green = float((r.rgba >> 16) & 255) / 255.0f;
            const float blue = float((r.rgba >> 8) & 255) / 255.0f;
            const float left = 2.0f * r.x0 / width - 1.0f;
            const float right = 2.0f * r.x1 / width - 1.0f;
            const float top = 1.0f - 2.0f * r.y0 / height;
            const float bottom = 1.0f - 2.0f * r.y1 / height;
            const RBVertex a{left, top, 0, red, green, blue, 0, 0};
            const RBVertex b{right, top, 0, red, green, blue, 0, 0};
            const RBVertex c{right, bottom, 0, red, green, blue, 0, 0};
            const RBVertex d{left, bottom, 0, red, green, blue, 0, 0};
            DrawTriangle(a, b, c, 0, 0, 1, NULL, true, true);
            DrawTriangle(a, c, d, 0, 0, 1, NULL, true, true);
        }
        Flush();
        std::memcpy(_proj, projection, sizeof(_proj));
        std::memcpy(_mv, modelview, sizeof(_mv));
        _mvpDirty = true;
        _lightingEnabled = lighting;
        _fogEnabled = fog;
        _opacity = opacity;
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        glUseProgram(program);
        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, buffer);
        glDepthMask(depthMask);
        glBlendFuncSeparate(srcRGB, dstRGB, srcAlpha, dstAlpha);
        if (depth) glEnable(GL_DEPTH_TEST);
        if (cull) glEnable(GL_CULL_FACE);
        if (scissor) glEnable(GL_SCISSOR_TEST);
        if (blend) glEnable(GL_BLEND); else glDisable(GL_BLEND);
    }

    void EndFrame() override
    {
        Flush();
        // glClear also honours the depth write mask on the next frame.
        glDepthMask(GL_TRUE);
        glDisable(GL_BLEND);
    }

    // ---- textures (D4/O3) --------------------------------------------------
    // Verbatim relocation of what pixelmap.cc used to do inline, so GL
    // behaviour is unchanged: same internal/external formats, same wrap and
    // filter policy, same GFX_ZBUFFER split. The only difference is that it
    // now lives in the backend that owns the representation.
    RBTextureHandle CreateTexture(int width, int height,
                                  RBTextureFormat format,
                                  const void* pixels) override
    {
        GLuint name = 0;
        glGenTextures(1, &name);
        if (!name)
            return NULL;

        glBindTexture(GL_TEXTURE_2D, name);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
#if defined ( GFX_ZBUFFER )
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        // Global state, and misplaced in a texture upload — but this is where
        // it has always been enabled, so moving it would be a behaviour change
        // smuggled into a refactor. Left as-is, flagged rather than fixed.
        glEnable(GL_DEPTH_TEST);
        glEnable(GL_BLEND);
#else
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
#endif
        // GL_RGB5 is a desktop-GL sized format; GLES 3.0 has no such enum (only
        // GL_RGB565 / GL_RGB5_A1), so the Android build broke on it (728bb808).
        // GL_RGB8 keeps the uploaded bytes exactly, which is what GL_RGB5 stores
        // for data that is already 5 bits per channel.
#if defined(__ANDROID__) || defined(__EMSCRIPTEN__)
        const GLint  rgb5Format = GL_RGB8;
#else
        const GLint  rgb5Format = GL_RGB5;
#endif
        const GLint  internalFormat =
            (format == RB_TEX_RGB5) ? rgb5Format : GL_RGBA;
        const GLenum externalFormat =
            (format == RB_TEX_RGB5) ? GL_RGB  : GL_RGBA;
        glTexImage2D(GL_TEXTURE_2D, 0, internalFormat, width, height,
                     0, externalFormat, GL_UNSIGNED_BYTE, pixels);

        return (RBTextureHandle)(uintptr_t)name;
    }

    void DestroyTexture(RBTextureHandle handle) override
    {
        if (!handle)
            return;
        GLuint name = (GLuint)(uintptr_t)handle;
        glDeleteTextures(1, &name);
    }

    // Hot-reload the program from new GLSL. Called from the game thread
    // (which is also the GL thread); safe to call any time DrainQueue runs
    // because it Flush()es first and then atomically swaps _prog. On failure
    // the current program stays live and log_out gets the GL info-log.
    bool ReloadProgram(const char* vert, const char* frag,
                       std::string& log_out) override
    {
        if (!_inited)
        {
            // No GL context yet — nothing to reload, and we don't have a
            // valid context to compile in either.
            log_out = "renderer not yet initialised";
            return false;
        }
        Flush();
        GLuint vs = TryCompileShader(GL_VERTEX_SHADER,   vert, log_out);
        if (!vs) return false;
        GLuint fs = TryCompileShader(GL_FRAGMENT_SHADER, frag, log_out);
        if (!fs) { glDeleteShader(vs); return false; }
        GLuint p = TryLinkProgram(vs, fs, log_out);
        glDeleteShader(vs);
        glDeleteShader(fs);
        if (!p) return false;

        glDeleteProgram(_prog);
        _prog = p;
        // Custom source may intentionally discard or define different uniforms.
        // Never substitute a built-in specialization for a successful reload.
        if (_opaqueProg) glDeleteProgram(_opaqueProg);
        _opaqueProg = 0;
        _opaqueUniforms = ProgramUniforms{};
        _customProgram = true;
        _uniforms = FetchUniformLocations(_prog);
        return true;
    }

    // Called from the Android lifecycle hook (WFAndroidEglTerm) when the
    // EGL surface is destroyed. Reset all GL-object handles; the next draw
    // call's LazyInit will recompile the program + recreate VAO/VBO in the
    // new context. Textures are re-uploaded lazily by PixelMap::SetGLTexture
    // the first time each one is bound after resume.
    void OnSurfaceLost()
    {
        _inited      = false;
        _vao         = 0;
        _vbo         = 0;
        _prog        = 0;
        _opaqueProg = 0;
        _uniforms = ProgramUniforms{};
        _opaqueUniforms = ProgramUniforms{};
        _customProgram = false;
        _cpu.clear();
        _curTexture  = nullptr;
        // Static meshes: every GL name is dead. Bumping the generation makes
        // StaticMeshLive false for all existing handles, so their owners bake
        // again on next draw (from the resident RenderObject3D data, there is
        // no CPU copy of the packed vertices to re-upload).
        ++_contextGeneration;
        _idx16.clear();
        _idx32.clear();
        _curMesh = nullptr;
        _staticGpuBytes = 0;
        _sharedIbo = 0;
        _sharedIboBytes = 0;
        _sharedMeshCount = 0;
    }

    // ---- static meshes (E3 phase 1) ----------------------------------------

    bool StaticMeshSupported() const override { return true; }

    RBStaticMeshHandle CreateStaticMesh(const RBStaticTriangle* triangles, int count) override
    {
        if (!triangles || count <= 0) return NULL;
        StaticMeshGL* mesh = new StaticMeshGL;
        mesh->generation = _contextGeneration;
        mesh->triangles  = count;
        mesh->index32    = size_t(count) * 3 > 65536;
        mesh->vboBytes   = size_t(count) * 3 * sizeof(Vert);
        mesh->sharedIndex = StaticMeshSharedIndex();
        glGenVertexArrays(1, &mesh->vao);
        glGenBuffers(1, &mesh->vbo);
        if (mesh->sharedIndex)
        {
            if (!_sharedIbo) glGenBuffers(1, &_sharedIbo);
            mesh->ibo = _sharedIbo;
        }
        else
            glGenBuffers(1, &mesh->ibo);
        if (!mesh->vao || !mesh->vbo || !mesh->ibo)
        {
            if (mesh->vao) glDeleteVertexArrays(1, &mesh->vao);
            if (mesh->vbo) glDeleteBuffers(1, &mesh->vbo);
            if (mesh->sharedIndex)
            {
                if (!_sharedMeshCount && _sharedIbo)
                {
                    glDeleteBuffers(1, &_sharedIbo);
                    _sharedIbo = 0;
                }
            }
            else if (mesh->ibo) glDeleteBuffers(1, &mesh->ibo);
            delete mesh;
            return NULL;
        }
        glBindVertexArray(mesh->vao);
        glBindBuffer(GL_ARRAY_BUFFER, mesh->vbo);
        glBufferData(GL_ARRAY_BUFFER, GLsizeiptr(mesh->vboBytes), NULL, GL_STATIC_DRAW);
        // Pack exactly as Pack would have, in chunks: the transient stays
        // small (kChunk x 228 B = 58 KB) instead of a whole mesh (1.1 MB for
        // the largest), so the allocator does not keep a large freed block
        // around (cast1 native heap rose 1.2 MB with a whole-mesh vector).
        enum { kChunk = 256 };
        std::vector<Vert> chunk(size_t(kChunk) * 3);
        for (int first = 0; first < count; first += kChunk)
        {
            const int n = (count - first < kChunk) ? count - first : kChunk;
            for (int t = 0; t < n; ++t)
            {
                const RBStaticTriangle& tri = triangles[first + t];
                for (int k = 0; k < 3; ++k)
                    PackVert(chunk[size_t(t) * 3 + k], tri.v[k], tri.nx, tri.ny, tri.nz,
                             tri.opacity, tri.paletteEnabled != 0, tri.paletteDark, tri.paletteLight);
            }
            glBufferSubData(GL_ARRAY_BUFFER, GLintptr(size_t(first) * 3 * sizeof(Vert)),
                            GLsizeiptr(size_t(n) * 3 * sizeof(Vert)), chunk.data());
        }
        SetupVertexAttribs();
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, mesh->ibo);   // recorded in the VAO
        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
        _staticGpuBytes += mesh->vboBytes;
        if (mesh->sharedIndex) ++_sharedMeshCount;
        return mesh;
    }

    void DestroyStaticMesh(RBStaticMeshHandle handle) override
    {
        StaticMeshGL* mesh = static_cast<StaticMeshGL*>(handle);
        if (!mesh) return;
        if (mesh == _curMesh) Flush();      // draw what is queued from it first
        if (mesh->generation == _contextGeneration)
        {
            glDeleteVertexArrays(1, &mesh->vao);
            glDeleteBuffers(1, &mesh->vbo);
            _staticGpuBytes -= mesh->vboBytes;
            if (mesh->sharedIndex)
            {
                // Other live mesh VAOs still refer to this buffer. Release it
                // only with the last mesh of this context generation.
                if (--_sharedMeshCount == 0)
                {
                    glDeleteBuffers(1, &_sharedIbo);
                    _sharedIbo = 0;
                    _staticGpuBytes -= _sharedIboBytes;
                    _sharedIboBytes = 0;
                }
            }
            else
            {
                glDeleteBuffers(1, &mesh->ibo);
                _staticGpuBytes -= mesh->iboBytes;
            }
        }
        delete mesh;
    }

    void StaticMeshBytes(size_t& gpu, size_t& cpu) const override
    {
        gpu = _staticGpuBytes;
        cpu = _idx16.capacity() * sizeof(uint16_t) + _idx32.capacity() * sizeof(uint32_t);
    }

    bool StaticMeshLive(RBStaticMeshHandle handle) const override
    {
        const StaticMeshGL* mesh = static_cast<const StaticMeshGL*>(handle);
        return mesh && mesh->generation == _contextGeneration;
    }

    void DrawStaticTriangles(RBStaticMeshHandle handle, const unsigned* triangles, int count,
                             const PixelMap* texture, bool prelit) override
    {
        if (count <= 0) return;             // all culled: DrawTriangle would queue nothing
        StaticMeshGL* mesh = static_cast<StaticMeshGL*>(handle);
        // Same batch key as DrawTriangle, with the mesh as part of it.
        if ((texture != _curTexture || prelit != _curPrelit || mesh != _curMesh) && !BatchEmpty())
            Flush();
        _curTexture = texture;
        _curPrelit  = prelit;
        _curMesh    = mesh;
        if (mesh->index32)
        {
            for (int i = 0; i < count; ++i)
            {
                const uint32_t base = uint32_t(triangles[i]) * 3;
                _idx32.push_back(base);
                _idx32.push_back(base + 1);
                _idx32.push_back(base + 2);
            }
        }
        else
        {
            for (int i = 0; i < count; ++i)
            {
                const uint16_t base = uint16_t(triangles[i] * 3);
                _idx16.push_back(base);
                _idx16.push_back(uint16_t(base + 1));
                _idx16.push_back(uint16_t(base + 2));
            }
        }
    }

private:
    bool   _inited   = false;
    GLuint _vao      = 0;
    GLuint _vbo      = 0;
    GLuint _prog     = 0;
    struct ProgramUniforms
    {
        GLint mvp=-1, mv=-1, tex=-1, useTex=-1, alphaCutout=-1;
        GLint lighting=-1, ambient=-1, lightDir=-1, lightColor=-1;
        GLint fog=-1, fogColor=-1, fogStart=-1, fogEnd=-1;
    };
    ProgramUniforms _uniforms, _opaqueUniforms;
    GLuint _opaqueProg = 0;
    bool _customProgram = false;
    bool _paletteEnabled=false; unsigned _paletteDark=0,_paletteLight=0xffffff;
    float _opacity = 1.0f;

    float _proj[16];
    float _mv[16];
    float _mvp[16];
    bool  _mvpDirty  = true;

    bool  _lightingEnabled = false;
    float _ambient[3];
    float _lightDir  [RB_MAX_LIGHTS][3];
    float _lightColor[RB_MAX_LIGHTS][3];

    bool _alphaCutout = false;
    bool _modulateTexture = false;
    bool  _fogEnabled = false;
    float _fogColor[3] = { 0.0f, 0.0f, 0.0f };
    float _fogStart = 1.0f;
    float _fogEnd   = 1000.0f;

    const PixelMap* _curTexture = nullptr;
    // Whether the triangles currently pending in _cpu came from a
    // LIGHTING_PRELIT material. Part of the batch key alongside _curTexture.
    bool  _curPrelit = false;
    std::vector<Vert> _cpu;
    // Static-mesh batch (E3): when _curMesh is set the pending triangles are
    // indices into its VBO (16-bit, or 32-bit for a mesh over 65536 vertices)
    // instead of packed vertices in _cpu. Only one of the two is non-empty.
    StaticMeshGL* _curMesh = nullptr;
    std::vector<uint16_t> _idx16;
    std::vector<uint32_t> _idx32;
    unsigned _contextGeneration = 1;
    size_t _staticGpuBytes = 0;
    GLuint _sharedIbo = 0;
    size_t _sharedIboBytes = 0;  // largest upload, counted once across all VAOs
    unsigned _sharedMeshCount = 0;

    bool BatchEmpty() const { return _cpu.empty() && _idx16.empty() && _idx32.empty(); }

    void Pack(Vert& dst, const RBVertex& v,
                     float nx, float ny, float nz)
    {
        PackVert(dst, v, nx, ny, nz, _opacity, _paletteEnabled, _paletteDark, _paletteLight);
    }

    static ProgramUniforms FetchUniformLocations(GLuint program)
    {
        ProgramUniforms uniforms;
        uniforms.mvp        = glGetUniformLocation(program, "u_mvp");
        uniforms.mv         = glGetUniformLocation(program, "u_mv");
        uniforms.tex        = glGetUniformLocation(program, "u_tex");
        uniforms.useTex     = glGetUniformLocation(program, "u_use_tex");
        uniforms.alphaCutout = glGetUniformLocation(program, "u_alpha_cutout");
        uniforms.lighting   = glGetUniformLocation(program, "u_lighting");
        uniforms.ambient    = glGetUniformLocation(program, "u_ambient");
        uniforms.lightDir   = glGetUniformLocation(program, "u_light_dir");
        uniforms.lightColor = glGetUniformLocation(program, "u_light_color");
        uniforms.fog        = glGetUniformLocation(program, "u_fog");
        uniforms.fogColor   = glGetUniformLocation(program, "u_fog_color");
        uniforms.fogStart   = glGetUniformLocation(program, "u_fog_start");
        uniforms.fogEnd     = glGetUniformLocation(program, "u_fog_end");
        return uniforms;
    }

    void LazyInit()
    {
        if (_inited) return;

        GLuint vs = CompileShader(GL_VERTEX_SHADER,   kVS);
        GLuint fs = CompileShader(GL_FRAGMENT_SHADER, kFS);
        _prog = LinkProgram(vs, fs);
        glDeleteShader(vs);
        glDeleteShader(fs);

        _uniforms = FetchUniformLocations(_prog);

        glGenVertexArrays(1, &_vao);
        glGenBuffers(1, &_vbo);
        glBindVertexArray(_vao);
        glBindBuffer(GL_ARRAY_BUFFER, _vbo);

        SetupVertexAttribs();

        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);

        _inited = true;
    }

    void InitOpaqueProgram()
    {
        if (_opaqueProg) return;
        // Compile out discard entirely; a runtime false branch can still make
        // the executable coverage-changing on tile-based GPUs.
        const std::string opaqueFS = std::string("#define WF_OPAQUE 1\n") + kFS;
        GLuint vs = CompileShader(GL_VERTEX_SHADER, kVS);
        GLuint fs = CompileShader(GL_FRAGMENT_SHADER, opaqueFS.c_str());
        _opaqueProg = LinkProgram(vs, fs);
        glDeleteShader(vs);
        glDeleteShader(fs);
        _opaqueUniforms = FetchUniformLocations(_opaqueProg);
    }

    void UpdateMvp()
    {
        if (!_mvpDirty) return;
        Mat4Multiply(_proj, _mv, _mvp);
        _mvpDirty = false;
    }

    void Flush()
    {
        if (BatchEmpty())
        {
            _curTexture = nullptr;
            _curPrelit  = false;
            _curMesh    = nullptr;
            return;
        }
        LazyInit();
        UpdateMvp();

        const bool opaque = !_customProgram && _opacity >= 1.0f && !_alphaCutout;
        if (opaque) InitOpaqueProgram();
        glUseProgram(opaque ? _opaqueProg : _prog);
        const ProgramUniforms& uniforms = opaque ? _opaqueUniforms : _uniforms;
        if (_opacity < 1.0f) {
            glEnable(GL_BLEND);
            glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
            glDepthMask(GL_FALSE);
        } else {
            glDisable(GL_BLEND);
            glDepthMask(GL_TRUE);
        }
        glUniformMatrix4fv(uniforms.mvp, 1, GL_FALSE, _mvp);
        glUniformMatrix4fv(uniforms.mv,  1, GL_FALSE, _mv);
        // A prelit batch is unlit by definition: its vertex colors are final.
        glUniform1i(uniforms.lighting, (_lightingEnabled && !_curPrelit) ? 1 : 0);
        glUniform3fv(uniforms.ambient, 1, _ambient);
        glUniform3fv(uniforms.lightDir,   RB_MAX_LIGHTS, &_lightDir[0][0]);
        glUniform3fv(uniforms.lightColor, RB_MAX_LIGHTS, &_lightColor[0][0]);
        glUniform1i(uniforms.fog, _fogEnabled ? 1 : 0);
        glUniform3fv(uniforms.fogColor, 1, _fogColor);
        glUniform1f(uniforms.fogStart, _fogStart);
        glUniform1f(uniforms.fogEnd,   _fogEnd);

        if (_curTexture)
        {
            glActiveTexture(GL_TEXTURE0);
            _curTexture->SetGLTexture();
            glUniform1i(uniforms.tex, 0);
            glUniform1i(uniforms.useTex, _modulateTexture ? 3 : 1);
            glUniform1i(uniforms.alphaCutout, _alphaCutout ? 1 : 0);
        }
        else
        {
            glUniform1i(uniforms.useTex, 0);
        }

        if (_curMesh)
        {
            // Static mesh: the vertices are already on the GPU; upload only
            // the surviving triangles' indices (orphaning the previous ones;
            // WebGL2 has no buffer mapping) and draw them in submission order.
            StaticMeshGL& mesh = *_curMesh;
            const size_t count = mesh.index32 ? _idx32.size() : _idx16.size();
            const size_t bytes = mesh.index32 ? count * sizeof(uint32_t) : count * sizeof(uint16_t);
            glBindVertexArray(mesh.vao);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, GLsizeiptr(bytes),
                         mesh.index32 ? static_cast<const void*>(_idx32.data())
                                      : static_cast<const void*>(_idx16.data()),
                         GL_STREAM_DRAW);
            // glBufferData orphans the old storage before each draw. Sharing
            // the name does not overwrite indices consumed by earlier draws,
            // including when the next mesh uses a different index width.
            size_t& iboBytes = mesh.sharedIndex ? _sharedIboBytes : mesh.iboBytes;
            if (bytes > iboBytes)
            {
                _staticGpuBytes += bytes - iboBytes;
                iboBytes = bytes;
            }
            wf_profile::count(wf_profile::Draws);
            wf_profile::count(wf_profile::Triangles, count / 3);
            wf_profile::count(wf_profile::StaticDraws);
            wf_profile::count(wf_profile::StaticIndexBytes, bytes);
            glDrawElements(GL_TRIANGLES, GLsizei(count),
                           mesh.index32 ? GL_UNSIGNED_INT : GL_UNSIGNED_SHORT, (void*)0);
            _idx16.clear();
            _idx32.clear();
        }
        else
        {
        glBindVertexArray(_vao);
        glBindBuffer(GL_ARRAY_BUFFER, _vbo);
        glBufferData(GL_ARRAY_BUFFER,
                     GLsizeiptr(_cpu.size() * sizeof(Vert)),
                     _cpu.data(),
                     GL_STREAM_DRAW);
        wf_profile::count(wf_profile::Uploads);
        wf_profile::count(wf_profile::UploadBytes,_cpu.size() * sizeof(Vert));
        wf_profile::count(2);
        wf_profile::count(3,_cpu.size()/3);
        glDrawArrays(GL_TRIANGLES, 0, GLsizei(_cpu.size()));
        }

        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glUseProgram(0);

        _cpu.clear();
        _curTexture = nullptr;
        _curPrelit  = false;
        _curMesh    = nullptr;
    }
};

ModernRendererBackend sModernBackend;

}  // namespace

RendererBackend* ModernBackendInstance()
{
    return &sModernBackend;
}

// Test hook (WF_STATIC_MESH_TEST=loss:N, via backend_factory.cc): the same
// reset the Android surface-loss path does, on a context that stays alive.
void ModernBackendSimulateSurfaceLoss()
{
    sModernBackend.OnSurfaceLost();
}

#if defined(__ANDROID__)
// Called from gfx/gl/android_window.cc's WFAndroidEglTerm when the EGL
// surface is torn down on pause/backgrounding. Resets all GL-object IDs so
// the first draw after resume (into the new context) triggers LazyInit
// again instead of trying to use stale handles.
extern "C" void
WFAndroidNotifySurfaceLost()
{
    sModernBackend.OnSurfaceLost();
}
#endif
