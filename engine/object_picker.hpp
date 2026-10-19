// 3D object picker: pure geometry for choosing an editable object by pointing at
// it in the scene (docs/plans/2026-10-16-runtime-object-editing.md, Phase P).
//
// Header-only and engine-free, so tests/object_picker_test.cc runs it without a
// level, a GL context or the property host. The host feeds it:
//   - Entry: the chooser's candidates, (actor id, label). Phase P takes them from
//     today's RP01 owners; the redesign swaps in the LevelObj Editable Objects
//     list without touching anything below.
//   - Candidate: where an Entry is in the world (bounds, or a gear at a point).
//   - Camera: the active camera's view and projection (column-major, GL style).
// Layout is in a 1920x1080 logical screen, the same space the TV form draws in.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace wfpick {

struct Vec3 { float x=0, y=0, z=0; };

// One candidate offered by the chooser. Nothing else is ever a candidate.
struct Entry { uint32_t actor=0; std::string label; };

// World placement of an Entry. Meshless objects (settings holders) have no
// bounds and are shown as a gear at their position.
struct Candidate {
    uint32_t actor=0; std::string label;
    bool bounded=false; Vec3 lo, hi; Vec3 position;
    Vec3 centre() const { return bounded ? Vec3{(lo.x+hi.x)*.5f,(lo.y+hi.y)*.5f,(lo.z+hi.z)*.5f} : position; }
};

// Column-major 4x4 matrices, as glLoadMatrixf takes them.
struct Camera { float view[16]={}, proj[16]={}; float width=1920, height=1080; };

constexpr float kGroupPx=12;       // projected centres closer than this share one bracket
constexpr float kGearPx=32;        // half size of a gear marker's bracket
constexpr float kMinBracketPx=18;  // half size floor for small bounded objects
constexpr float kGearRadius=.35f;  // world radius a mouse ray must pass within for a gear

inline void transform(const float m[16], const float in[4], float out[4]) {
    for (int r=0; r<4; ++r) { out[r]=0; for (int c=0; c<4; ++c) out[r]+=m[c*4+r]*in[c]; }
}

// World point to logical screen pixels. False when behind the camera.
inline bool projectPoint(const Camera& cam, const Vec3& p, float& sx, float& sy) {
    const float world[4]={p.x,p.y,p.z,1}; float eye[4], clip[4];
    transform(cam.view, world, eye); transform(cam.proj, eye, clip);
    if (!(clip[3] > 1e-6f)) return false;
    const float nx=clip[0]/clip[3], ny=clip[1]/clip[3];
    sx=(nx+1)*cam.width*.5f; sy=(1-ny)*cam.height*.5f;
    return std::isfinite(sx) && std::isfinite(sy);
}

// One bracket on screen: a single candidate or several on the same spot.
struct Target {
    std::vector<size_t> members;  // indices into the candidate list
    float cx=0, cy=0;             // projected centre
    float x0=0, y0=0, x1=0, y1=0; // bracket rectangle
    bool gear=false;              // every member is meshless
};

// Projects one candidate. False when its centre is behind the camera or off screen.
inline bool projectCandidate(const Camera& cam, const Candidate& c, Target& t) {
    const Vec3 mid=c.centre();
    if (!projectPoint(cam, mid, t.cx, t.cy)) return false;
    if (t.cx < 0 || t.cy < 0 || t.cx > cam.width || t.cy > cam.height) return false;
    t.gear=!c.bounded;
    float half=kGearPx;
    t.x0=t.cx-half; t.x1=t.cx+half; t.y0=t.cy-half; t.y1=t.cy+half;
    if (c.bounded) {
        bool any=false; float a=0,b=0,x0=0,y0=0,x1=0,y1=0;
        for (int i=0; i<8; ++i) {
            const Vec3 corner{(i&1)?c.hi.x:c.lo.x,(i&2)?c.hi.y:c.lo.y,(i&4)?c.hi.z:c.lo.z};
            if (!projectPoint(cam, corner, a, b)) continue;
            if (!any) { x0=x1=a; y0=y1=b; any=true; }
            x0=std::min(x0,a); x1=std::max(x1,a); y0=std::min(y0,b); y1=std::max(y1,b);
        }
        if (any) {
            x0=std::min(x0,t.cx-kMinBracketPx); x1=std::max(x1,t.cx+kMinBracketPx);
            y0=std::min(y0,t.cy-kMinBracketPx); y1=std::max(y1,t.cy+kMinBracketPx);
            t.x0=std::max(0.f,x0); t.y0=std::max(0.f,y0);
            t.x1=std::min(cam.width,x1); t.y1=std::min(cam.height,y1);
        }
    }
    return true;
}

