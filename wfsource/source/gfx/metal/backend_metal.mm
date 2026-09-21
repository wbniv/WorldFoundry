//=============================================================================
// gfx/metal/backend_metal.mm: Metal implementation of RendererBackend
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// The Metal sibling of gfx/glpipeline/backend_modern.cc, shared by both Apple
// targets. It lived in hal/ios/ until Phase 2 of
// docs/plans/2026-09-20-macos-metal-renderer.md; it imports only Metal, simd
// and engine headers — no UIKit, no AppKit — so it was never iOS HAL code (D3).
//
// Mirrors backend_modern's CPU-side state + triangle batching; MSL shaders
// inline and runtime-compiled via [MTLDevice newLibraryWithSource:] so the
// build stays Codemagic-native (no .metal file + Xcode build phase).
//
// Phase 2 (macOS) added, on top of the iOS Phase 2B3 skeleton:
//   * the OFFSCREEN path at the bottom of this file (wf_metal::), which owns a
//     device, queue, colour + depth MTLTexture and command buffer, so the
//     engine can render a frame with no window and no drawable. This target is
//     deliberately shaped as the editor's future viewport handshake surface
//     (plan O2), which is why ColorTextureHandle() is part of the interface.
//   * a DEPTH attachment — pipeline depth format, depth texture, and a
//     Less/write-enabled MTLDepthStencilState.
//   * three first-light fixes, all of which were latent in the iOS skeleton and
//     could never have fired there because no encoder was ever set (so Flush()
//     always dropped the batch). See the comments at each site:
//       - Mat4Perspective emitted GL's [-1,1] NDC z; Metal's is [0,1].
//       - vertices went through setVertexBytes, which is capped at 4 KB.
//       - no depth state at all.
//
// Textures are still not supported — DrawTriangle ignores the PixelMap* and
// draws flat-lit. That is Phase 3, and per the resolved D4/O3 it lands by
// widening the RendererBackend seam (CreateTexture/DestroyTexture + an opaque
// handle on PixelMap), not by a Metal-side sidecar.
//=============================================================================

#import <Metal/Metal.h>
#import <simd/simd.h>
// CAMetalLayer / CAMetalDrawable for the Phase 4 windowed path. Metal.h does
// NOT pull these in — they are QuartzCore types — which is what broke build
// 6ab051f8b90e9b17b45ad5b1. Present on both Apple targets, and QuartzCore is
// already linked on each.
#import <QuartzCore/CAMetalLayer.h>

