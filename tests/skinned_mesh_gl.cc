// Real GL draws: skinning, derivative flat normals, hardware/two-sided cull,
// state restoration, upload counters and stale-handle recreation.
#include <gfx/renderer_backend.hp>
#include <game/runtime_profile.hp>
#include <renderassets/skin_pose.h>
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

extern RendererBackend* ModernBackendInstance();
extern void ModernBackendSimulateSurfaceLoss();
static void need(bool ok,const char* message) {if(!ok){std::fprintf(stderr,"skinned_mesh_gl: %s\n",message);std::exit(1);}}
static std::vector<unsigned char> frame() {
    std::vector<unsigned char> p(64*64*4);glReadPixels(0,0,64,64,GL_RGBA,GL_UNSIGNED_BYTE,p.data());return p;
}
static void center(int r) {auto p=frame();need(std::abs(int(p[4*(24*64+32)])-r)<=1,"wrong center pixel");}

int main() {
    Display* display=XOpenDisplay(nullptr);need(display,"X display");
    int attributes[]={GLX_RGBA,GLX_RED_SIZE,8,GLX_GREEN_SIZE,8,GLX_BLUE_SIZE,8,GLX_DOUBLEBUFFER,None};
    auto* visual=glXChooseVisual(display,DefaultScreen(display),attributes);need(visual,"GL visual");
    XSetWindowAttributes attrs{};attrs.colormap=XCreateColormap(display,RootWindow(display,visual->screen),visual->visual,AllocNone);
    Window window=XCreateWindow(display,RootWindow(display,visual->screen),0,0,64,64,0,visual->depth,InputOutput,visual->visual,CWColormap,&attrs);
    XMapWindow(display,window);XSync(display,False);
    GLXContext context=glXCreateContext(display,visual,nullptr,GL_TRUE);need(context && glXMakeCurrent(display,window,context),"GL context");
    glViewport(0,0,64,64);glDisable(GL_DEPTH_TEST);glDisable(GL_DITHER);glDisable(GL_CULL_FACE);glClearColor(0,0,0,1);
    auto* backend=ModernBackendInstance();need(backend->SkinnedMeshSupported(),"skin shaders/capacity");
    backend->SetProjection(60,1,.1f,10);backend->SetFogEnabled(false);backend->SetLightingEnabled(true);backend->SetAmbient(.2f,.2f,.2f);
    backend->SetDirLight(0,0,0,1,.8f,.8f,.8f);
    float palette[4*12]={};for(int i=0;i<4;++i)palette[12*i]=palette[12*i+5]=palette[12*i+10]=1;
    RBSkinnedVertex v[3]{};
    v[0].vertex={-.7f,-.7f,-2.f,1,0,0,0,0};v[1].vertex={.7f,-.7f,-2.f,1,0,0,0,0};v[2].vertex={0,.7f,-2.f,1,0,0,0,0};
    for(auto& vertex:v){vertex.normal[2]=1;vertex.opacity=1;vertex.weights[0]=255;}
    auto h=backend->CreateSkinnedMesh(v,3);need(h,"skin buffer");
    auto draw=[&](bool two,bool cull){glClear(GL_COLOR_BUFFER_BIT);need(backend->DrawSkinnedMesh(h,0,3,palette,4,nullptr,false,two,cull),"draw rejected");backend->EndFrame();};
    draw(false,true);center(255);
    // CPU reference with the same posed positions and flat normal.
    glClear(GL_COLOR_BUFFER_BIT);backend->DrawTriangle(v[0].vertex,v[1].vertex,v[2].vertex,0,0,1,nullptr,true,false);backend->EndFrame();auto cpu=frame();
    draw(false,true);need(cpu==frame(),"rigid lighting differs");
    backend->DestroySkinnedMesh(h);std::swap(v[1],v[2]);h=backend->CreateSkinnedMesh(v,3);
    draw(false,true);center(0);draw(true,true);center(51);draw(false,false);center(51);
    backend->DestroySkinnedMesh(h);std::swap(v[1],v[2]);
    // Four distinct influences on a triangle spanning bindings. Its deformed
    // geometric normal must light it flat, exactly like the streamed CPU face.
    palette[12+3]=.12f;palette[24+7]=.09f;palette[36+11]=.22f;
    const float C=std::cos(.3f),S=std::sin(.3f);
    palette[24]=C;palette[25]=-S;palette[28]=S;palette[29]=C;
    palette[36]=C;palette[38]=S;palette[44]=-S;palette[46]=C;
    for(int k=0;k<3;++k)for(int j=0;j<4;++j)v[k].joints[j]=j;
    const unsigned char weights[3][4]={{255,0,0,0},{0,128,127,0},{64,64,64,63}};
    RBVertex posed[3];
    for(int k=0;k<3;++k) {
        std::memcpy(v[k].weights,weights[k],4);wf_render::SkinBinding bind{};
        bind.point[0]=v[k].vertex.x;bind.point[1]=v[k].vertex.y;bind.point[2]=v[k].vertex.z;
        std::memcpy(bind.joints,v[k].joints,4);std::memcpy(bind.weights,v[k].weights,4);
        float p[3];wf_render::SkinPoint(bind,palette,p);posed[k]=v[k].vertex;posed[k].x=p[0];posed[k].y=p[1];posed[k].z=p[2];
    }
    float a[3]={posed[1].x-posed[0].x,posed[1].y-posed[0].y,posed[1].z-posed[0].z};
    float b[3]={posed[2].x-posed[0].x,posed[2].y-posed[0].y,posed[2].z-posed[0].z};
    float n[3]={a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
    float length=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);for(float& x:n)x/=length;
    glClear(GL_COLOR_BUFFER_BIT);backend->DrawTriangle(posed[0],posed[1],posed[2],n[0],n[1],n[2],nullptr,true,false);backend->EndFrame();cpu=frame();
    h=backend->CreateSkinnedMesh(v,3);draw(false,false);auto gpu=frame();
    int differences=0;for(size_t i=0;i<gpu.size();++i)if(std::abs(int(gpu[i])-int(cpu[i]))>1)++differences;
    need(differences==0,"four-influence geometry/flat shading differs");
    backend->SetFog(.1f,.2f,.3f,1.f,3.f);backend->SetFogEnabled(true);
    glClear(GL_COLOR_BUFFER_BIT);backend->DrawTriangle(posed[0],posed[1],posed[2],n[0],n[1],n[2],nullptr,true,false);backend->EndFrame();cpu=frame();
    draw(false,false);gpu=frame();
    for(size_t i=0;i<gpu.size();++i)need(std::abs(int(gpu[i])-int(cpu[i]))<=1,"posed fog differs");
    backend->SetFogEnabled(false);
    // Restore all cull state even when the host had nondefault values.
    glFrontFace(GL_CW);glCullFace(GL_FRONT);glEnable(GL_CULL_FACE);draw(false,true);
    GLint front=0,face=0;glGetIntegerv(GL_FRONT_FACE,&front);glGetIntegerv(GL_CULL_FACE_MODE,&face);
    need(glIsEnabled(GL_CULL_FACE) && front==GL_CW && face==GL_FRONT,"cull state leaked");
    glDisable(GL_CULL_FACE);glFrontFace(GL_CCW);glCullFace(GL_BACK);
    wf_profile::enableFresh();wf_profile::begin_frame();draw(false,true);
    need(wf_profile::state().counters[wf_profile::SkinVertexBytes]==0,"steady-state vertex upload");
    need(wf_profile::state().counters[wf_profile::SkinPaletteBytes]==4*48,"palette byte count");
    ModernBackendSimulateSurfaceLoss();
    glXMakeCurrent(display,None,nullptr);glXDestroyContext(display,context);
    context=glXCreateContext(display,visual,nullptr,GL_TRUE);need(context && glXMakeCurrent(display,window,context),"recreated GL context");
    glViewport(0,0,64,64);glDisable(GL_DEPTH_TEST);glDisable(GL_DITHER);glDisable(GL_CULL_FACE);glClearColor(0,0,0,1);
    need(!backend->SkinnedMeshLive(h),"stale handle remained live");backend->DestroySkinnedMesh(h);
    h=backend->CreateSkinnedMesh(v,3);need(h,"resource rebuild");draw(false,true);backend->DestroySkinnedMesh(h);
    size_t bytes=1,staging=1;backend->SkinnedMeshBytes(bytes,staging);need(bytes==0 && staging==0,"GPU resource leak");
    need(glGetError()==GL_NO_ERROR,"GL error");
    glXMakeCurrent(display,None,nullptr);glXDestroyContext(display,context);XDestroyWindow(display,window);XCloseDisplay(display);
    std::puts("skinned_mesh_gl: rigid and 4-weight draws, flat normals, culling, state, upload and recreation pass");
}