// Every visible candidate, with those whose centres fall within `groupPx` of
// each other (transitively) merged into one Target.
inline std::vector<Target> layout(const Camera& cam, const std::vector<Candidate>& candidates, float groupPx=kGroupPx) {
    std::vector<Target> single;
    for (size_t i=0; i<candidates.size(); ++i) {
        Target t; if (!projectCandidate(cam, candidates[i], t)) continue;
        t.members.push_back(i); single.push_back(t);
    }
    std::vector<size_t> parent(single.size());
    for (size_t i=0; i<parent.size(); ++i) parent[i]=i;
    auto root=[&](size_t i){ while (parent[i]!=i) i=parent[i]=parent[parent[i]]; return i; };
    for (size_t i=0; i<single.size(); ++i)
        for (size_t j=i+1; j<single.size(); ++j)
            if (std::hypot(single[i].cx-single[j].cx, single[i].cy-single[j].cy) <= groupPx) parent[root(j)]=root(i);
    std::vector<Target> merged; std::vector<int> slot(single.size(), -1);
    for (size_t i=0; i<single.size(); ++i) {
        const size_t r=root(i);
        if (slot[r] < 0) { slot[r]=int(merged.size()); merged.push_back(single[i]); continue; }
        Target& m=merged[size_t(slot[r])]; const Target& s=single[i];
        const float n=float(m.members.size());
        m.cx=(m.cx*n+s.cx)/(n+1); m.cy=(m.cy*n+s.cy)/(n+1);
        m.x0=std::min(m.x0,s.x0); m.y0=std::min(m.y0,s.y0); m.x1=std::max(m.x1,s.x1); m.y1=std::max(m.y1,s.y1);
        m.gear=m.gear&&s.gear; m.members.push_back(s.members[0]);
    }
    return merged;
}

// The first highlight: the target nearest the screen centre; -1 when none.
inline int nearestCentre(const std::vector<Target>& targets, float width=1920, float height=1080) {
    int best=-1; float bestD=0;
    for (size_t i=0; i<targets.size(); ++i) {
        const float d=std::hypot(targets[i].cx-width*.5f, targets[i].cy-height*.5f);
        if (best < 0 || d < bestD) { best=int(i); bestD=d; }
    }
    return best;
}

enum Direction { Up, Down, Left, Right };

// The best target in a direction: within +-60 degrees of the arrow, smallest
// distance plus twice the perpendicular offset. Returns `from` when none.
inline int step(const std::vector<Target>& targets, int from, Direction dir) {
    if (from < 0 || size_t(from) >= targets.size()) return from;
    const float ux=dir==Left?-1.f:dir==Right?1.f:0.f, uy=dir==Up?-1.f:dir==Down?1.f:0.f;
    const float tan60=std::sqrt(3.f);
    int best=from; float bestScore=0;
    for (size_t i=0; i<targets.size(); ++i) {
        if (int(i)==from) continue;
        const float dx=targets[i].cx-targets[size_t(from)].cx, dy=targets[i].cy-targets[size_t(from)].cy;
        const float along=dx*ux+dy*uy, perp=std::fabs(dx*uy-dy*ux);
        if (!(along > 0) || perp > along*tan60+1e-4f) continue;
        const float score=std::hypot(dx,dy)+2*perp;
        if (best==from || score < bestScore) { best=int(i); bestScore=score; }
    }
    return best;
}

