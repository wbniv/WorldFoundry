"""Exercise the real common compositor with a recording backend (no GPU)."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_cross_actor_sort_state_and_frame_lifetime(tmp_path):
    # Small platform/allocator adapters let us compile the production compositor
    # without a window. Backend records verify submitted geometry and state.
    files = {
        'math/matrix34.hp': '''#pragma once
#include <cassert>
#include <cstdint>
using int32 = int32_t;
#define AssertMsg(condition, message) assert(condition)
#define ASSERTIONS(args)
struct Scalar { float value=0; float AsFloat() const { return value; } };
struct Matrix34 {
 Scalar values[4][3];
 Matrix34() { for(int i=0;i<3;i++) values[i][i].value=1; }
 Scalar* operator[](int i) { return values[i]; }
 const Scalar* operator[](int i) const { return values[i]; }
};
''',
        'memory/lmalloc.hp': '''#pragma once
#include <cstdlib>
struct Memory {
 int allocated=0;
 void* Allocate(size_t n) { ++allocated; return malloc(n); }
 void Free(const void* p) { --allocated; free(const_cast<void*>(p)); }
};
using LMalloc = Memory;
''',
        'hal/halbase.h': '''#include <memory/lmalloc.hp>
extern LMalloc testMemory;
#define HALLmalloc testMemory
''',
    }
    for name, source in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    harness = r'''
#include <vector>
#include "gfx/glpipeline/backend_factory.cc"
LMalloc testMemory;
struct Recorded { float x,z,opacity,ambient,fog; bool prelit,modulate,palette; unsigned dark,light; };
struct Backend : RendererBackend {
 std::vector<Recorded> draws;
 float opacity=1, ambient=0, fog=0;
 int ambientCalls=0;
 bool modulate=false,palette=false;unsigned dark=0,light=0xffffff;
 void SetProjection(float,float,float,float) override {}
 void SetModelView(const Matrix34&) override {}
 void ResetModelView() override {}
 void SetAmbient(float r,float,float) override { ambient=r; ++ambientCalls; }
 void SetDirLight(int,float,float,float,float,float,float) override {}
 void SetLightingEnabled(bool) override {}
 void SetFog(float r,float,float,float,float) override { fog=r; }
 void SetFogEnabled(bool) override {}
 void SetTexturePalette(bool e,unsigned d,unsigned l) override { palette=e;dark=d;light=l; }
 void SetOpacity(float x) override { opacity=x; }
 void SetTextureModulation(bool x) override { modulate=x; }
 void DrawTriangle(const RBVertex& a,const RBVertex&,const RBVertex&,
                   float,float,float,const PixelMap*,bool,bool p) override {
   draws.push_back({a.x,a.z,opacity,ambient,fog,p,modulate,palette,dark,light});
 }
 void EndFrame() override {}
 RBTextureHandle CreateTexture(int,int,RBTextureFormat,const void*) override { return nullptr; }
 void DestroyTexture(RBTextureHandle) override {}
} backend;
RendererBackend* ModernBackendInstance() { return &backend; }
int main() {
 RendererBackend& r=RendererBackendGet();
 RBVertex v={0,0,-2,1,1,1,0,0};
 auto submit=[&](bool prelit=false) { r.DrawTriangle(v,v,v,0,0,1,nullptr,false,prelit); };
 r.SetProjection(45,1,.1,100);
 r.SetAmbient(.2,0,0); r.SetFog(.3,0,0,1,10);
 r.SetTexturePalette(true,0x330011,0xffffaa);
 r.SetTextureModulation(true); r.SetOpacity(.25); submit(true); // near translucent, encountered first
 Matrix34 far; far[3][0].value=7; far[3][2].value=-8;
 r.SetTexturePalette(true,0x553300,0xffdd88);
 r.SetTextureModulation(false); r.SetModelView(far); r.SetAmbient(.8,0,0); r.SetOpacity(.5); submit();
 r.SetTexturePalette(false,0,0xffffff);
 r.SetTextureModulation(true); r.ResetModelView(); r.SetOpacity(1); submit(); // scenery encountered later
 assert(backend.draws.size()==1 && backend.draws[0].opacity==1 && backend.draws[0].modulate);
 r.FlushTranslucency();
 assert(backend.draws.size()==3);
 assert(backend.draws[1].x==7 && backend.draws[1].z==-10);
 assert(backend.draws[1].opacity==.5 && backend.draws[1].ambient==.8f && !backend.draws[1].modulate);
 assert(backend.draws[1].palette && backend.draws[1].dark==0x553300 && backend.draws[1].light==0xffdd88);
 assert(backend.draws[2].palette && backend.draws[2].dark==0x330011 && backend.draws[2].light==0xffffaa);
 assert(!backend.draws[0].palette);
 assert(backend.draws[2].z==-2 && backend.draws[2].ambient==.2f);
 assert(backend.draws[2].fog==.3f && backend.draws[2].prelit && backend.draws[2].modulate);
 assert(testMemory.allocated==0 && backend.opacity==1 && backend.modulate);
 // Equal-depth faces retain submission order; camera boundaries drain them.
 r.SetOpacity(.4); submit(); r.SetOpacity(.6); submit();
 r.SetProjection(60,1,.1,100);
 assert(backend.draws[3].opacity==.4f && backend.draws[4].opacity==.6f);
 assert(testMemory.allocated==0);
 r.SetOpacity(0); submit(); r.EndFrame(); assert(backend.draws.size()==5);
 r.SetTextureModulation(false); r.SetOpacity(1); submit(); r.EndFrame();
 assert(testMemory.allocated==0 && backend.draws.back().opacity==1 && !backend.draws.back().modulate);
 // Alternating palettes in depth order retain each color without replaying
 // lighting/fog uniforms and flushing every triangle's GPU batch.
 r.ResetModelView(); r.SetOpacity(.55);
 const int before=backend.ambientCalls;
 const size_t drawStart=backend.draws.size();
 for(int i=0;i<40;++i) {
   v.z=-50.f+i;
   r.SetTexturePalette(true,i%2?0x550000:0x330000,0xffffaa);
   submit();
 }
 r.EndFrame();
 assert(backend.draws.size()==drawStart+40);
 assert(backend.ambientCalls-before<=1);
 for(int i=0;i<40;++i) assert(backend.draws[drawStart+i].dark==(i%2?0x550000u:0x330000u));
 assert(testMemory.allocated==0);
}
'''
    source = tmp_path/'queue.cc'
    source.write_text(harness)
    binary = tmp_path/'queue'
    subprocess.run(['c++', '-std=c++17', '-I'+str(tmp_path),
                    '-I'+str(ROOT/'wfsource/source'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