#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#include <gfx/metal/metal_offscreen.h>
#include <math/matrix34.hp>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace
{

// One place for the depth format: the pipeline descriptor, the depth texture
// and the render pass descriptor must all agree or pipeline creation fails at
// runtime with a message that does not name the mismatch.
static constexpr MTLPixelFormat kDepthFormat = MTLPixelFormatDepth32Float;

// ---- RBTextureHandle <-> id<MTLTexture> -------------------------------------
// The handle crosses a void* boundary into shared C++ (PixelMap), so ownership
// has to be transferred explicitly. This build is manual retain/release — there
// is no -fobjc-arc anywhere in CMakeLists.txt or codemagic.yaml — but the ARC
// arm is written out so switching it on later fails to compile rather than
// silently leaking or over-releasing every texture.
static inline RBTextureHandle TexToHandle(id<MTLTexture> t)
{
#if __has_feature(objc_arc)
    return (RBTextureHandle)CFBridgingRetain(t);
#else
    return (RBTextureHandle)[t retain];
#endif
}

static inline id<MTLTexture> HandleToTex(RBTextureHandle h)
{
#if __has_feature(objc_arc)
    return (__bridge id<MTLTexture>)h;
#else
    return (id<MTLTexture>)h;
#endif
}

static inline void ReleaseTexHandle(RBTextureHandle h)
{
    if (!h) return;
#if __has_feature(objc_arc)
    CFBridgingRelease(h);
#else
    [(id<MTLTexture>)h release];
#endif
}

static constexpr const char* kMSL = R"MSL(
#include <metal_stdlib>
using namespace metal;

struct VertexIn {
    float3 pos    [[attribute(0)]];
    float3 color  [[attribute(1)]];
    float2 uv     [[attribute(2)]];
    float3 normal [[attribute(3)]];
};

struct VertexOut {
    float4 position  [[position]];
    float3 color;
    float2 uv;
    float3 lit;
    float  fog_factor;
};

// Layout must match CPU-side Uniforms struct byte-for-byte.
// Directions use float4 (xyz used) to sidestep MSL's float3[] stride-16
// padding so we don't have to special-case CPU serialization.
struct Uniforms {
    float4x4 mvp;
    float4x4 mv;
    float3   ambient;
    int      lighting;
    float4   light_dir[3];
    float4   light_color[3];
    float3   fog_color;
    int      fog;
    float    fog_start;
    float    fog_end;
    int      use_tex;
    int      _pad;
};

vertex VertexOut wf_vs(VertexIn v                  [[stage_in]],
                       constant Uniforms& u        [[buffer(1)]])
{
    VertexOut o;
    o.position = u.mvp * float4(v.pos, 1.0);
    o.color    = v.color;
    o.uv       = v.uv;

    if (u.lighting != 0) {
        float3 N = normalize((u.mv * float4(v.normal, 0.0)).xyz);
        float3 lit = u.ambient;
        for (int i = 0; i < 3; ++i) {
            lit += u.light_color[i].xyz *
                   max(0.0, dot(N, u.light_dir[i].xyz));
        }
        o.lit = lit;
    } else {
        o.lit = float3(1.0);
    }

    if (u.fog != 0) {
        float eye_dist = -(u.mv * float4(v.pos, 1.0)).z;
        o.fog_factor = clamp((u.fog_end - eye_dist) /
                             (u.fog_end - u.fog_start), 0.0, 1.0);
    } else {
        o.fog_factor = 1.0;
    }
    return o;
}

fragment float4 wf_fs(VertexOut v                  [[stage_in]],
                      constant Uniforms& u         [[buffer(1)]],
                      texture2d<float> tex         [[texture(0)]],
                      sampler          smp         [[sampler(0)]])
{
    float4 c = float4(v.color * v.lit, 1.0);
    // Phase 3: REPLACE-IF-WHITE, character for character the rule in
    // backend_modern.cc's kFS. WF's convention is that a white vertex colour
    // means "this face is textured" and any other colour means "flat coloured,
    // ignore the texture" — so it is a mix() selected by whiteness, NOT a
    // modulate. Modulating (the obvious guess) happens to agree on white faces
    // and silently darkens every coloured-but-textured face.
    if (u.use_tex != 0) {
        float is_white = step(0.99, min(v.color.r, min(v.color.g, v.color.b)));
        c = float4(mix(v.color, tex.sample(smp, v.uv).rgb, is_white) * v.lit, 1.0);
    }
    if (u.fog != 0) {
        c.rgb = mix(u.fog_color, c.rgb, v.fog_factor);
    }
    return c;
}
)MSL";

struct Vert
{
    float x, y, z;
    float r, g, b;
    float u, v;
    float nx, ny, nz;
};

struct Uniforms
{
    simd::float4x4 mvp;
    simd::float4x4 mv;
    simd::float3   ambient;
    int32_t        lighting;
    simd::float4   light_dir[3];
    simd::float4   light_color[3];
    simd::float3   fog_color;
    int32_t        fog;
    float          fog_start;
    float          fog_end;
    int32_t        use_tex;
    int32_t        _pad;
};

// ---- matrix helpers (column-major, GL/Metal convention) ---------------------

