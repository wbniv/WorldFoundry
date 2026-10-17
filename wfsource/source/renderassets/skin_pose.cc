#include <renderassets/skin_pose.h>
#include <algorithm>
#include <cmath>
#include <cstring>

namespace wf_render {
namespace {
float Length(const float* v) { return std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]); }
float DoubleArea(const float p[3][3]) {
    float a[3],b[3],n[3];for(int k=0;k<3;++k){a[k]=p[1][k]-p[0][k];b[k]=p[2][k]-p[0][k];}
    n[0]=a[1]*b[2]-a[2]*b[1];n[1]=a[2]*b[0]-a[0]*b[2];n[2]=a[0]*b[1]-a[1]*b[0];return Length(n);
}
// Rigid faces stay nondegenerate. For mixed faces accept only weights of one
// axial transform (identity = weight zero), and certify its WHOLE clamped angle
// interval using a conservative Lipschitz lower bound on |edge1 x edge2|.
// Thus skipping CPU normals cannot change the evaluator's degenerate-face
// "keep previous normal" rule. Unsupported topology falls back, not guesses.
bool SafeSkinGeometry(const DfrmData& data,const float* rest,int count,const int* faces,int faceCount) {
    const auto& curve=data.curves[0];std::vector<float> joints(3*(data.samples.size()+1));
    for(int k=0;k<3;++k)joints[k]=curve.root[k];
    for(size_t i=0;i<data.samples.size();++i)for(int k=0;k<3;++k)joints[3*(i+1)+k]=joints[3*i+k]+curve.d[k]*data.samples[i].length;
    size_t work=0;
    for(int f=0;f<faceCount;++f) {
        const DfrmInfluence* in[3];float p[3][3];
        for(int i=0;i<3;++i) {
            int index=faces[3*f+i];if(index<0 || index>=count)return false;
            in[i]=&data.influences[index];std::memcpy(p[i],rest+3*index,12);
            if(in[i]->kind==DfrmOnSample) {
                if(in[i]->index>=data.samples.size())return false;
                for(int k=0;k<3;++k)p[i][k]=joints[3*in[i]->index+k]+in[i]->a*curve.d[k]+in[i]->b*curve.v[k]+in[i]->c*curve.s[k];
            }
        }
        const bool same=in[0]->kind==in[1]->kind && in[1]->kind==in[2]->kind &&
            in[0]->index==in[1]->index && in[1]->index==in[2]->index &&
            (in[0]->kind!=DfrmOnTransform || (in[0]->a==in[1]->a && in[1]->a==in[2]->a));
        if(!(DoubleArea(p)>1e-6f))return false;
        if(same)continue;
        int t=-1;float weights[3]={};
        for(int i=0;i<3;++i) {
            if(in[i]->kind==DfrmNone)continue;
            if(in[i]->kind!=DfrmOnTransform || in[i]->index>=data.transforms.size())return false;
            if(t>=0 && t!=in[i]->index)return false;t=in[i]->index;weights[i]=in[i]->a;
        }
        if(t<0)continue;
        const auto& tr=data.transforms[t];float relative[3][3],radius[3],speed[3];
        for(int i=0;i<3;++i){for(int k=0;k<3;++k)relative[i][k]=p[i][k]-tr.pivot[k];radius[i]=Length(relative[i])*1.01f;speed[i]=std::fabs(weights[i])*radius[i]*1.01f;}
        const float bound=(speed[1]+speed[0])*(radius[2]+radius[0])+(radius[1]+radius[0])*(speed[2]+speed[0]);
        const int steps=std::max(1,int(std::ceil((tr.hi-tr.lo)/.1f)));work+=steps;if(work>1000000)return false;
        const float delta=(tr.hi-tr.lo)*(.017453292519943295f/steps);
        const float largest=std::max(radius[0],std::max(radius[1],radius[2]));
        const float margin=1e-6f*std::max(1.f,largest*largest);
        for(int step=0;step<steps;++step) {
            const float angle=tr.lo*.017453292519943295f+(step+.5f)*delta;float posed[3][3];
            for(int i=0;i<3;++i) {
                if(weights[i]==0){std::memcpy(posed[i],p[i],12);continue;}
                const float C=std::cos(angle*weights[i]),S=std::sin(angle*weights[i]);const float* r=relative[i];const float* a=tr.axis;
                const float dot=a[0]*r[0]+a[1]*r[1]+a[2]*r[2];
                const float cross[3]={a[1]*r[2]-a[2]*r[1],a[2]*r[0]-a[0]*r[2],a[0]*r[1]-a[1]*r[0]};
                for(int k=0;k<3;++k)posed[i][k]=tr.pivot[k]+r[k]*C+cross[k]*S+a[k]*dot*(1-C);
            }
            if(!(DoubleArea(posed)-bound*std::fabs(delta)*.5f>margin))return false;
        }
    }
    return true;
}
}

