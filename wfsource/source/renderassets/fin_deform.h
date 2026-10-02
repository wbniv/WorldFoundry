#ifndef WF_FIN_DEFORM_H
#define WF_FIN_DEFORM_H
#include <algorithm>
#include <cmath>
namespace wf_render {
// Solid-colour fin meshes carry across-fin and root-to-tip coordinates in UV.
// Cache the rest pose and delayed oscillators; never deform an already bent mesh.
struct FinWaveWeight {
    float x,y,z,weight,sinDelay,cosDelay,sinCurl,cosCurl,rootX,rootZ;
    static FinWaveWeight make(float x,float y,float z,float across,float tip) {
        tip=std::max(0.f,std::min(1.f,tip));
        const float delay=tip*2.4f+across*9.42477796f;
        const float curl=tip*1.3f+across*1.1f;
        return {x,y,z,tip*tip,std::sin(delay),std::cos(delay),std::sin(curl),std::cos(curl),x,z};
    }
    float bentY(float sine,float cosine,float amplitude) const {
        return y+weight*amplitude*(sine*cosDelay-cosine*sinDelay);
    }
    float sweptX(float sweep,float spread=1.f) const { return rootX+(x-rootX)*spread-weight*sweep; }
    float bentZ(float sine,float cosine,float amplitude,float spread=1.f) const {
        return rootZ+(z-rootZ)*spread+weight*amplitude*.25f*(sine*sinCurl+cosine*cosCurl);
    }
};
}
#endif