static void Mat4Identity(float m[16])
{
    std::memset(m, 0, sizeof(float) * 16);
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

// NOTE (Phase 2 first light): this emits METAL's clip convention, z in [0,1],
// not OpenGL's [-1,1]. It previously used the GL form
//     out[10] = (fz+nz)/(nz-fz);  out[14] = 2*fz*nz/(nz-fz);
// which maps the near half of the frustum to negative z. Metal clips anything
// with z < 0, so with a depth buffer cleared to 1 and a Less test, roughly the
// front half of every scene would have been silently discarded. It could not
// have shown up on iOS: no encoder was ever set there, so Flush() dropped every
// batch before a pixel was rasterised. The plan predicted this exact class of
// bug ("NDC Z range [0,1] on Metal vs [-1,1] on GL") — it was real.
static void Mat4Perspective(float fovDegY, float aspect, float nz, float fz,
                            float out[16])
{
    const float f =
        1.0f / std::tan((fovDegY * 0.5f) * (3.14159265358979323846f / 180.0f));
    std::memset(out, 0, sizeof(float) * 16);
    out[0]  = f / aspect;
    out[5]  = f;
    out[10] = fz / (nz - fz);           // Metal: nz -> 0, fz -> 1
    out[11] = -1.0f;
    out[14] = (fz * nz) / (nz - fz);
}

static void Mat4Multiply(const float a[16], const float b[16], float out[16])
{
    float r[16];
    for (int c = 0; c < 4; ++c)
        for (int rr = 0; rr < 4; ++rr)
            r[c*4+rr] = a[0*4+rr]*b[c*4+0] + a[1*4+rr]*b[c*4+1]
                      + a[2*4+rr]*b[c*4+2] + a[3*4+rr]*b[c*4+3];
    std::memcpy(out, r, sizeof(r));
}

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

static simd::float4x4 Float16ToSimd(const float m[16])
{
    return simd::float4x4{
        simd::float4{ m[0],  m[1],  m[2],  m[3]  },
        simd::float4{ m[4],  m[5],  m[6],  m[7]  },
        simd::float4{ m[8],  m[9],  m[10], m[11] },
        simd::float4{ m[12], m[13], m[14], m[15] }
    };
}

// ---- the backend ------------------------------------------------------------

class MetalRendererBackend : public RendererBackend
{
public:
    MetalRendererBackend()
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
        _ambient[0] = r; _ambient[1] = g; _ambient[2] = b;
    }

    void SetDirLight(int index,
                     float dirX, float dirY, float dirZ,
                     float r, float g, float b) override
    {
        if (index < 0 || index >= RB_MAX_LIGHTS) return;
        Flush();
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
        _fogColor[0] = r; _fogColor[1] = g; _fogColor[2] = b;
        _fogStart = start; _fogEnd = end;
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
        // Software backface cull — mirrors backend_modern.cc. Cull from the
        // object-space face normal + model->eye _mv (winding-independent): a face
        // points away when dot(Ne, Pe) > 0 in eye space. DOUBLE_SIDED/matte pass
        // cullExempt=true. OFF BY DEFAULT (opt-in via WF_CULL=1) — see the long
        // note in backend_modern.cc::DrawTriangle for why.
        static const bool cullEnabled = []() {
            const char* e = getenv("WF_CULL");
            return e && atoi(e) != 0;   // opt-in
        }();
        if (cullEnabled && !cullExempt)
        {
            const float nex = _mv[0]*nx + _mv[4]*ny + _mv[8]*nz;
            const float ney = _mv[1]*nx + _mv[5]*ny + _mv[9]*nz;
            const float nez = _mv[2]*nx + _mv[6]*ny + _mv[10]*nz;
            const float cx = (v0.x + v1.x + v2.x) * (1.0f / 3.0f);
            const float cy = (v0.y + v1.y + v2.y) * (1.0f / 3.0f);
            const float cz = (v0.z + v1.z + v2.z) * (1.0f / 3.0f);
            const float pex = _mv[0]*cx + _mv[4]*cy + _mv[8]*cz  + _mv[12];
            const float pey = _mv[1]*cx + _mv[5]*cy + _mv[9]*cz  + _mv[13];
            const float pez = _mv[2]*cx + _mv[6]*cy + _mv[10]*cz + _mv[14];
            if (nex*pex + ney*pey + nez*pez > 0.0f)
                return;
        }

        // Batch key = (texture, prelit) — mirrors backend_modern.cc. A
        // LIGHTING_PRELIT run is drawn with u.lighting cleared, which is
        // per-draw state, so a change breaks the batch like a texture change.
        if ((texture != _curTexture || prelit != _curPrelit) && !_cpu.empty())
            Flush();
        _curTexture = texture;
        _curPrelit  = prelit;

        Vert tri[3];
        Pack(tri[0], v0, nx, ny, nz);
        Pack(tri[1], v1, nx, ny, nz);
        Pack(tri[2], v2, nx, ny, nz);
        _cpu.push_back(tri[0]);
        _cpu.push_back(tri[1]);
        _cpu.push_back(tri[2]);
        ++_trianglesThisFrame;
    }

    void EndFrame() override
    {
        Flush();
        ++_renderedFrames;
        _trianglesLastFrame = _trianglesThisFrame;
        _trianglesTotal    += _trianglesThisFrame;
        _trianglesThisFrame = 0;
    }

    // Phase 2C: MetalView's CADisplayLink callback calls SetCurrentEncoder
    // with the frame's MTLRenderCommandEncoder before invoking the engine
    // frame loop, then ClearCurrentEncoder after EndFrame.
    void SetCurrentEncoder(id<MTLRenderCommandEncoder> encoder)
    {
        _encoder = encoder;
    }

    void ClearCurrentEncoder()
    {
        _encoder = nil;
    }

    // ---- textures (Phase 3, D4/O3) -----------------------------------------
    RBTextureHandle CreateTexture(int width, int height,
                                  RBTextureFormat format,
                                  const void* pixels) override
    {
        if (!EnsureInited() || width <= 0 || height <= 0 || !pixels)
            return NULL;
        // RB_TEX_RGB5 is the SIXTEEN_BIT_VRAM path, which feeds 3 bytes/texel.
        // Metal has no 24-bit format, and this build does not use it, so refuse
        // loudly rather than silently sample garbage if it is ever switched on.
        if (format != RB_TEX_RGBA8) {
            NSLog(@"wf_game: MetalBackend: RB_TEX_RGB5 not implemented");
            return NULL;
        }

        MTLTextureDescriptor* td = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                         width:(NSUInteger)width
                                        height:(NSUInteger)height
                                     mipmapped:NO];
        td.usage       = MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeManaged;
        id<MTLTexture> tex = [_device newTextureWithDescriptor:td];
        if (!tex) {
            NSLog(@"wf_game: MetalBackend: texture %dx%d alloc failed", width, height);
            return NULL;
        }
        [tex replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)width, (NSUInteger)height)
               mipmapLevel:0
                 withBytes:pixels
               bytesPerRow:(NSUInteger)width * 4];

        // +1 from `new...`, handed to the caller. PixelMap owns it from here and
        // releases it through DestroyTexture; TexToHandle balances that
        // ownership across the opaque-handle boundary under either ARC or MRR.
        return TexToHandle(tex);
    }

    void DestroyTexture(RBTextureHandle handle) override
    {
        ReleaseTexHandle(handle);
    }

    // ---- offscreen support (Phase 2) ---------------------------------------
    // The wf_metal:: free functions below are the public face of this; these
    // are the accessors they need. LazyInitPublic exists so the offscreen path
    // can create the device/queue/pipeline BEFORE any draw call, rather than on
    // the first Flush the way the iOS path did.
    bool EnsureInited()          { LazyInit(); return _inited; }
    id<MTLDevice>       Device() { return _device; }
    id<MTLCommandQueue> Queue()  { return _queue;  }

    unsigned long RenderedFrames()   const { return _renderedFrames; }
    unsigned long TrianglesLast()    const { return _trianglesLastFrame; }
    unsigned long TrianglesRunning() const { return _trianglesTotal; }

