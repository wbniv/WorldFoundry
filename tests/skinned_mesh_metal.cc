// Apple sibling of skinned_mesh_gl: real offscreen rendering, not shader-only
// compilation. No Metal device is a failure of this verification gate.
#include <gfx/renderer_backend.hp>
#include <gfx/metal/metal_offscreen.h>
#include <renderassets/skin_pose.h>
#include <game/runtime_profile.hp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
extern RendererBackend* MetalBackendInstance();
static void need(bool ok,const char* message) {if(!ok){std::fprintf(stderr,"skinned_mesh_metal: %s\n",message);std::exit(1);}}
static std::vector<unsigned char> frame() {
    std::vector<unsigned char> p(64*64*4);need(wf_metal::ReadbackRGBA8(p.data(),64,64),"readback");return p;
}
static void save(const char* path,const std::vector<unsigned char>& pixels) {
    FILE* file=std::fopen(path,"wb");need(file,"frame artifact");std::fprintf(file,"P6\n64 64\n255\n");
    for(size_t i=0;i<pixels.size();i+=4)std::fwrite(&pixels[i],1,3,file);std::fclose(file);
}
static void center(int red) {auto p=frame();save("skin-metal-last.ppm",p);need(std::abs(int(p[4*(40*64+32)])-red)<=1,"wrong center pixel");}
int main() {
    need(wf_metal::Available(),"no Metal device; rendering not verified");
    auto* backend=MetalBackendInstance();need(backend->SkinnedMeshSupported(),"skin shaders/pipeline");
    backend->SetProjection(60,1,.1f,10);backend->SetFogEnabled(false);backend->SetLightingEnabled(true);
    backend->SetAmbient(.2f,.2f,.2f);backend->SetDirLight(0,0,0,1,.8f,.8f,.8f);
    float palette[4*12]={};for(int i=0;i<4;++i)palette[12*i]=palette[12*i+5]=palette[12*i+10]=1;
    RBSkinnedVertex v[3]{};
    v[0].vertex={-.7f,-.7f,-2,1,0,0,0,0};v[1].vertex={.7f,-.7f,-2,1,0,0,0,0};v[2].vertex={0,.7f,-2,1,0,0,0,0};
    for(auto& vertex:v){vertex.normal[2]=1;vertex.opacity=1;vertex.weights[0]=255;}
    auto h=backend->CreateSkinnedMesh(v,3);need(h,"skin buffer");
    auto finish=[&](){backend->EndFrame();wf_metal::EndFrame();};
    auto draw=[&](bool two,bool cull){need(wf_metal::BeginFrame(64,64),"begin frame");need(backend->DrawSkinnedMesh(h,0,3,palette,4,nullptr,false,two,cull),"draw rejected");finish();};
    draw(false,true);center(255);
    need(wf_metal::BeginFrame(64,64),"CPU begin");wf_profile::enableFresh();wf_profile::begin_frame();{wf_profile::SkinObjectScope tagged(true);backend->DrawTriangle(v[0].vertex,v[1].vertex,v[2].vertex,0,0,1,nullptr,true,false);}finish();auto cpu=frame();
    need(wf_profile::state().counters[wf_profile::SkinVertexBytes]==3*76,"CPU rig stream byte count");
    draw(false,true);need(cpu==frame(),"rigid lighting differs");
    backend->DestroySkinnedMesh(h);std::swap(v[1],v[2]);h=backend->CreateSkinnedMesh(v,3);
    draw(false,true);center(0);draw(true,true);center(51);draw(false,false);center(51);
    // A new encoder drawing ordinary CPU geometry must not inherit skin cull.
    need(wf_metal::BeginFrame(64,64),"ordinary begin");backend->DrawTriangle(v[0].vertex,v[1].vertex,v[2].vertex,0,0,-1,nullptr,true,false);finish();center(51);
    backend->DestroySkinnedMesh(h);std::swap(v[1],v[2]);
    palette[12+3]=.12f;palette[24+7]=.09f;palette[36+11]=.22f;
    const float C=std::cos(.3f),S=std::sin(.3f);
    palette[24]=C;palette[25]=-S;palette[28]=S;palette[29]=C;
    palette[36]=C;palette[38]=S;palette[44]=-S;palette[46]=C;
    const unsigned char weights[3][4]={{255,0,0,0},{0,128,127,0},{64,64,64,63}};
    RBVertex posed[3];
    for(int k=0;k<3;++k) {
        std::memcpy(v[k].weights,weights[k],4);for(int j=0;j<4;++j)v[k].joints[j]=j;
        wf_render::SkinBinding bind{};bind.point[0]=v[k].vertex.x;bind.point[1]=v[k].vertex.y;bind.point[2]=v[k].vertex.z;
        std::memcpy(bind.joints,v[k].joints,4);std::memcpy(bind.weights,v[k].weights,4);
        float p[3];wf_render::SkinPoint(bind,palette,p);posed[k]=v[k].vertex;posed[k].x=p[0];posed[k].y=p[1];posed[k].z=p[2];
    }
    float a[3]={posed[1].x-posed[0].x,posed[1].y-posed[0].y,posed[1].z-posed[0].z};
    float b[3]={posed[2].x-posed[0].x,posed[2].y-posed[0].y,posed[2].z-posed[0].z};
    float n[3]={a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
    float length=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);for(float& x:n)x/=length;
    need(wf_metal::BeginFrame(64,64),"mixed CPU begin");backend->DrawTriangle(posed[0],posed[1],posed[2],n[0],n[1],n[2],nullptr,true,false);finish();cpu=frame();save("skin-metal-cpu.ppm",cpu);
    h=backend->CreateSkinnedMesh(v,3);draw(false,false);auto gpu=frame();save("skin-metal-gpu.ppm",gpu);
    int differences=0;for(size_t i=0;i<gpu.size();++i)if(std::abs(int(gpu[i])-int(cpu[i]))>1)++differences;
    need(differences==0,"four-weight geometry/flat shading differs");
    backend->SetFog(.1f,.2f,.3f,1.f,3.f);backend->SetFogEnabled(true);
    need(wf_metal::BeginFrame(64,64),"fog CPU begin");backend->DrawTriangle(posed[0],posed[1],posed[2],n[0],n[1],n[2],nullptr,true,false);finish();cpu=frame();
    draw(false,false);gpu=frame();
    for(size_t i=0;i<gpu.size();++i)need(std::abs(int(gpu[i])-int(cpu[i]))<=1,"posed fog differs");
    backend->SetFogEnabled(false);
    wf_profile::enableFresh();wf_profile::begin_frame();draw(false,true);
    need(wf_profile::state().counters[wf_profile::SkinVertexBytes]==0,"steady-state vertex upload");
    need(wf_profile::state().counters[wf_profile::SkinPaletteBytes]==4*48,"palette byte count");
    backend->DestroySkinnedMesh(h);size_t bytes=1,staging=1;backend->SkinnedMeshBytes(bytes,staging);need(bytes==0 && staging==0,"resident buffer leak");
    need(wf_metal::BeginFrame(80,80),"resize attachments");finish();
    h=backend->CreateSkinnedMesh(v,3);need(h,"recreated buffer");draw(false,true);backend->DestroySkinnedMesh(h);
    std::puts("skinned_mesh_metal: rigid/four-weight draws, flat normals, culling, state, upload, resize and recreation pass");
}
