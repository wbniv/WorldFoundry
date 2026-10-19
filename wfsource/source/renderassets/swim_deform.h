#ifndef WF_SWIM_DEFORM_H
#define WF_SWIM_DEFORM_H
#include <renderassets/fish_deform.h>
namespace wf_render {
// All pieces of a rig use an explicit common model-space head/tail span.
// UV V is local root-to-tip distance: the added membrane wave vanishes at roots.
// Cache the rest pose, so a wave never accumulates into the previous frame.
struct SwimWaveWeight {
    FishWaveWeight body;
    float envelope, finWeight, sinDelay, cosDelay;
    static SwimWaveWeight make(float x,float y,float minX,float maxX,float across,float tip) {
        const float t=std::max(0.f,std::min(1.f,(maxX-x)/(maxX-minX)));
        const float w=std::max(0.f,(t-.35f)/.65f);
        tip=std::max(0.f,std::min(1.f,tip));
        const float delay=tip*2.4f+across*1.1f;
        return {FishWaveWeight::make(x,y,minX,maxX),w*w,tip*tip,std::sin(delay),std::cos(delay)};
    }
    float deform(float sine,float cosine,float amplitude,float bend,
                 float finSine,float finCosine,float finAmplitude) const {
        return body.deform(sine,cosine,amplitude)+bend*envelope+
            finAmplitude*finWeight*(finSine*cosDelay-finCosine*sinDelay);
    }
};
}
#endif