private:
    friend struct OffscreenTarget;

    id<MTLDevice>              _device          = nil;
    id<MTLCommandQueue>        _queue           = nil;
    id<MTLRenderPipelineState> _pipeline        = nil;
    id<MTLDepthStencilState>   _depthState      = nil;
    id<MTLRenderCommandEncoder> _encoder        = nil;
    id<MTLSamplerState>        _sampler         = nil;
    id<MTLTexture>             _whiteTexture    = nil;
    RBTextureHandle            _boundTexture    = NULL;
    bool                       _inited          = false;

    // Phase 1 measured 1563 triangles/frame against the headless backend; these
    // keep that number comparable now that Metal has replaced it.
    unsigned long _trianglesThisFrame = 0;
    unsigned long _trianglesLastFrame = 0;
    unsigned long _trianglesTotal     = 0;
    unsigned long _renderedFrames     = 0;

    float _proj[16];
    float _mv[16];
    float _mvp[16];
    bool  _mvpDirty  = true;

    bool  _lightingEnabled = false;
    float _ambient[3];
    float _lightDir  [RB_MAX_LIGHTS][3];
    float _lightColor[RB_MAX_LIGHTS][3];

    bool  _fogEnabled = false;
    float _fogColor[3] = { 0.0f, 0.0f, 0.0f };
    float _fogStart = 1.0f;
    float _fogEnd   = 1000.0f;

    const PixelMap* _curTexture = nullptr;
    // Whether the triangles pending in _cpu came from a LIGHTING_PRELIT
    // material. Part of the batch key alongside _curTexture.
    bool  _curPrelit = false;
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

        _device = MTLCreateSystemDefaultDevice();
        if (!_device) {
            NSLog(@"wf_game: MetalBackend: MTLCreateSystemDefaultDevice nil");
            return;
        }

        NSError* err = nil;
        NSString* src = [NSString stringWithUTF8String:kMSL];
        id<MTLLibrary> lib = [_device newLibraryWithSource:src
                                                   options:nil
                                                     error:&err];
        if (!lib) {
            NSLog(@"wf_game: MetalBackend shader compile failed: %@", err);
            return;
        }
        id<MTLFunction> vs = [lib newFunctionWithName:@"wf_vs"];
        id<MTLFunction> fs = [lib newFunctionWithName:@"wf_fs"];

        MTLVertexDescriptor* vd = [[MTLVertexDescriptor alloc] init];
        // attribute 0: pos (float3)
        vd.attributes[0].format      = MTLVertexFormatFloat3;
        vd.attributes[0].offset      = offsetof(Vert, x);
        vd.attributes[0].bufferIndex = 0;
        // attribute 1: color (float3)
        vd.attributes[1].format      = MTLVertexFormatFloat3;
        vd.attributes[1].offset      = offsetof(Vert, r);
        vd.attributes[1].bufferIndex = 0;
        // attribute 2: uv (float2)
        vd.attributes[2].format      = MTLVertexFormatFloat2;
        vd.attributes[2].offset      = offsetof(Vert, u);
        vd.attributes[2].bufferIndex = 0;
        // attribute 3: normal (float3)
        vd.attributes[3].format      = MTLVertexFormatFloat3;
        vd.attributes[3].offset      = offsetof(Vert, nx);
        vd.attributes[3].bufferIndex = 0;
        vd.layouts[0].stride         = sizeof(Vert);
        vd.layouts[0].stepFunction   = MTLVertexStepFunctionPerVertex;

        MTLRenderPipelineDescriptor* pd =
            [[MTLRenderPipelineDescriptor alloc] init];
        pd.vertexFunction                  = vs;
        pd.fragmentFunction                = fs;
        pd.vertexDescriptor                = vd;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        // Depth (Phase 2). Must match the depth texture's format and the
        // render pass descriptor, or pipeline creation fails at runtime.
        pd.depthAttachmentPixelFormat      = kDepthFormat;

        _pipeline = [_device newRenderPipelineStateWithDescriptor:pd
                                                            error:&err];
        if (!_pipeline) {
            NSLog(@"wf_game: MetalBackend pipeline create failed: %@", err);
            return;
        }

        // Standard opaque depth test. GL's default is GL_LESS with writes on,
        // so this matches backend_modern.cc rather than inventing a policy.
        MTLDepthStencilDescriptor* dsd = [[MTLDepthStencilDescriptor alloc] init];
        dsd.depthCompareFunction = MTLCompareFunctionLess;
        dsd.depthWriteEnabled    = YES;
        _depthState = [_device newDepthStencilStateWithDescriptor:dsd];

        // Repeat + linear, matching the GL backend's GFX_ZBUFFER policy that
        // CreateTexture in backend_modern.cc applies via glTexParameteri.
        MTLSamplerDescriptor* sd = [[MTLSamplerDescriptor alloc] init];
        sd.minFilter    = MTLSamplerMinMagFilterLinear;
        sd.magFilter    = MTLSamplerMinMagFilterLinear;
        sd.sAddressMode = MTLSamplerAddressModeRepeat;
        sd.tAddressMode = MTLSamplerAddressModeRepeat;
        _sampler = [_device newSamplerStateWithDescriptor:sd];

        // 1x1 opaque white, bound whenever a batch has no texture. The
        // fragment function declares texture(0) as a required argument, and
        // Metal's validation layer flags an unbound argument even when the
        // shader guards the sample behind use_tex. Four bytes buys that away.
        MTLTextureDescriptor* wd = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                         width:1 height:1 mipmapped:NO];
        wd.usage       = MTLTextureUsageShaderRead;
        wd.storageMode = MTLStorageModeManaged;
        _whiteTexture  = [_device newTextureWithDescriptor:wd];
        const uint8_t white[4] = { 255, 255, 255, 255 };
        [_whiteTexture replaceRegion:MTLRegionMake2D(0, 0, 1, 1)
                         mipmapLevel:0
                           withBytes:white
                         bytesPerRow:4];

        _queue = [_device newCommandQueue];

        NSLog(@"wf_game: MetalBackend ready (device=%@)", _device.name);
        _inited = true;
    }

    void UpdateMvp()
    {
        if (!_mvpDirty) return;
        Mat4Multiply(_proj, _mv, _mvp);
        _mvpDirty = false;
    }

    void BuildUniforms(Uniforms& u)
    {
        u.mvp = Float16ToSimd(_mvp);
        u.mv  = Float16ToSimd(_mv);
        u.ambient  = simd::float3{ _ambient[0], _ambient[1], _ambient[2] };
        // A prelit batch is unlit by definition: its vertex colors are final.
        u.lighting = (_lightingEnabled && !_curPrelit) ? 1 : 0;
        for (int i = 0; i < RB_MAX_LIGHTS; ++i) {
            u.light_dir[i]   = simd::float4{ _lightDir[i][0],   _lightDir[i][1],   _lightDir[i][2],   0.0f };
            u.light_color[i] = simd::float4{ _lightColor[i][0], _lightColor[i][1], _lightColor[i][2], 0.0f };
        }
        u.fog_color = simd::float3{ _fogColor[0], _fogColor[1], _fogColor[2] };
        u.fog       = _fogEnabled ? 1 : 0;
        u.fog_start = _fogStart;
        u.fog_end   = _fogEnd;
        // Phase 3: texture on iff this batch has a PixelMap that actually owns a
        // GPU texture. GetTextureHandle() follows the _parent chain, so a
        // sub-pixelmap correctly reports its atlas parent's texture.
        _boundTexture = _curTexture ? _curTexture->GetTextureHandle() : NULL;
        u.use_tex     = _boundTexture ? 1 : 0;
        u._pad        = 0;
    }

    void Flush()
    {
        if (_cpu.empty()) {
            _curTexture = nullptr;
            _curPrelit  = false;
            return;
        }
        if (!_encoder) {
            // No live encoder yet (Phase 2B3 — engine frame loop not wired).
            // Drop the batched triangles; Phase 2C hands the backend an
            // encoder each frame.
            _cpu.clear();
            _curTexture = nullptr;
            _curPrelit  = false;
            return;
        }
        LazyInit();
        if (!_inited) {
            _cpu.clear();
            _curTexture = nullptr;
            _curPrelit  = false;
            return;
        }
        UpdateMvp();

        Uniforms u;
        BuildUniforms(u);

        // Vertices go through an MTLBuffer, NOT setVertexBytes: the latter is
        // capped at 4 KB and one snowgoons frame batches ~1563 triangles
        // (~206 KB), so every flush would be rejected.
        //
        // A FRESH buffer per flush, not a reused one. Flush() runs on every
        // state change — there are ten call sites — and none of those draws
        // execute until waitUntilCompleted at EndFrame. A single buffer bound
        // at offset 0 by all of them means every draw in the frame reads
        // whatever the LAST flush happened to leave there, so only the final
        // batch renders its own geometry. That is exactly what the first
        // textured macOS capture showed: the right triangle count, most of the
        // scene wrong or missing. Metal's encoder retains the buffer until the
        // command buffer completes, so releasing our reference here is safe and
        // the allocations are bounded by the flush count, not the frame rate.
        const size_t bytes = _cpu.size() * sizeof(Vert);
        id<MTLBuffer> vbuf = [_device newBufferWithBytes:_cpu.data()
                                                  length:bytes
                                                 options:MTLResourceStorageModeShared];
        if (!vbuf) {
            NSLog(@"wf_game: MetalBackend vertex buffer alloc failed (%zu bytes)", bytes);
            _cpu.clear();
            _curTexture = nullptr;
            _curPrelit  = false;
            return;
        }

        [_encoder setRenderPipelineState:_pipeline];
        if (_depthState)
            [_encoder setDepthStencilState:_depthState];
        // One batch = one texture (DrawTriangle flushes on a texture change),
        // so a single bind per flush is correct.
        // Always bind something at texture(0) — see _whiteTexture in LazyInit.
        [_encoder setFragmentTexture:(u.use_tex ? HandleToTex(_boundTexture)
                                                : _whiteTexture)
                             atIndex:0];
        [_encoder setFragmentSamplerState:_sampler atIndex:0];
        [_encoder setVertexBuffer:vbuf offset:0 atIndex:0];
        [_encoder setVertexBytes:&u
                           length:sizeof(Uniforms)
                          atIndex:1];
        [_encoder setFragmentBytes:&u
                             length:sizeof(Uniforms)
                            atIndex:1];
        [_encoder drawPrimitives:MTLPrimitiveTypeTriangle
                     vertexStart:0
                     vertexCount:_cpu.size()];

#if !__has_feature(objc_arc)
        [vbuf release];   // the encoder holds it until the command buffer ends
#endif
        _cpu.clear();
        _curTexture = nullptr;
        _curPrelit  = false;
    }
};

