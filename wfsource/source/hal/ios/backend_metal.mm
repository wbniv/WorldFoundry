//=============================================================================
// hal/ios/backend_metal.mm: Metal implementation of RendererBackend
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2B3: the Metal sibling of gfx/glpipeline/backend_modern.cc.
//
// Mirrors backend_modern's CPU-side state + triangle batching; MSL shaders
// inline and runtime-compiled via [MTLDevice newLibraryWithSource:] so the
// build stays Codemagic-native (no .metal file + Xcode build phase).
//
// For Phase 2B3 the deliverable is "compiles + links + MetalBackendInstance()
// is reachable via RendererBackendGet()". Nothing in the engine drives it
// yet — Phase 2C wires MetalView's CADisplayLink callback to the engine
// frame loop and hands the backend a live MTLRenderCommandEncoder each
// frame via SetCurrentEncoder / ClearCurrentEncoder.
//
// Textures are not yet supported — DrawTriangle ignores the PixelMap*
// argument and always draws flat-lit. Phase 2C+ adds a PixelMap→MTLTexture
// upload path that parallels PixelMap::SetGLTexture on the GL side.
//=============================================================================

#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#import <simd/simd.h>

#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#include <math/matrix34.hp>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

namespace
{

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
                      constant Uniforms& u         [[buffer(1)]])
{
    float4 c = float4(v.color * v.lit, 1.0);
    // Phase 2B3: texture path disabled, PixelMap→MTLTexture upload lands
    // with the frame-loop wiring in Phase 2C.
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

static void Mat4Perspective(float fovDegY, float aspect, float nz, float fz,
                            float out[16])
{
    const float f =
        1.0f / std::tan((fovDegY * 0.5f) * (3.14159265358979323846f / 180.0f));
    std::memset(out, 0, sizeof(float) * 16);
    out[0]  = f / aspect;
    out[5]  = f;
    out[10] = (fz + nz) / (nz - fz);
    out[11] = -1.0f;
    out[14] = (2.0f * fz * nz) / (nz - fz);
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
        static bool sLoggedFirstEndFrame = true;
        if (sLoggedFirstEndFrame) {
            sLoggedFirstEndFrame = false;
            std::fprintf(stderr,
                         "wf_game: first MetalBackend EndFrame — cpu=%zu tris, encoder=%s\n",
                         _cpu.size() / 3, _encoder ? "live" : "nil");
        }
        Flush();
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

private:
    id<MTLDevice>              _device          = nil;
    id<MTLRenderPipelineState> _pipeline        = nil;
    id<MTLRenderCommandEncoder> _encoder        = nil;
    bool                       _inited          = false;

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

        _pipeline = [_device newRenderPipelineStateWithDescriptor:pd
                                                            error:&err];
        if (!_pipeline) {
            NSLog(@"wf_game: MetalBackend pipeline create failed: %@", err);
            return;
        }

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
        u.lighting = _lightingEnabled ? 1 : 0;
        for (int i = 0; i < RB_MAX_LIGHTS; ++i) {
            u.light_dir[i]   = simd::float4{ _lightDir[i][0],   _lightDir[i][1],   _lightDir[i][2],   0.0f };
            u.light_color[i] = simd::float4{ _lightColor[i][0], _lightColor[i][1], _lightColor[i][2], 0.0f };
        }
        u.fog_color = simd::float3{ _fogColor[0], _fogColor[1], _fogColor[2] };
        u.fog       = _fogEnabled ? 1 : 0;
        u.fog_start = _fogStart;
        u.fog_end   = _fogEnd;
        u.use_tex   = 0;  // Phase 2C adds texture binding.
        u._pad      = 0;
    }

    void Flush()
    {
        if (_cpu.empty()) {
            _curTexture = nullptr;
            return;
        }
        if (!_encoder) {
            // No live encoder yet (Phase 2B3 — engine frame loop not wired).
            // Drop the batched triangles; Phase 2C hands the backend an
            // encoder each frame.
            _cpu.clear();
            _curTexture = nullptr;
            return;
        }
        LazyInit();
        if (!_inited) {
            _cpu.clear();
            _curTexture = nullptr;
            return;
        }
        UpdateMvp();

        Uniforms u;
        BuildUniforms(u);

        [_encoder setRenderPipelineState:_pipeline];
        [_encoder setVertexBytes:_cpu.data()
                           length:_cpu.size() * sizeof(Vert)
                          atIndex:0];
        [_encoder setVertexBytes:&u
                           length:sizeof(Uniforms)
                          atIndex:1];
        [_encoder setFragmentBytes:&u
                             length:sizeof(Uniforms)
                            atIndex:1];
        [_encoder drawPrimitives:MTLPrimitiveTypeTriangle
                     vertexStart:0
                     vertexCount:_cpu.size()];

        _cpu.clear();
        _curTexture = nullptr;
    }
};

