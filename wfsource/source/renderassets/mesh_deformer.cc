//============================================================================
// mesh_deformer.cc: the deformer kinds behind RenderActor3D's one slot.
//
// Fish, fin, swim, jelly and lion are moved verbatim from RenderActor3D
// (rendacto.cc before the E0 move): the same clamps, the same arithmetic order,
// the same weights. deformer_golden compares them bit for bit with fixtures
// recorded from the old code. The generic checks (finite channels, the slot's
// kind, taking the writable vertex list) live in RenderActor3D::Deform.
//============================================================================
#include <renderassets/mesh_deformer.h>
#include <renderassets/fish_deform.h>
#include <renderassets/fin_deform.h>
#include <renderassets/swim_deform.h>
#include <renderassets/jelly_deform.h>
#include <renderassets/lionfish_deform.h>
#include <renderassets/dfrm_deform.h>

#include <algorithm>
#include <cmath>
#include <map>
#include <vector>

namespace {

class FishDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Fish; }
    int MaxChannels() const override { return 2; }
    DeformStatus Check(const float*, int n) const override { return n == 2 ? DeformStatus::Ok : DeformStatus::BadInput; }
    DeformStatus Bind(const DeformTarget& t, const float*, int) override
    {
        Vertex3D* vertices = t.vertices; const int count = t.count;
        float minX=vertices[0].position.X().AsFloat(),maxX=minX;
        for(int i=1;i<count;i++){ float x=vertices[i].position.X().AsFloat(); minX=std::min(minX,x); maxX=std::max(maxX,x); }
        _length=maxX-minX; _weights.reserve(count);
        for(int i=0;i<count;i++) _weights.push_back(wf_render::FishWaveWeight::make(vertices[i].position.X().AsFloat(),vertices[i].position.Y().AsFloat(),minX,maxX));
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int) override
    {
        float phase=c[0], amplitude=c[1];
        Vertex3D* vertices = t.vertices; const int count = t.count;
        const float angle=phase*6.283185307f,sine=std::sin(angle),cosine=std::cos(angle);
        amplitude=std::max(0.f,std::min(.12f,amplitude))*_length;
        for(int i=0;i<count;i++) vertices[i].position.SetY(Scalar(_weights[i].deform(sine,cosine,amplitude)));
        return DeformStatus::Ok;
    }
private:
    std::vector<wf_render::FishWaveWeight> _weights;
    float _length = 0;
};

class FinDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Fin; }
    int MaxChannels() const override { return 4; }
    DeformStatus Check(const float*, int n) const override { return n == 4 ? DeformStatus::Ok : DeformStatus::BadInput; }
    DeformStatus Bind(const DeformTarget& t, const float*, int) override
    {
        Vertex3D* vertices = t.vertices; const int count = t.count;
        std::map<int,std::pair<float,float>> roots;
        // Root rows are authored explicitly, including every across-fin coordinate.
        // This one-time scan is shared by all rendering backends.
        for(int i=0;i<count;i++) {
            if(vertices[i].v.AsFloat()<=.00001f)
                roots[int(std::lround(vertices[i].u.AsFloat()*65536.f))]=
                    {vertices[i].position.X().AsFloat(),vertices[i].position.Z().AsFloat()};
        }
        _weights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vertex3D& v=vertices[i];
            _weights.push_back(wf_render::FinWaveWeight::make(v.position.X().AsFloat(),
                v.position.Y().AsFloat(),v.position.Z().AsFloat(),v.u.AsFloat(),v.v.AsFloat()));
            const auto root=roots.find(int(std::lround(v.u.AsFloat()*65536.f)));
            if(root!=roots.end()) {
                _weights.back().rootX=root->second.first;_weights.back().rootZ=root->second.second;
            }
        }
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int) override
    {
        float phase=c[0], amplitude=c[1], sweep=c[2], spread=c[3];
        Vertex3D* vertices = t.vertices; const int count = t.count;
        const float angle=std::fmod(phase,1.f)*6.283185307f;
        const float sine=std::sin(angle),cosine=std::cos(angle);
        amplitude=std::max(0.f,std::min(.25f,amplitude));
        sweep=std::max(-.15f,std::min(.15f,sweep));
        spread=std::max(.55f,std::min(1.1f,spread));
        for(int i=0;i<count;i++) {
            vertices[i].position.SetX(Scalar(_weights[i].sweptX(sweep,spread)));
            vertices[i].position.SetY(Scalar(_weights[i].bentY(sine,cosine,amplitude)));
            vertices[i].position.SetZ(Scalar(_weights[i].bentZ(sine,cosine,amplitude,spread)));
        }
        return DeformStatus::Ok;
    }
private:
    std::vector<wf_render::FinWaveWeight> _weights;
};

class SwimDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Swim; }
    int MaxChannels() const override { return 7; }
    DeformStatus Check(const float* c, int n) const override
    {
        if (n != 7) return DeformStatus::BadInput;
        const float minX=c[5], maxX=c[6];
        return maxX-minX<.001f ? DeformStatus::BadInput : DeformStatus::Ok;
    }
    DeformStatus Bind(const DeformTarget& t, const float* c, int) override
    {
        const float minX=c[5], maxX=c[6];
        Vertex3D* vertices = t.vertices; const int count = t.count;
        _minX=minX; _maxX=maxX; _weights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vertex3D& v=vertices[i];
            _weights.push_back(wf_render::SwimWaveWeight::make(v.position.X().AsFloat(),
                v.position.Y().AsFloat(),minX,maxX,v.u.AsFloat(),v.v.AsFloat()));
        }
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int) override
    {
        float phase=c[0], amplitude=c[1], bend=c[2], finPhase=c[3], finAmplitude=c[4];
        const float minX=c[5], maxX=c[6];
        Vertex3D* vertices = t.vertices; const int count = t.count;
        // Reference span is model metadata, not an animation channel.
        if (minX!=_minX || maxX!=_maxX) return DeformStatus::BadInput;
        const float angle=std::fmod(phase,1.f)*6.283185307f;
        const float finAngle=std::fmod(finPhase,1.f)*6.283185307f;
        const float sine=std::sin(angle),cosine=std::cos(angle);
        const float finSine=std::sin(finAngle),finCosine=std::cos(finAngle);
        amplitude=std::max(0.f,std::min(.12f*(maxX-minX),amplitude));
        bend=std::max(-.4f,std::min(.4f,bend));
        finAmplitude=std::max(0.f,std::min(.15f,finAmplitude));
        for(int i=0;i<count;i++) vertices[i].position.SetY(Scalar(_weights[i].deform(
            sine,cosine,amplitude,bend,finSine,finCosine,finAmplitude)));
        return DeformStatus::Ok;
    }
private:
    std::vector<wf_render::SwimWaveWeight> _weights;
    float _minX = 0, _maxX = 0;
};

class JellyDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Jelly; }
    int MaxChannels() const override { return 4; }
    DeformStatus Check(const float*, int n) const override { return n == 4 ? DeformStatus::Ok : DeformStatus::BadInput; }
    DeformStatus Bind(const DeformTarget& t, const float*, int) override
    {
        Vertex3D* vertices = t.vertices; const int count = t.count;
        _weights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vector3& p=vertices[i].position;
            _weights.push_back(wf_render::JellyWeight::make(p.X().AsFloat(),p.Y().AsFloat(),p.Z().AsFloat()));
        }
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int) override
    {
        float contraction=c[0], phase=c[1], pitchLag=c[2], rollLag=c[3];
        Vertex3D* vertices = t.vertices; const int count = t.count;
        contraction=std::max(0.f,std::min(1.f,contraction));
        phase=std::fmod(phase,1.f);
        pitchLag=std::max(-.025f,std::min(.025f,pitchLag));
        rollLag=std::max(-.025f,std::min(.025f,rollLag));
        for(int i=0;i<count;i++) {
            float x,y,z; _weights[i].deform(contraction,phase,pitchLag,rollLag,x,y,z);
            vertices[i].position=Vector3(Scalar(x),Scalar(y),Scalar(z));
        }
        return DeformStatus::Ok;
    }
private:
    std::vector<wf_render::JellyWeight> _weights;
};

// Channels: phase, drive, turn, gape, palette dark, palette light. The two
// palette colours are 24-bit integers carried exactly in float.
class LionDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Lion; }
    int MaxChannels() const override { return 6; }
    DeformStatus Check(const float*, int n) const override { return n == 6 ? DeformStatus::Ok : DeformStatus::BadInput; }
    DeformStatus Bind(const DeformTarget& t, const float*, int) override
    {
        if (t.object.GetLionRig().size()!=unsigned(t.count)) return DeformStatus::NoMetadata;
        Vertex3D* vertices = t.vertices; const int count = t.count;
        for(int i=0;i<count;i++) {
            const auto& p=vertices[i].position;
            _rest.push_back({p.X().AsFloat(),p.Y().AsFloat(),p.Z().AsFloat()});
        }
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int) override
    {
        float phase=c[0], drive=c[1], turn=c[2], gape=c[3];
        const unsigned dark=unsigned(c[4]), light=unsigned(c[5]);
        const auto& rig=t.object.GetLionRig();
        Vertex3D* vertices = t.vertices; const int count = t.count;
        if (rig.size()!=unsigned(count)) return DeformStatus::NoMetadata;
        phase=std::fmod(phase,1.f);drive=wf_render::lionClamp(drive,0,1);
        turn=wf_render::lionClamp(turn,-1,1);gape=wf_render::lionClamp(gape,0,1);
        for(int i=0;i<count;i++) {
            float x,y,z;wf_render::lionPose(_rest[i],rig[i],phase,drive,turn,gape,x,y,z);
            vertices[i].position=Vector3(Scalar(x),Scalar(y),Scalar(z));
        }
        t.object.SetLionPalette(dark,light);
        return DeformStatus::Ok;
    }
