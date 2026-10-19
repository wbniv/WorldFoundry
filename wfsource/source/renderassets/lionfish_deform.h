// Optional single-mesh lionfish rig. UVs remain exclusively texture coordinates.
#ifndef WF_LIONFISH_DEFORM_H
#define WF_LIONFISH_DEFORM_H
#include <cmath>
#include <algorithm>
namespace wf_render {
enum LionRegion { Trunk, Head, Jaw, PectoralLeft, PectoralRight, Tail, Dorsal, Anal, Pelvic, Spines, LionRegionCount };
struct LionRig { unsigned region; float weight, px, py, pz; };
struct LionRest { float x,y,z; };
inline float lionClamp(float v,float lo,float hi) { return std::max(lo,std::min(hi,v)); }
inline void lionPose(const LionRest& p,const LionRig& r,float phase,float drive,float turn,float gape,float& x,float& y,float& z) {
    x=p.x;y=p.y;z=p.z;
    const float w=r.weight, a=phase*6.283185307f;
    if(r.region==PectoralLeft || r.region==PectoralRight) {
        float side=r.region==PectoralLeft?-1.f:1.f;
        // Root fixed; curvature travels along the membrane, with independent sides.
        y=r.py+(y-r.py)*(1-.4f*drive*w);
        x-=.09f*drive*w;
        y+=side*(.034f*std::sin(a-2.4f*std::sqrt(w)+side*.65f)+.045f*turn)*w;
        z+=.023f*std::sin(a-3.f*std::sqrt(w)+side*.65f)*w;
    } else if(r.region==Tail) {
        y+=(.023f+.05f*drive)*std::sin(a*2-2.f*std::sqrt(w))*w+.035f*turn*w;
    } else if(r.region==Dorsal || r.region==Anal || r.region==Pelvic) {
        y+=.012f*std::sin(a-2.f*std::sqrt(w))*w;
    } else if(r.region==Spines) {
        x-=.065f*drive*w; z-=.02f*drive*w;
    } else if(r.region==Jaw) {
        const float angle=.48f*gape*w, dx=x-r.px,dz=z-r.pz;
        x=r.px+dx*std::cos(angle)+dz*std::sin(angle)+.04f*gape*w;
        z=r.pz-dx*std::sin(angle)+dz*std::cos(angle);
    } else if(r.region==Head) {
        const float angle=.06f*gape*w, dx=x-r.px,dz=z-r.pz;
        x=r.px+dx*std::cos(angle)-dz*std::sin(angle)+.02f*gape*w;
        z=r.pz+dx*std::sin(angle)+dz*std::cos(angle);
    } else if(r.region==Trunk && x>.1f) {
        y*=1+.06f*gape; z-=.018f*gape;
    }
}
}
#endif