MetalRendererBackend sMetalBackend;

}  // namespace

RendererBackend* MetalBackendInstance()
{
    return &sMetalBackend;
}

// ---- Phase 2C-B frame bridge ------------------------------------------------
// Display::RenderBegin / RenderEnd (display_ios.cc) call these from the engine
// thread. Between them the engine batches triangles into sMetalBackend;
// RenderEnd's backend.EndFrame() flushes the batch into the live encoder, then
// WFIosRenderEnd ends the encoder and commits.
//
// Layer + queue come from hal/ios/metal_view.mm.
extern CAMetalLayer*       gWFMetalLayer;
extern id<MTLCommandQueue> gWFMetalQueue;

static id<MTLCommandBuffer>        sFrameCmdBuffer = nil;
static id<CAMetalDrawable>         sFrameDrawable  = nil;
static id<MTLRenderCommandEncoder> sFrameEncoder   = nil;

extern "C" void
WFIosRenderBegin(float clearR, float clearG, float clearB)
{
    static bool sFirstCall    = true;
    static bool sLoggedNoLayer = false;
    static bool sLoggedNoDraw  = false;

    if (sFirstCall) {
        sFirstCall = false;
        std::fprintf(stderr, "wf_game: → first WFIosRenderBegin "
                             "layer=%p queue=%p clear=(%.2f,%.2f,%.2f)\n",
                     (void*)gWFMetalLayer, (void*)gWFMetalQueue,
                     clearR, clearG, clearB);
    }
    if (!gWFMetalLayer || !gWFMetalQueue) {
        if (!sLoggedNoLayer) {
            sLoggedNoLayer = true;
            std::fprintf(stderr, "wf_game: WFIosRenderBegin — layer/queue nil\n");
        }
        return;
    }

    id<CAMetalDrawable> drawable = [gWFMetalLayer nextDrawable];
    if (!drawable) {
        if (!sLoggedNoDraw) {
            sLoggedNoDraw = true;
            std::fprintf(stderr, "wf_game: WFIosRenderBegin — nextDrawable nil (first occurrence)\n");
        }
        return;   // swap chain busy — drop this frame.
    }

    MTLRenderPassDescriptor* rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture     = drawable.texture;
    rp.colorAttachments[0].loadAction  = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    rp.colorAttachments[0].clearColor  =
        MTLClearColorMake(clearR, clearG, clearB, 1.0);

    id<MTLCommandBuffer> cb  = [gWFMetalQueue commandBuffer];
    id<MTLRenderCommandEncoder> enc =
        [cb renderCommandEncoderWithDescriptor:rp];

    sFrameCmdBuffer = cb;
    sFrameDrawable  = drawable;
    sFrameEncoder   = enc;
    sMetalBackend.SetCurrentEncoder(enc);
}

extern "C" void
WFIosRenderEnd(void)
{
    if (!sFrameEncoder) return;   // matched a skipped RenderBegin.

    // Display::RenderEnd has already invoked backend.EndFrame(), which calls
    // Flush() and submits any batched triangles into sFrameEncoder. Tear down.
    sMetalBackend.ClearCurrentEncoder();
    [sFrameEncoder endEncoding];
    [sFrameCmdBuffer presentDrawable:sFrameDrawable];
    [sFrameCmdBuffer commit];

    sFrameEncoder   = nil;
    sFrameDrawable  = nil;
    sFrameCmdBuffer = nil;
}
