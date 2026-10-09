//=============================================================================
// gfx/glpipeline/backend_factory.cc: RendererBackend singleton accessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Modern (VBO + GLSL) backend on Linux + Android.
// Metal backend on BOTH Apple targets (gfx/metal/backend_metal.mm) — macOS
// joined iOS in Phase 2 of docs/plans/2026-09-20-macos-metal-renderer.md, which
// also moved that file out of hal/ios/ since it is renderer code, not iOS HAL
// code (D3). macOS previously used the headless no-op stub
// (engine/stubs/renderer_stub.cc); that stub is still built and still selected
// by nothing, kept as the fallback if a machine has no Metal device.
// Legacy fixed-function backend retired Android Phase 0 step 4c/f.
//============================================================================

#include <gfx/renderer_backend.hp>
#include <gfx/static_mesh.hp>
#include <game/runtime_profile.hp>
#include <math/matrix34.hp>
#include <hal/halbase.h>
#include <memory/lmalloc.hp>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <cstddef>

// Translucent faces must follow ALL opaque submissions, including scenery
// encountered later in the level. Store vertices in eye space so sorting is
// shared across actors and backends, rather than sorting each mesh separately.
// The bounded queue uses the caller's frame allocator and is released before
// EndFrame returns; opaque-only scenes allocate nothing.
class CompositingBackend : public RendererBackend
{
    struct State {
        float ambient[3];
        float light[RB_MAX_LIGHTS][6];
        float fog[5];
        int32 lighting, fogEnabled, cutout, textureModulation, paletteEnabled;
        unsigned paletteDark, paletteLight;
    };
    struct Triangle {
        RBVertex vertices[3];
        float normal[3], depth, opacity;
        const PixelMap* texture;
        int32 state, order, cullExempt, prelit;
    };
    enum { MAX_TRIANGLES = 8192, MAX_STATES = 64 };
    RendererBackend& _backend;
    Memory& _memory;
    Triangle* _triangles = NULL;
    int32 _count = 0, _stateCount = 0;
    State _state = {}, _states[MAX_STATES];
    Matrix34 _modelView;
    float _matrix[12] = {1,0,0,0,1,0,0,0,1,0,0,0};
    float _opacity = 1;
    bool _identity = true;

