#include <gfx/skinned_mesh.hp>
#include <gfx/rendobj3.hp>
#include <gfx/material.hp>
#include <gfx/backface_cull.hp>
#include <gfx/static_mesh.hp>
#include <game/runtime_profile.hp>
#include <cstdio>
#include <cstring>
#include <cmath>

namespace {
SkinningMode mode = SkinningMode::Cpu;
struct Run { int first, count; const PixelMap* texture; bool prelit, twoSided, modulate; };
size_t stagingBytes = 0,poseBytes=0;

// Capture the real poly renderer's UVs, primitive colors and material state.
// Skin binds are attached in exactly the original face/corner order.
class Recorder : public RendererBackend {
public:
    std::vector<RBSkinnedVertex> vertices;
    std::vector<Run> runs;
    bool modulate=false, palette=false; unsigned dark=0, light=0;
    float opacity=1;
    void SetProjection(float,float,float,float) override {}
    void SetModelView(const Matrix34&) override {}
    void ResetModelView() override {}
    void SetAmbient(float,float,float) override {}
    void SetDirLight(int,float,float,float,float,float,float) override {}
    void SetLightingEnabled(bool) override {}
    void SetFog(float,float,float,float,float) override {}
    void SetFogEnabled(bool) override {}
    void SetTextureModulation(bool b) override { modulate=b; }
    void SetTexturePalette(bool b,unsigned d,unsigned l) override { palette=b; dark=d; light=l; }
    void SetOpacity(float a) override { opacity=a; }
    void EndFrame() override {}
    RBTextureHandle CreateTexture(int,int,RBTextureFormat,const void*) override { return NULL; }
    void DestroyTexture(RBTextureHandle) override {}
    void DrawTriangle(const RBVertex& a,const RBVertex& b,const RBVertex& c,float nx,float ny,float nz,
                      const PixelMap* tex,bool two,bool prelit) override {
        int first=vertices.size();
        if (runs.empty() || runs.back().texture!=tex || runs.back().prelit!=prelit || runs.back().twoSided!=two || runs.back().modulate!=modulate)
            runs.push_back({first,0,tex,prelit,two,modulate});
        for (const RBVertex* v : {&a,&b,&c}) {
            RBSkinnedVertex out{}; out.vertex=*v; out.normal[0]=nx; out.normal[1]=ny; out.normal[2]=nz; out.opacity=opacity;
            for (int k=0;k<3;++k) { int shift=16-8*k; out.paletteDark[k]=((dark>>shift)&255)/255.f; out.paletteLight[k]=((light>>shift)&255)/255.f; }
            out.paletteDark[3]=palette ? 1.f : 0.f;
            vertices.push_back(out); ++runs.back().count;
        }
    }
};
}

struct SkinMeshState {
    RBSkinnedMeshHandle handle=NULL;
    std::vector<Run> runs;
    unsigned version=0, atlas=0;
    std::vector<unsigned> materials;
    size_t bytes=0;
    bool drew=false;
};

SkinningMode SkinningGetMode() { return mode; }
bool SkinningSetMode(const char* name) {
    if (!std::strcmp(name,"cpu")) mode=SkinningMode::Cpu;
    else if (!std::strcmp(name,"cpu-no-cull")) mode=SkinningMode::CpuNoCull;
    else if (!std::strcmp(name,"gpu-no-cull")) mode=SkinningMode::GpuNoCull;
    else if (!std::strcmp(name,"gpu")) mode=SkinningMode::Gpu;
    else return false;
    std::fprintf(stderr,"skinning: requested=%s\n",name); return true;
}

void SkinMeshDestroy(SkinMeshState* state) {
    if (!state) return;
    RendererBackendGet().DestroySkinnedMesh(state->handle);
    stagingBytes-=state->bytes; delete state;
}

void SkinPoseResidentBytes(size_t bytes,bool add) { if(add)poseBytes+=bytes;else poseBytes-=bytes; }

void SkinMeshSampleGauges() {
    size_t gpu=0,cpu=0; RendererBackendGet().SkinnedMeshBytes(gpu,cpu);
    wf_profile::count(wf_profile::SkinGpuBytes,gpu);
    wf_profile::count(wf_profile::SkinCpuBytes,stagingBytes+poseBytes+cpu);
}

bool RenderObject3D::SkinEligible() const {
    if (_handleCount || _materialCount<=0 || !_dfrm) return false;
    for (int i=0;i<_materialCount;++i) {
        const Material& m=_materialList[i];
        if (m.IsAlphaCutout() || m.GetOpacity()!=1 || (m.GetMaterialFlags()&Material::TEXTURE_TRANSLUCENCY_ON)) return false;
    }
    return true;
}