// ---- mouse ---------------------------------------------------------------------

struct Ray { Vec3 origin, dir; };

inline bool invert(const float m[16], float out[16]) {
    float inv[16];
    inv[0]=m[5]*m[10]*m[15]-m[5]*m[11]*m[14]-m[9]*m[6]*m[15]+m[9]*m[7]*m[14]+m[13]*m[6]*m[11]-m[13]*m[7]*m[10];
    inv[4]=-m[4]*m[10]*m[15]+m[4]*m[11]*m[14]+m[8]*m[6]*m[15]-m[8]*m[7]*m[14]-m[12]*m[6]*m[11]+m[12]*m[7]*m[10];
    inv[8]=m[4]*m[9]*m[15]-m[4]*m[11]*m[13]-m[8]*m[5]*m[15]+m[8]*m[7]*m[13]+m[12]*m[5]*m[11]-m[12]*m[7]*m[9];
    inv[12]=-m[4]*m[9]*m[14]+m[4]*m[10]*m[13]+m[8]*m[5]*m[14]-m[8]*m[6]*m[13]-m[12]*m[5]*m[10]+m[12]*m[6]*m[9];
    inv[1]=-m[1]*m[10]*m[15]+m[1]*m[11]*m[14]+m[9]*m[2]*m[15]-m[9]*m[3]*m[14]-m[13]*m[2]*m[11]+m[13]*m[3]*m[10];
    inv[5]=m[0]*m[10]*m[15]-m[0]*m[11]*m[14]-m[8]*m[2]*m[15]+m[8]*m[3]*m[14]+m[12]*m[2]*m[11]-m[12]*m[3]*m[10];
    inv[9]=-m[0]*m[9]*m[15]+m[0]*m[11]*m[13]+m[8]*m[1]*m[15]-m[8]*m[3]*m[13]-m[12]*m[1]*m[11]+m[12]*m[3]*m[9];
    inv[13]=m[0]*m[9]*m[14]-m[0]*m[10]*m[13]-m[8]*m[1]*m[14]+m[8]*m[2]*m[13]+m[12]*m[1]*m[10]-m[12]*m[2]*m[9];
    inv[2]=m[1]*m[6]*m[15]-m[1]*m[7]*m[14]-m[5]*m[2]*m[15]+m[5]*m[3]*m[14]+m[13]*m[2]*m[7]-m[13]*m[3]*m[6];
    inv[6]=-m[0]*m[6]*m[15]+m[0]*m[7]*m[14]+m[4]*m[2]*m[15]-m[4]*m[3]*m[14]-m[12]*m[2]*m[7]+m[12]*m[3]*m[6];
    inv[10]=m[0]*m[5]*m[15]-m[0]*m[7]*m[13]-m[4]*m[1]*m[15]+m[4]*m[3]*m[13]+m[12]*m[1]*m[7]-m[12]*m[3]*m[5];
    inv[14]=-m[0]*m[5]*m[14]+m[0]*m[6]*m[13]+m[4]*m[1]*m[14]-m[4]*m[2]*m[13]-m[12]*m[1]*m[6]+m[12]*m[2]*m[5];
    inv[3]=-m[1]*m[6]*m[11]+m[1]*m[7]*m[10]+m[5]*m[2]*m[11]-m[5]*m[3]*m[10]-m[9]*m[2]*m[7]+m[9]*m[3]*m[6];
    inv[7]=m[0]*m[6]*m[11]-m[0]*m[7]*m[10]-m[4]*m[2]*m[11]+m[4]*m[3]*m[10]+m[8]*m[2]*m[7]-m[8]*m[3]*m[6];
    inv[11]=-m[0]*m[5]*m[11]+m[0]*m[7]*m[9]+m[4]*m[1]*m[11]-m[4]*m[3]*m[9]-m[8]*m[1]*m[7]+m[8]*m[3]*m[5];
    inv[15]=m[0]*m[5]*m[10]-m[0]*m[6]*m[9]-m[4]*m[1]*m[10]+m[4]*m[2]*m[9]+m[8]*m[1]*m[6]-m[8]*m[2]*m[5];
    const float det=m[0]*inv[0]+m[1]*inv[4]+m[2]*inv[8]+m[3]*inv[12];
    if (!(std::fabs(det) > 1e-12f)) return false;
    for (int i=0; i<16; ++i) out[i]=inv[i]/det;
    return true;
}