bool DfrmSkin::Bind(const DfrmData& data, const float* rest, int count, const int* faces, int faceCount)
{
    if (!rest || !faces || faceCount<=0 || count<=0 || data.curves.size()!=1 || data.influences.size()!=size_t(count) || 1+data.samples.size()>SkinMaxPalette) return false;
    _bindings.clear(); _weighted.clear(); _palette.clear();
    for (const auto& in : data.influences) {
        if (in.kind != DfrmOnTransform) continue;
        const auto found = std::find_if(_weighted.begin(), _weighted.end(), [&](const Weighted& w) {
            return w.transform == in.index && w.weight == in.a;
        });
        if (found == _weighted.end()) _weighted.push_back({in.index, in.a});
        if(1+data.samples.size()+_weighted.size()>SkinMaxPalette)return false;
    }
    const int size = 1 + int(data.samples.size() + _weighted.size());
    if (size > SkinMaxPalette) return false;
    _palette.assign(size_t(size) * 12, 0.f);
    _palette[0] = _palette[5] = _palette[10] = 1.f;
    _bindings.resize(count);
    for (int i = 0; i < count; ++i) {
        const auto& in = data.influences[i];
        auto& binding = _bindings[i];
        std::memcpy(binding.point, rest + 3*i, sizeof(binding.point));
        if (in.kind == DfrmOnSample) {
            binding.joints[0] = 1 + in.index;
            binding.point[0] = in.a; binding.point[1] = in.b; binding.point[2] = in.c;
        } else if (in.kind == DfrmOnTransform) {
            const auto w = std::find_if(_weighted.begin(), _weighted.end(), [&](const Weighted& w) {
                return w.transform == in.index && w.weight == in.a;
            });
            binding.joints[0] = 1 + data.samples.size() + (w - _weighted.begin());
        }
    }
    return SafeSkinGeometry(data,rest,count,faces,faceCount);
}

bool DfrmSkin::Pose(const DfrmData& data, const DfrmEvaluator& eval)
{
    if (_palette.empty()) return false;
    const auto& joints = eval.Joints(); const auto& frames = eval.Frames();
    for (size_t i = 0; i < data.samples.size(); ++i) {
        float* matrix = &_palette[12*(i + 1)];
        for (int k = 0; k < 3; ++k) {
            matrix[4*k] = frames[9*i + k]; matrix[4*k+1] = frames[9*i + 3+k];
            matrix[4*k+2] = frames[9*i + 6+k]; matrix[4*k+3] = joints[3*i+k];
        }
    }
    for (size_t i = 0; i < _weighted.size(); ++i) {
        const auto& w = _weighted[i]; const auto& t = data.transforms[w.transform];
        const float angle = eval.TransformAngles()[w.transform] * w.weight * (3.14159265358979323846f/180.f);
        const float C = std::cos(angle), S = std::sin(angle);
        const float x = t.axis[0], y = t.axis[1], z = t.axis[2];
        const float r[9] = {C+x*x*(1-C), x*y*(1-C)-z*S, x*z*(1-C)+y*S,
                            y*x*(1-C)+z*S, C+y*y*(1-C), y*z*(1-C)-x*S,
                            z*x*(1-C)-y*S, z*y*(1-C)+x*S, C+z*z*(1-C)};
        float* matrix = &_palette[12*(1 + data.samples.size() + i)];
        for (int k = 0; k < 3; ++k) {
            for (int j = 0; j < 3; ++j) matrix[4*k+j] = r[3*k+j];
            matrix[4*k+3] = t.pivot[k] - (r[3*k]*t.pivot[0]+r[3*k+1]*t.pivot[1]+r[3*k+2]*t.pivot[2]);
        }
    }
    for (float value : _palette) if (!std::isfinite(value)) return false;
    return true;
}

void SkinPoint(const SkinBinding& binding, const float* palette, float* out)
{
    out[0] = out[1] = out[2] = 0.f;
    for (int j = 0; j < 4; ++j) {
        if (!binding.weights[j]) continue;
        const float* m = palette + 12*binding.joints[j];
        const float w = binding.weights[j] / 255.f;
        for (int k = 0; k < 3; ++k)
            out[k] += w*(m[4*k]*binding.point[0]+m[4*k+1]*binding.point[1]+m[4*k+2]*binding.point[2]+m[4*k+3]);
    }
}
}