bool RenderObject3D::RenderSkinned(const Matrix34& position) {
    if (!_skinPose) return false;
    auto& backend=RendererBackendGet();
    auto fallback=[&](unsigned flag,const char* reason) {
        wf_profile::count(wf_profile::SkinFallbacks);
        if(!(_skinFallbackReasons&flag)){std::fprintf(stderr,"skinning: effective=cpu reason=%s\n",reason);_skinFallbackReasons|=flag;}
        if(_skinPose->MaterializeCpu(*this))return true;
        std::fprintf(stderr,"skinning: CPU materialization failed; draw skipped\n");return false;
    };
    float mv[16]; WfMatrix34ToGL(position,mv); WfCullFrame frame; WfCullFramePrepare(mv,frame);
    const float det=mv[0]*(mv[5]*mv[10]-mv[6]*mv[9])-mv[4]*(mv[1]*mv[10]-mv[2]*mv[9])+mv[8]*(mv[1]*mv[6]-mv[2]*mv[5]);
    bool finite=true;for(float x:mv)if(!std::isfinite(x))finite=false;
    if(SkinningGetMode()==SkinningMode::Cpu || SkinningGetMode()==SkinningMode::CpuNoCull)return !fallback(1,"cpu-mode");
    if(!SkinEligible())return !fallback(2,"material-or-handle");
    if(!finite || !frame.similarity || !(det>0))return !fallback(4,"transform");
    if(!backend.SkinnedMeshSupported())return !fallback(8,"backend");
    bool stale=_skinMesh && (_skinMesh->version!=_staticVersion || _skinMesh->atlas!=StaticMeshAtlasGeneration()
                             || !backend.SkinnedMeshLive(_skinMesh->handle) || _skinMesh->materials.size()!=size_t(_materialCount)*4);
    if (_skinMesh && !stale) for(int i=0;i<_materialCount;++i) {
        const Material& m=_materialList[i];const Color& c=m.GetColor();
        const unsigned values[4]={unsigned(m.GetMaterialFlags()),(unsigned(c.Red())<<16)|(unsigned(c.Green())<<8)|c.Blue(),m.PaletteDark(),m.PaletteLight()};
        for(int k=0;k<4;++k)if(_skinMesh->materials[4*i+k]!=values[k])stale=true;
    }
    if(stale){SkinMeshDestroy(_skinMesh);_skinMesh=NULL;}
    const auto& skin=_skinPose->Skin();
    if (!_skinMesh) {
        Recorder recorder;
        RendererBackendSetRecorder(&recorder); StreamFaces(0,_faceCount); RendererBackendSetRecorder(NULL);
        if (recorder.vertices.size()!=size_t(_faceCount)*3 || skin.Bindings().size()!=size_t(_vertexCount)) { return !fallback(16,"recording"); }
        for (int f=0;f<_faceCount;++f) {
            const TriFace& face=_faceList[f]; int indices[3]={face.v1Index,face.v2Index,face.v3Index};
            for (int k=0;k<3;++k) {
                auto& v=recorder.vertices[3*f+k]; const auto& bind=skin.Bindings()[indices[k]];
                v.vertex.x=bind.point[0];v.vertex.y=bind.point[1];v.vertex.z=bind.point[2];
                std::memcpy(v.joints,bind.joints,4);std::memcpy(v.weights,bind.weights,4);
            }
        }
        const auto handle=backend.CreateSkinnedMesh(recorder.vertices.data(),recorder.vertices.size());
        if (!handle) { return !fallback(32,"resource-create"); }
        _skinMesh=new SkinMeshState;
        _skinMesh->handle=handle; _skinMesh->runs=std::move(recorder.runs);
        _skinMesh->version=_staticVersion;_skinMesh->atlas=StaticMeshAtlasGeneration();
        for(int i=0;i<_materialCount;++i) {
            const Material& m=_materialList[i];const Color& c=m.GetColor();
            _skinMesh->materials.push_back(m.GetMaterialFlags());
            _skinMesh->materials.push_back((unsigned(c.Red())<<16)|(unsigned(c.Green())<<8)|c.Blue());
            _skinMesh->materials.push_back(m.PaletteDark());_skinMesh->materials.push_back(m.PaletteLight());
        }
        _skinMesh->bytes=sizeof(SkinMeshState)+_skinMesh->runs.capacity()*sizeof(Run)+_skinMesh->materials.capacity()*sizeof(unsigned);
        stagingBytes+=_skinMesh->bytes; wf_profile::count(wf_profile::SkinRebuilds);
    }
    wf_profile::Scope submit(wf_profile::SkinSubmitCpu);
    for (const Run& run : _skinMesh->runs) {
        backend.SetAlphaCutout(false);backend.SetTextureModulation(run.modulate);backend.SetOpacity(1);
        if (!backend.DrawSkinnedMesh(_skinMesh->handle,run.first,run.count,skin.Palette().data(),skin.Palette().size()/12,
                                    run.texture,run.prelit,run.twoSided,SkinningGetMode()==SkinningMode::Gpu && WfBackfaceCullEnabled())) {
            if(fallback(64,"backend-draw"))StreamFaces(run.first/3,(run.first+run.count)/3);
        } else if(!_skinMesh->drew) {
            _skinMesh->drew=true;
            std::fprintf(stderr,"skinning: effective=%s vertices=%d faces=%d palette=%zu\n",
                SkinningGetMode()==SkinningMode::Gpu ? "gpu" : "gpu-no-cull",_vertexCount,_faceCount,skin.Palette().size()/12);
        }
    }
    return true;
}