// The world ray under a logical screen pixel: from the eye through the pixel.
// Uses NDC z = 0.5, inside the clip range of both GL (-1..1) and Metal (0..1).
inline bool cursorRay(const Camera& cam, float px, float py, Ray& ray) {
    float viewInv[16], vp[16], vpInv[16];
    if (!invert(cam.view, viewInv)) return false;
    for (int c=0; c<4; ++c) for (int r=0; r<4; ++r) { float s=0; for (int k=0; k<4; ++k) s+=cam.proj[k*4+r]*cam.view[c*4+k]; vp[c*4+r]=s; }
    if (!invert(vp, vpInv)) return false;
    const float ndc[4]={2*px/cam.width-1, 1-2*py/cam.height, .5f, 1}; float w[4];
    transform(vpInv, ndc, w);
    if (!(std::fabs(w[3]) > 1e-12f)) return false;
    ray.origin={viewInv[12], viewInv[13], viewInv[14]};
    Vec3 d{w[0]/w[3]-ray.origin.x, w[1]/w[3]-ray.origin.y, w[2]/w[3]-ray.origin.z};
    const float n=std::sqrt(d.x*d.x+d.y*d.y+d.z*d.z);
    if (!(n > 1e-12f)) return false;
    ray.dir={d.x/n, d.y/n, d.z/n};
    return true;
}

// Distance along the ray to an axis-aligned box; false on a miss.
inline bool hitBox(const Ray& ray, const Vec3& lo, const Vec3& hi, float& t) {
    float t0=0, t1=1e30f;
    const float o[3]={ray.origin.x,ray.origin.y,ray.origin.z}, d[3]={ray.dir.x,ray.dir.y,ray.dir.z};
    const float a[3]={lo.x,lo.y,lo.z}, b[3]={hi.x,hi.y,hi.z};
    for (int i=0; i<3; ++i) {
        if (std::fabs(d[i]) < 1e-12f) { if (o[i] < a[i] || o[i] > b[i]) return false; continue; }
        float n=(a[i]-o[i])/d[i], f=(b[i]-o[i])/d[i]; if (n > f) std::swap(n,f);
        t0=std::max(t0,n); t1=std::min(t1,f); if (t0 > t1) return false;
    }
    t=t0; return true;
}

inline bool hitSphere(const Ray& ray, const Vec3& c, float radius, float& t) {
    const float ox=ray.origin.x-c.x, oy=ray.origin.y-c.y, oz=ray.origin.z-c.z;
    const float b=ox*ray.dir.x+oy*ray.dir.y+oz*ray.dir.z, cc=ox*ox+oy*oy+oz*oz-radius*radius;
    const float disc=b*b-cc; if (disc < 0) return false;
    const float s=std::sqrt(disc); t=-b-s; if (t < 0) t=-b+s;
    return t >= 0;
}

// The nearest candidate the ray hits (bounds, or a small sphere for a gear); -1 on none.
inline int rayPick(const std::vector<Candidate>& candidates, const Ray& ray, float gearRadius=kGearRadius) {
    int best=-1; float bestT=0;
    for (size_t i=0; i<candidates.size(); ++i) {
        float t=0; const Candidate& c=candidates[i];
        if (!(c.bounded ? hitBox(ray,c.lo,c.hi,t) : hitSphere(ray,c.position,gearRadius,t))) continue;
        if (best < 0 || t < bestT) { best=int(i); bestT=t; }
    }
    return best;
}

}  // namespace wfpick
