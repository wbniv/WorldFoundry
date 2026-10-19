// object_picker: the 3D object picker's pure geometry (engine/object_picker.hpp).
// Projection, arrow choice on synthetic layouts (row, column, diagonal, the
// +-60 degree cone, behind the camera, off screen), 12 px same-spot grouping
// and the mouse ray pick. See docs/plans/2026-10-16-runtime-object-editing.md,
// verification step 9.
#include "object_picker.hpp"
#include <cstdio>
#include <cstdlib>

static int failures=0;
#define CHECK(cond) do{ if(!(cond)){ std::printf("FAIL %s:%d: %s\n",__FILE__,__LINE__,#cond); ++failures; } }while(0)

using namespace wfpick;

// Camera at the origin looking down -Z with +Y up; 60 degree vertical fov, 16:9.
static Camera camera(){
    Camera c;
    for(int i=0;i<16;++i)c.view[i]=c.proj[i]=0;
    c.view[0]=c.view[5]=c.view[10]=c.view[15]=1;
    const float f=1/std::tan(30*3.14159265f/180),aspect=16.f/9,n=.1f,far=100;
    c.proj[0]=f/aspect;c.proj[5]=f;c.proj[10]=(far+n)/(n-far);c.proj[11]=-1;c.proj[14]=2*far*n/(n-far);
    return c;
}
static Candidate gear(uint32_t actor,float x,float y,float z){Candidate c;c.actor=actor;c.label="Object "+std::to_string(actor);c.position={x,y,z};return c;}
static Candidate box(uint32_t actor,Vec3 lo,Vec3 hi){Candidate c;c.actor=actor;c.label="Box "+std::to_string(actor);c.bounded=true;c.lo=lo;c.hi=hi;return c;}
// The target holding a candidate index, or -1.
static int targetOf(const std::vector<Target>& targets,size_t candidate){
    for(size_t i=0;i<targets.size();++i)for(auto m:targets[i].members)if(m==candidate)return int(i);
    return -1;
}