MetalRendererBackend sMetalBackend;

// ---- offscreen render target (Phase 2) --------------------------------------
//
// Owns the colour + depth attachments and this frame's command buffer. Kept a
// plain struct with a single static instance to match the backend's own shape.
//
// macOS ONLY, deliberately. iOS renders into a CAMetalDrawable and has no need
// for this yet, and the storage modes diverge: MTLStorageModeManaged (and the
// synchronizeResource blit it requires) do not exist on iOS, where all
// resources are already shared. Guarding the whole block is cleaner than
// #ifdef-ing three storage modes, and keeps iOS behaviour byte-identical to
// before the file moved here.
#if defined(WF_TARGET_MACOS)

struct OffscreenTarget
{
    id<MTLTexture>             color   = nil;
    id<MTLTexture>             depth   = nil;
    id<MTLCommandBuffer>       cmd     = nil;
    id<MTLRenderCommandEncoder> enc    = nil;
    int  width   = 0;
    int  height  = 0;
    bool haveFrame = false;

    bool EnsureTextures(int w, int h)
    {
        if (color && width == w && height == h)
            return true;

        id<MTLDevice> dev = sMetalBackend.Device();
        if (!dev) return false;

        MTLTextureDescriptor* cd = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                         width:(NSUInteger)w
                                        height:(NSUInteger)h
                                     mipmapped:NO];
        // RenderTarget to draw into; ShaderRead so the editor can sample this
        // same texture in its viewport without a copy (plan O2).
        cd.usage       = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        cd.storageMode = MTLStorageModeManaged;
        color = [dev newTextureWithDescriptor:cd];