    void Transform(float x, float y, float z, float* out, bool position) const
    {
        for (int32 i = 0; i < 3; ++i)
            out[i] = _matrix[i]*x + _matrix[3+i]*y + _matrix[6+i]*z
                   + (position ? _matrix[9+i] : 0);
    }
    int32 CaptureState()
    {
        for (int32 i = 0; i < _stateCount; ++i)
            if (!std::memcmp(&_state, &_states[i], sizeof(State))) return i;
        AssertMsg(_stateCount < MAX_STATES, "translucent state count must be < 64");
        _states[_stateCount] = _state;
        return _stateCount++;
    }
    void ApplyState(const State& state, const State* previous = NULL)
    {
        // Palette-only changes must not replay uniform setters: those flush
        // GPU batches, defeating the per-vertex palette when fins interleave.
        if (previous && !std::memcmp(&state, previous, offsetof(State, paletteEnabled))) {
            _backend.SetTexturePalette(state.paletteEnabled!=0,state.paletteDark,state.paletteLight);
            return;
        }
        _backend.SetAmbient(state.ambient[0], state.ambient[1], state.ambient[2]);
        for (int32 i = 0; i < RB_MAX_LIGHTS; ++i) {
            const float* l = state.light[i];
            _backend.SetDirLight(i,l[0],l[1],l[2],l[3],l[4],l[5]);
        }
        _backend.SetLightingEnabled(state.lighting != 0);
        _backend.SetFog(state.fog[0],state.fog[1],state.fog[2],state.fog[3],state.fog[4]);
        _backend.SetFogEnabled(state.fogEnabled != 0);
        _backend.SetAlphaCutout(state.cutout != 0);
        _backend.SetTextureModulation(state.textureModulation != 0);
        _backend.SetTexturePalette(state.paletteEnabled!=0,state.paletteDark,state.paletteLight);
    }
    static int Compare(const void* a, const void* b)
    {
        const Triangle& x = *static_cast<const Triangle*>(a);
        const Triangle& y = *static_cast<const Triangle*>(b);
        // Camera looks down -Z: more negative is farther away. Submission
        // order breaks equal-depth ties deterministically.
        if (x.depth < y.depth) return -1;
        if (x.depth > y.depth) return 1;
        return (x.order > y.order) - (x.order < y.order);
    }
    void Drain()
    {
        if (!_triangles) return;
        std::qsort(_triangles, _count, sizeof(Triangle), Compare);
        _backend.ResetModelView(); // flush opaque work before blending
        int32 state = -1;
        for (int32 i = 0; i < _count; ++i) {
            const Triangle& t = _triangles[i];
            if (t.state != state) { ApplyState(_states[t.state], state >= 0 ? &_states[state] : NULL); state = t.state; }
            _backend.SetOpacity(t.opacity);
            _backend.DrawTriangle(t.vertices[0],t.vertices[1],t.vertices[2],
                t.normal[0],t.normal[1],t.normal[2],t.texture,t.cullExempt != 0,t.prelit != 0);
        }
        _backend.SetOpacity(1); // flush last blended batch
        ApplyState(_state, state >= 0 ? &_states[state] : NULL); // directions already in eye space
        if (!_identity) _backend.SetModelView(_modelView);
        _memory.Free(_triangles);
        _triangles = NULL;
        _count = _stateCount = 0;
    }
public:
    CompositingBackend(RendererBackend& backend, Memory& memory)
        : _backend(backend), _memory(memory) {}
    void SetProjection(float f, float a, float n, float z) override
    { Drain(); _backend.SetProjection(f,a,n,z); }
    void SetModelView(const Matrix34& m) override
    {
        _modelView = m; _identity = false;
        for (int32 r = 0; r < 4; ++r)
            for (int32 c = 0; c < 3; ++c) _matrix[r*3+c] = m[r][c].AsFloat();
        _backend.SetModelView(m);
    }
    void ResetModelView() override
    {
        std::memset(_matrix,0,sizeof(_matrix));
        _matrix[0] = _matrix[4] = _matrix[8] = 1; _identity = true;
        _backend.ResetModelView();
    }
    void SetAmbient(float r, float g, float b) override
    { _state.ambient[0]=r; _state.ambient[1]=g; _state.ambient[2]=b; _backend.SetAmbient(r,g,b); }
    void SetDirLight(int i,float x,float y,float z,float r,float g,float b) override
    {
        if (i < 0 || i >= RB_MAX_LIGHTS) return;
        float* l = _state.light[i]; Transform(x,y,z,l,false);
        float length = std::sqrt(l[0]*l[0]+l[1]*l[1]+l[2]*l[2]);
        if (length > 1e-6f) for (int32 c=0;c<3;++c) l[c] /= length;
        l[3]=r; l[4]=g; l[5]=b; _backend.SetDirLight(i,x,y,z,r,g,b);
    }
    void SetLightingEnabled(bool e) override { _state.lighting=e; _backend.SetLightingEnabled(e); }
    void SetFog(float r,float g,float b,float s,float e) override
    {
        _state.fog[0]=r; _state.fog[1]=g; _state.fog[2]=b; _state.fog[3]=s; _state.fog[4]=e;
        _backend.SetFog(r,g,b,s,e);
    }
    void SetFogEnabled(bool e) override { _state.fogEnabled=e; _backend.SetFogEnabled(e); }
    void SetAlphaCutout(bool e) override { _state.cutout=e; _backend.SetAlphaCutout(e); }
    void SetTextureModulation(bool e) override
    { _state.textureModulation=e; _backend.SetTextureModulation(e); }
    void SetTexturePalette(bool e,unsigned d,unsigned l) override
    { _state.paletteEnabled=e; _state.paletteDark=d; _state.paletteLight=l; _backend.SetTexturePalette(e,d,l); }
    void SetOpacity(float opacity) override
    { assert(opacity >= 0 && opacity <= 1); _opacity=opacity; }
    void DrawTriangle(const RBVertex& a,const RBVertex& b,const RBVertex& c,
                      float nx,float ny,float nz,const PixelMap* texture,bool exempt,bool prelit) override
    {
        if (_opacity >= 1) { _backend.SetOpacity(1); _backend.DrawTriangle(a,b,c,nx,ny,nz,texture,exempt,prelit); return; }
        if (_opacity == 0) return;
        if (!_triangles) _triangles = static_cast<Triangle*>(_memory.Allocate(
            MAX_TRIANGLES*sizeof(Triangle) ASSERTIONS(COMMA __FILE__ COMMA __LINE__)));
        AssertMsg(_count < MAX_TRIANGLES, "translucent triangle count must be < 8192");
        Triangle& t = _triangles[_count];
        t.vertices[0]=a; t.vertices[1]=b; t.vertices[2]=c;
        for (int32 i=0;i<3;++i) {
            RBVertex& v=t.vertices[i]; float eye[3]; Transform(v.x,v.y,v.z,eye,true);
            v.x=eye[0]; v.y=eye[1]; v.z=eye[2];
        }
        Transform(nx,ny,nz,t.normal,false);
        t.depth=(t.vertices[0].z+t.vertices[1].z+t.vertices[2].z)/3;
        t.opacity=_opacity; t.texture=texture; t.state=CaptureState();
        t.order=_count++; t.cullExempt=exempt; t.prelit=prelit;
    }
    void FlushTranslucency() override { Drain(); }
    void DrawOverlay(const PhonepadRect* rects, int count, int w, int h) override
    { Drain(); _backend.DrawOverlay(rects, count, w, h); }
    bool BitmapTextSupported() const override { return _backend.BitmapTextSupported(); }
    unsigned TextureGeneration() const override { return _backend.TextureGeneration(); }
    void CaptureTextView() override { _backend.CaptureTextView(); }
    bool ProjectTextAnchor(float x,float y,float z,int w,int h,float& px,float& py,float& depth) const override
    { return _backend.ProjectTextAnchor(x,y,z,w,h,px,py,depth); }
    void DrawGlyphs(const bitmaptext::Quad* q,int n,int w,int h,RBTextureHandle t,bool depth,float x,float y,float z) override
    { Drain(); _backend.DrawGlyphs(q,n,w,h,t,depth,x,y,z); }
    void EndFrame() override
    {
        Drain(); _backend.EndFrame();
        if (StaticMeshEndFrame())   // E3 per-frame reset; true = test hook asks for a simulated surface loss
            SimulateSurfaceLoss();
    }
    static void SimulateSurfaceLoss();
    RBTextureHandle CreateTexture(int w,int h,RBTextureFormat f,const void* p) override
    { return _backend.CreateTexture(w,h,f,p); }
    void DestroyTexture(RBTextureHandle h) override { Drain(); _backend.DestroyTexture(h); }
    bool ReloadProgram(const char* v,const char* f,std::string& log) override
    { Drain(); return _backend.ReloadProgram(v,f,log); }