private:
    std::vector<wf_render::LionRest> _rest;
};

// DFRM v1: rooted curve with clips, knots and wrap, plus weighted transforms
// (renderassets/dfrm_deform.h). Channels are the control block's input cells
// 0..32; the caller publishes Outputs() and the status to cells 33..39.
// Positions and face normals are written only for a complete pose (E5).
class DfrmDeformer : public MeshDeformer {
public:
    DeformKind Kind() const override { return DeformKind::Dfrm; }
    int MaxChannels() const override { return wf_render::DfrmBlockSize; }
    DeformStatus Check(const float*, int n) const override
    {
        return n >= wf_render::DfrmInputCount ? DeformStatus::Ok : DeformStatus::BadInput;
    }
    DeformStatus Bind(const DeformTarget& t, const float*, int) override
    {
        const wf_render::DfrmData* data = t.object.GetDfrm();
        if (!data) return DeformStatus::NoMetadata;
        TriFace* faces = t.object.GetWritableFaceList();
        const int faceCount = t.object.GetFaceCount();
        std::vector<float> rest(3 * size_t(t.count)), normals(3 * size_t(faceCount));
        std::vector<int> indices(3 * size_t(faceCount));
        for (int i = 0; i < t.count; ++i) {
            const Vector3& p = t.vertices[i].position;
            rest[3*i] = p.X().AsFloat(); rest[3*i+1] = p.Y().AsFloat(); rest[3*i+2] = p.Z().AsFloat();
        }
        for (int f = 0; f < faceCount; ++f) {
            indices[3*f] = faces[f].v1Index; indices[3*f+1] = faces[f].v2Index; indices[3*f+2] = faces[f].v3Index;
            normals[3*f] = faces[f].normal.X().AsFloat(); normals[3*f+1] = faces[f].normal.Y().AsFloat();
            normals[3*f+2] = faces[f].normal.Z().AsFloat();
        }
        if (!_evaluator.Bind(*data, rest.data(), t.count, indices.data(), normals.data(), faceCount))
            return DeformStatus::NoMetadata;
        return DeformStatus::Ok;
    }
    DeformStatus Pose(const DeformTarget& t, const float* c, int n) override
    {
        const int status = _evaluator.Evaluate(c, n, t.time);
        if (status != wf_render::DfrmOk && status != wf_render::DfrmClamped) return DeformStatus(status);
        const std::vector<float>& p = _evaluator.Positions();
        for (int i = 0; i < t.count; ++i)
            t.vertices[i].position = Vector3(Scalar(p[3*i]), Scalar(p[3*i+1]), Scalar(p[3*i+2]));
        TriFace* faces = t.object.GetWritableFaceList();
        const std::vector<float>& nrm = _evaluator.FaceNormals();
        const int faceCount = t.object.GetFaceCount();
        for (int f = 0; f < faceCount; ++f)
            if (_evaluator.FaceNormalDriven(f))
                faces[f].normal = Vector3ToPS12(Vector3(Scalar(nrm[3*f]), Scalar(nrm[3*f+1]), Scalar(nrm[3*f+2])));
        return DeformStatus(status);
    }
    int Outputs(float* out, int max) const override
    {
        const int count = std::min(max, 6);
        for (int i = 0; i < count; ++i) out[i] = _evaluator.Outputs()[i];
        return count;
    }
private:
    wf_render::DfrmEvaluator _evaluator;
};

} // namespace

std::unique_ptr<MeshDeformer> MakeDeformer(DeformKind kind)
{
    switch (kind) {
        case DeformKind::Fish:  return std::unique_ptr<MeshDeformer>(new FishDeformer);
        case DeformKind::Fin:   return std::unique_ptr<MeshDeformer>(new FinDeformer);
        case DeformKind::Swim:  return std::unique_ptr<MeshDeformer>(new SwimDeformer);
        case DeformKind::Jelly: return std::unique_ptr<MeshDeformer>(new JellyDeformer);
        case DeformKind::Lion:  return std::unique_ptr<MeshDeformer>(new LionDeformer);
        case DeformKind::Dfrm:  return std::unique_ptr<MeshDeformer>(new DfrmDeformer);
        default:                return nullptr;
    }
}
