#ifndef WF_FISH_DEFORM_H
#define WF_FISH_DEFORM_H
#include <algorithm>
#include <cmath>
namespace wf_render {
// Precompute the travelling-wave weights once per vertex; only two trig calls
// per fish update. Nose faces +X; the front 35% remains stable.
struct FishWaveWeight {
    float y, sinWeight, cosWeight;
    static FishWaveWeight make(float x,float y,float minX,float maxX) {
        const float length=maxX-minX;
        const float t=length>0 ? std::max(0.f,std::min(1.f,(maxX-x)/length)) : 0;
        const float w=std::max(0.f,(t-.35f)/.65f);
        return {y,w*w*std::sin(t*3.14159265f),w*w*std::cos(t*3.14159265f)};
    }
    float deform(float sine,float cosine,float amplitude) const {
        return y+amplitude*(sine*cosWeight-cosine*sinWeight);
    }
};
}
#endif