    // Static meshes (E3 phase 1). Only opaque runs are drawn this way (the
    // caller streams translucent ones, which this layer still queues and
    // sorts), so DrawStaticTriangles does what DrawTriangle does for an
    // opaque triangle: reset the backend's opacity, then hand it on.
    bool StaticMeshSupported() const override { return _backend.StaticMeshSupported(); }
    RBStaticMeshHandle CreateStaticMesh(const RBStaticTriangle* t, int n) override
    { return _backend.CreateStaticMesh(t, n); }
    void DestroyStaticMesh(RBStaticMeshHandle m) override { _backend.DestroyStaticMesh(m); }
    bool StaticMeshLive(RBStaticMeshHandle m) const override { return _backend.StaticMeshLive(m); }
    void StaticMeshBytes(size_t& gpu, size_t& cpu) const override { _backend.StaticMeshBytes(gpu, cpu); }
    void DrawStaticTriangles(RBStaticMeshHandle m, const unsigned* t, int n,
                             const PixelMap* texture, bool prelit) override
    {
        AssertMsg(_opacity >= 1, "static mesh runs are opaque");
        _backend.SetOpacity(1);
        _backend.DrawStaticTriangles(m, t, n, texture, prelit);
    }
};

#if defined(WF_TARGET_IOS) || defined(WF_TARGET_MACOS)
RendererBackend* MetalBackendInstance();
#else
RendererBackend* ModernBackendInstance();
#endif

// Set only while a static mesh is being baked (gfx/glpipeline/static_mesh.cc);
// a single load and branch on the common path.
static RendererBackend* sRecorder = NULL;

void RendererBackendSetRecorder(RendererBackend* recorder)
{
    sRecorder = recorder;
}

// WF_STATIC_MESH_TEST=loss:N (gfx/static_mesh.hp): drop every GL name the GL
// backend holds, as the Android surface-loss hook does, so the re-bake path can
// be tested on desktop. The old objects leak in this test; the context lives.
void CompositingBackend::SimulateSurfaceLoss()
{
#if !defined(WF_TARGET_IOS) && !defined(WF_TARGET_MACOS)
    void ModernBackendSimulateSurfaceLoss();
    ModernBackendSimulateSurfaceLoss();
#endif
}

RendererBackend& RendererBackendGet()
{
    if (sRecorder) return *sRecorder;
#if defined(WF_TARGET_IOS) || defined(WF_TARGET_MACOS)
    static RendererBackend* s = MetalBackendInstance();
#else
    static RendererBackend* s = ModernBackendInstance();
#endif
    static CompositingBackend composite(*s, HALLmalloc);
    return composite;
}