        MTLTextureDescriptor* dd = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:kDepthFormat
                                         width:(NSUInteger)w
                                        height:(NSUInteger)h
                                     mipmapped:NO];
        dd.usage       = MTLTextureUsageRenderTarget;
        dd.storageMode = MTLStorageModePrivate;   // never read back
        depth = [dev newTextureWithDescriptor:dd];

        if (!color || !depth) {
            NSLog(@"wf_game: offscreen target %dx%d creation failed", w, h);
            color = nil; depth = nil;
            return false;
        }
        width = w; height = h;
        NSLog(@"wf_game: offscreen Metal target %dx%d ready", w, h);
        return true;
    }
};

OffscreenTarget sOffscreen;

// ---- windowed (CAMetalLayer) path, Phase 4 ----------------------------------
// Shares the depth attachment and the encoder handoff with the offscreen path;
// only the colour attachment and the present differ.
id<CAMetalDrawable>  sDrawable        = nil;
unsigned long        sPresentedCount  = 0;

#endif  // WF_TARGET_MACOS

}  // namespace

RendererBackend* MetalBackendInstance()
{
    return &sMetalBackend;
}

//=============================================================================
// wf_metal:: — the pure-C++ interface declared in gfx/metal/metal_offscreen.h.
//=============================================================================