int main(){
    const Camera cam=camera();
    const float pxPerUnit=960*(1/std::tan(30*3.14159265f/180))/(16.f/9)/10;  // at z=-10, horizontally

    // ---- projection
    float sx=0,sy=0;
    CHECK(projectPoint(cam,{0,0,-10},sx,sy)&&std::fabs(sx-960)<.01f&&std::fabs(sy-540)<.01f);
    CHECK(projectPoint(cam,{1,0,-10},sx,sy)&&std::fabs(sx-(960+pxPerUnit))<.05f);
    CHECK(projectPoint(cam,{0,1,-10},sx,sy)&&sy<540);                 // +Y is screen up
    CHECK(!projectPoint(cam,{0,0,5},sx,sy));                          // behind the camera
    {Target t;CHECK(projectCandidate(cam,box(1,{-1,-1,-11},{1,1,-9}),t)&&!t.gear&&t.x0<960&&t.x1>960&&t.y0<540&&t.y1>540&&t.x1-t.x0>2*pxPerUnit*.9f);}
    {Target t;CHECK(projectCandidate(cam,gear(1,0,0,-10),t)&&t.gear&&std::fabs(t.x1-t.x0-2*kGearPx)<.01f);}

    // ---- behind the camera and off screen are skipped
    {
        std::vector<Candidate> c={gear(1,0,0,-10),gear(2,0,0,6),gear(3,100,0,-10),gear(4,0,-100,-10)};
        auto t=layout(cam,c);
        CHECK(t.size()==1&&t[0].members.size()==1&&t[0].members[0]==0);
    }
    // Nothing in view: no targets, no highlight.
    {
        std::vector<Candidate> c={gear(1,0,0,6)};
        auto t=layout(cam,c);CHECK(t.empty()&&nearestCentre(t)==-1&&step(t,-1,Right)==-1);
    }

    // ---- a row: first highlight is nearest the centre; Left/Right walk it
    {
        std::vector<Candidate> c={gear(1,-3,0,-10),gear(2,.2f,0,-10),gear(3,3,0,-10),gear(4,6,0,-10)};
        auto t=layout(cam,c);CHECK(t.size()==4);
        int h=nearestCentre(t);CHECK(h==targetOf(t,1));
        CHECK(step(t,h,Right)==targetOf(t,2));
        CHECK(step(t,targetOf(t,2),Right)==targetOf(t,3));
        CHECK(step(t,h,Left)==targetOf(t,0));
        CHECK(step(t,targetOf(t,0),Left)==targetOf(t,0));           // nothing further: stays
        CHECK(step(t,h,Up)==h&&step(t,h,Down)==h);                   // nothing above or below a row
    }
    // ---- a column: Up/Down walk it, Left/Right stay
    {
        std::vector<Candidate> c={gear(1,0,-2,-10),gear(2,0,0,-10),gear(3,0,2,-10)};
        auto t=layout(cam,c);int h=nearestCentre(t);CHECK(h==targetOf(t,1));
        CHECK(step(t,h,Up)==targetOf(t,2));CHECK(step(t,h,Down)==targetOf(t,0));
        CHECK(step(t,h,Left)==h&&step(t,h,Right)==h);
    }
    // ---- a diagonal: inside the 60 degree cone, but a straight neighbour scores better
    {
        std::vector<Candidate> c={gear(1,0,0,-10),gear(2,2,2,-10),gear(3,4,0,-10)};
        auto t=layout(cam,c);int h=targetOf(t,0);
        // Candidate 2 is 45 degrees up-right on screen (equal pixel offsets).
        CHECK(std::fabs((t[targetOf(t,1)].cx-t[h].cx)+(t[targetOf(t,1)].cy-t[h].cy))<1);
        CHECK(step(t,h,Right)==targetOf(t,2));                      // 4+0 beats 2.83+2*2
        CHECK(step(t,h,Up)==targetOf(t,1));                         // only candidate within the cone
        CHECK(step(t,targetOf(t,1),Left)==h);                       // back: h is 45 degrees down-left
    }
    // ---- the cone edge: 70 degrees off the arrow is outside, 50 is inside
    {
        auto at=[&](float degrees){const float r=3,a=degrees*3.14159265f/180;
            Target o;o.cx=960;o.cy=540;o.members={0};Target p;p.cx=960+r*100*std::cos(a);p.cy=540-r*100*std::sin(a);p.members={1};
            return std::vector<Target>{o,p};};
        auto inside=at(50),outside=at(70);
        CHECK(step(inside,0,Right)==1);CHECK(step(outside,0,Right)==0);CHECK(step(outside,0,Up)==1);
    }

    // ---- same spot: centres within 12 px share one bracket
    {
        const float near=8/pxPerUnit,far=20/pxPerUnit;
        std::vector<Candidate> c={gear(1,0,0,-10),gear(2,near,0,-10),gear(3,3,0,-10),gear(4,3+far,0,-10)};
        auto t=layout(cam,c);
        CHECK(t.size()==3);
        CHECK(targetOf(t,0)==targetOf(t,1)&&t[size_t(targetOf(t,0))].members.size()==2);
        CHECK(targetOf(t,2)!=targetOf(t,3));
        // Exactly the same position (the baseline fixture's case).
        std::vector<Candidate> same={gear(1,2,1,-10),gear(2,2,1,-10)};
        auto s=layout(cam,same);CHECK(s.size()==1&&s[0].members.size()==2&&s[0].gear);
        // A 12 px threshold, not more.
        std::vector<Candidate> inside={gear(1,0,0,-10),gear(2,11.5f/pxPerUnit,0,-10)};
        std::vector<Candidate> outside={gear(1,0,0,-10),gear(2,13/pxPerUnit,0,-10)};
        CHECK(layout(cam,inside).size()==1);CHECK(layout(cam,outside).size()==2);
    }

    // ---- mouse ray pick
    {
        Ray ray;CHECK(cursorRay(cam,960,540,ray));
        CHECK(std::fabs(ray.origin.x)<1e-4f&&std::fabs(ray.origin.y)<1e-4f&&std::fabs(ray.origin.z)<1e-4f);
        CHECK(std::fabs(ray.dir.z+1)<1e-4f);
        std::vector<Candidate> c={box(1,{-1,-1,-11},{1,1,-9}),box(2,{-.5f,-.5f,-6},{.5f,.5f,-5}),gear(3,5,0,-10)};
        CHECK(rayPick(c,ray)==1);                                    // the nearer of two boxes
        CHECK(projectPoint(cam,{5,0,-10},sx,sy)&&cursorRay(cam,sx,sy,ray)&&rayPick(c,ray)==2);  // a gear under the cursor
        CHECK(projectPoint(cam,{5.3f,0,-10},sx,sy)&&cursorRay(cam,sx,sy,ray)&&rayPick(c,ray)==2);  // within its sphere
        CHECK(projectPoint(cam,{5.6f,0,-10},sx,sy)&&cursorRay(cam,sx,sy,ray)&&rayPick(c,ray)==-1); // outside it
        CHECK(cursorRay(cam,10,10,ray)&&rayPick(c,ray)==-1);         // empty corner
        std::vector<Candidate> behind={box(1,{-1,-1,1},{1,1,3})};
        CHECK(cursorRay(cam,960,540,ray)&&rayPick(behind,ray)==-1);  // behind the eye is no hit
    }

    if(failures){std::printf("object_picker: %d failure(s)\n",failures);return 1;}
    std::printf("object_picker: projection, arrows (row, column, diagonal, cone, behind, off screen), 12 px grouping and ray pick passed\n");
    return 0;
}
