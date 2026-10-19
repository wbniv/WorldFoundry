#ifndef WF_JELLY_DEFORM_H
#define WF_JELLY_DEFORM_H
#include <algorithm>
#include <cmath>
namespace wf_render {
// Cached common rest frame. Apex, margin and trailing tissue have distinct weights.
struct JellyWeight {
    float x,y,z,margin,length,delay;
    static JellyWeight make(float x,float y,float z) {
        const float length=std::max(0.f,-z);
        return {x,y,z,std::max(0.f,std::min(1.f,(.30f-z)/.30f)),length,
            length*2.8f+std::atan2(y,x)*.25f};
    }
    void deform(float contraction,float phase,float pitchLag,float rollLag,
                float& px,float& py,float& pz) const {
        const float radial=1.f-.18f*contraction*margin;
        const float trail=length*length;
        const float wave=std::sin(phase*6.283185307f-delay)*.022f*trail;
        px=x*radial-pitchLag*6.283185307f*trail+wave;
        py=y*radial+rollLag*6.283185307f*trail+wave*.45f;
        pz=z+(z>0.f ? .28f*contraction*z*margin : 0.f);
    }
};
}
#endif