#if defined(WF_TARGET_MACOS)

namespace wf_metal
{

bool Available()
{
    return sMetalBackend.EnsureInited();
}

bool BeginFrame(int width, int height)
{
    if (width <= 0 || height <= 0) return false;
    if (!sMetalBackend.EnsureInited()) return false;
    if (!sOffscreen.EnsureTextures(width, height)) return false;

    id<MTLCommandQueue> q = sMetalBackend.Queue();
    if (!q) return false;

    MTLRenderPassDescriptor* rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture     = sOffscreen.color;
    rp.colorAttachments[0].loadAction  = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    // Opaque black. Not cornflower blue: a debug clear colour that looks like
    // "something rendered" is exactly how a blank frame gets called a pass.
    rp.colorAttachments[0].clearColor  = MTLClearColorMake(0.0, 0.0, 0.0, 1.0);

    rp.depthAttachment.texture      = sOffscreen.depth;
    rp.depthAttachment.loadAction   = MTLLoadActionClear;
    rp.depthAttachment.storeAction  = MTLStoreActionDontCare;
    rp.depthAttachment.clearDepth   = 1.0;

    sOffscreen.cmd = [q commandBuffer];
    sOffscreen.enc = [sOffscreen.cmd renderCommandEncoderWithDescriptor:rp];
    if (!sOffscreen.enc) {
        sOffscreen.cmd = nil;
        return false;
    }
    // Written out rather than as a compound literal: (MTLViewport){...} is a C
    // construct that Clang only accepts in C++ as an extension.
    MTLViewport vp;
    vp.originX = 0.0;
    vp.originY = 0.0;
    vp.width   = (double)width;
    vp.height  = (double)height;
    vp.znear   = 0.0;
    vp.zfar    = 1.0;
    [sOffscreen.enc setViewport:vp];

    sMetalBackend.SetCurrentEncoder(sOffscreen.enc);
    return true;
}

void EndFrame()
{
    if (!sOffscreen.enc) return;

    [sOffscreen.enc endEncoding];
    sMetalBackend.ClearCurrentEncoder();

    // Managed storage: the GPU-side copy must be synchronised before the CPU
    // can see it. Without this blit the readback returns the cleared texture on
    // discrete-GPU Macs even though the draw succeeded.
    id<MTLBlitCommandEncoder> blit = [sOffscreen.cmd blitCommandEncoder];
    [blit synchronizeResource:sOffscreen.color];
    [blit endEncoding];

    [sOffscreen.cmd commit];
    [sOffscreen.cmd waitUntilCompleted];

    sOffscreen.enc = nil;
    sOffscreen.cmd = nil;
    sOffscreen.haveFrame = true;
}

bool ReadbackRGBA8(unsigned char* dst, int width, int height)
{
    if (!dst || !sOffscreen.haveFrame) return false;
    // One source for both modes: the windowed path blits its drawable into
    // sOffscreen.color before presenting (see EndFrameToLayer).
    id<MTLTexture> src = sOffscreen.color;
    if (!src) return false;
    if ((NSUInteger)width  != [src width] ||
        (NSUInteger)height != [src height]) return false;

    const size_t rowBytes = (size_t)width * 4;
    std::vector<unsigned char> bgra(rowBytes * (size_t)height);
    [src getBytes:bgra.data()
                   bytesPerRow:rowBytes
                    fromRegion:MTLRegionMake2D(0, 0,
                                               (NSUInteger)width,
                                               (NSUInteger)height)
                   mipmapLevel:0];

    // BGRA -> RGBA. Row order already matches: Metal's texture origin is
    // top-left, which is also stb_image_write's first row, so no vertical flip.
    for (size_t i = 0; i < bgra.size(); i += 4) {
        dst[i + 0] = bgra[i + 2];
        dst[i + 1] = bgra[i + 1];
        dst[i + 2] = bgra[i + 0];
        dst[i + 3] = bgra[i + 3];
    }
    return true;
}

void* ColorTextureHandle()
{
    return (__bridge void*)sOffscreen.color;
}

bool BeginFrameToLayer(void* caMetalLayer, int width, int height)
{
    if (!caMetalLayer || width <= 0 || height <= 0) return false;
    if (!sMetalBackend.EnsureInited()) return false;

    CAMetalLayer* layer = (__bridge CAMetalLayer*)caMetalLayer;
    sDrawable = [layer nextDrawable];
    if (!sDrawable) {
        // Legitimate and transient: the layer hands out a bounded pool and
        // returns nil when they are all in flight. Skipping the frame is
        // correct; asserting would turn a hitch into a crash.
        return false;
    }
#if !__has_feature(objc_arc)
    [sDrawable retain];
#endif

    // Depth must match the drawable's size, so reuse the offscreen target's
    // depth texture and let it resize with the window.
    if (!sOffscreen.EnsureTextures(width, height)) return false;

    id<MTLCommandQueue> q = sMetalBackend.Queue();
    if (!q) return false;

    MTLRenderPassDescriptor* rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture     = sDrawable.texture;
    rp.colorAttachments[0].loadAction  = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    rp.colorAttachments[0].clearColor  = MTLClearColorMake(0.0, 0.0, 0.0, 1.0);
    rp.depthAttachment.texture      = sOffscreen.depth;
    rp.depthAttachment.loadAction   = MTLLoadActionClear;
    rp.depthAttachment.storeAction  = MTLStoreActionDontCare;
    rp.depthAttachment.clearDepth   = 1.0;

    sOffscreen.cmd = [q commandBuffer];
    sOffscreen.enc = [sOffscreen.cmd renderCommandEncoderWithDescriptor:rp];
    if (!sOffscreen.enc) { sOffscreen.cmd = nil; return false; }

    MTLViewport vp;
    vp.originX = 0.0; vp.originY = 0.0;
    vp.width   = (double)width; vp.height = (double)height;
    vp.znear   = 0.0; vp.zfar = 1.0;
    [sOffscreen.enc setViewport:vp];

    sMetalBackend.SetCurrentEncoder(sOffscreen.enc);
    return true;
}

void EndFrameToLayer()
{
    if (!sOffscreen.enc) return;

    [sOffscreen.enc endEncoding];
    sMetalBackend.ClearCurrentEncoder();

    // Copy the drawable into the offscreen colour texture so --capture-frame
    // can read it. NOT a direct getBytes on the drawable: a CAMetalLayer
    // drawable's storage mode is the layer's business and may be private, in
    // which case a CPU read is invalid. sOffscreen.color is Managed, is already
    // the drawable's size (EnsureTextures ran in BeginFrameToLayer), and the
    // synchronize below makes it CPU-visible — so one readback path serves both
    // windowed and headless modes.
    if (sOffscreen.color)
    {
        id<MTLBlitCommandEncoder> copy = [sOffscreen.cmd blitCommandEncoder];
        [copy copyFromTexture:sDrawable.texture
                  sourceSlice:0 sourceLevel:0
                 sourceOrigin:MTLOriginMake(0, 0, 0)
                   sourceSize:MTLSizeMake(sOffscreen.width, sOffscreen.height, 1)
                    toTexture:sOffscreen.color
             destinationSlice:0 destinationLevel:0
            destinationOrigin:MTLOriginMake(0, 0, 0)];
        [copy synchronizeResource:sOffscreen.color];
        [copy endEncoding];
    }

    [sOffscreen.cmd presentDrawable:sDrawable];
    [sOffscreen.cmd commit];
    [sOffscreen.cmd waitUntilCompleted];
    ++sPresentedCount;

#if !__has_feature(objc_arc)
    [sDrawable release];
#endif
    sDrawable      = nil;
    sOffscreen.enc = nil;
    sOffscreen.cmd = nil;
    sOffscreen.haveFrame = true;
}

unsigned long PresentedDrawableCount() { return sPresentedCount; }

unsigned long RenderedFrameCount() { return sMetalBackend.RenderedFrames();   }
unsigned long TrianglesLastFrame() { return sMetalBackend.TrianglesLast();    }
unsigned long TrianglesTotal()     { return sMetalBackend.TrianglesRunning(); }

}  // namespace wf_metal

#endif  // WF_TARGET_MACOS
