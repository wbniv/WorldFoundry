#ifndef WF_SKIN_POSE_H
#define WF_SKIN_POSE_H

#include <renderassets/dfrm_deform.h>
#include <vector>

namespace wf_render {
constexpr int SkinMaxPalette = 48;
struct SkinBinding {
    float point[3];
    unsigned char joints[4] = {};
    unsigned char weights[4] = {255, 0, 0, 0};
};

// DFRM sample points live in sample-local space; transform/identity points
// live in model space. A palette entry maps either directly to posed model
// space. No float-weight LBS approximation of an angle-weighted rotation.
class DfrmSkin {
public:
    bool Bind(const DfrmData&, const float* rest, int count, const int* faces, int faceCount);
    bool Pose(const DfrmData&, const DfrmEvaluator&);
    size_t CpuBytes() const { return _bindings.capacity()*sizeof(SkinBinding)+_palette.capacity()*sizeof(float)+_weighted.capacity()*sizeof(Weighted); }
    const std::vector<SkinBinding>& Bindings() const { return _bindings; }
    const std::vector<float>& Palette() const { return _palette; }
private:
    struct Weighted { int transform; float weight; };
    std::vector<Weighted> _weighted;
    std::vector<SkinBinding> _bindings;
    std::vector<float> _palette;  // three float4 ROWS per affine transform
};

void SkinPoint(const SkinBinding&, const float* palette, float* out);
}
#endif
