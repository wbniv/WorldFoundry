#include <hal/android/touch_controls.h>
#include <cassert>
#include <cstdio>
using namespace androidtouch;
static Point center(const Rect& r){return {(r.x0+r.x1)/2,(r.y0+r.y1)/2};}
int main(){
    int checks=0;
    for(float density:{1.f,2.f,2.625f,3.f}) {
        const float w=855*density,h=384*density;
        auto l=layout(w,h,density,24*density);
        assert(l.valid&&l.cell>=48*density);++checks;
        for(const auto& c:l.controls) {
            auto p=center(c.rect);
            assert(hit(l,p.x,p.y)==c.bit);++checks;
            assert(c.rect.x0>=12*density&&c.rect.x1<=w-12*density+.01f);++checks;
            assert(c.rect.y0>=0&&c.rect.y1<=h-30*density+.01f);++checks;
        }
        const auto up=center(l.controls[2].rect),a=center(l.controls[4].rect);
        Point points[]={up,a};
        assert(buttons(l,points,2)==(Up|A));++checks;
        assert(buttons(l,points,2,0)==A);++checks;
        assert(buttons(l,points,2,1)==Up);++checks;
        assert(buttons(l,points,2,-1,true)==0);++checks;
        assert(hit(l,l.pad.x0+(l.pad.x1-l.pad.x0)/6,l.pad.y0+(l.pad.y1-l.pad.y0)/6)==(Left|Up));++checks;
        assert(hit(l,l.pad.x0+(l.pad.x1-l.pad.x0)*5/6,l.pad.y0+(l.pad.y1-l.pad.y0)*5/6)==(Right|Down));++checks;
        auto neutral=center(l.pad);
        assert(hit(l,neutral.x,neutral.y)==0);++checks;
        assert(hit(l,w-20*density,h-5*density)==0);++checks;
        auto inset=layout(w,h,density,60*density);
        assert(inset.controls[4].rect.y1<=h-66*density+.01f);++checks;
    }
    for(auto dimensions:{Point{320,768},Point{900,120},Point{0,0}}) {
        auto l=layout(dimensions.x,dimensions.y,1);
        if(dimensions.x==0){assert(!l.valid&&hit(l,0,0)==0);++checks;continue;}
        assert(l.valid);++checks;
        assert(l.pad.x1<l.controls[6].rect.x0);++checks;
    }
    auto l=layout(2244,1008,2.625f);
    const auto middle=center(l.pad),a=center(l.controls[4].rect);
    const float radius=stickRadius(l);
    assert(stick(l,middle.x+radius*.49f,middle.y).bits==0);++checks;
    assert(stick(l,middle.x+radius*.51f,middle.y).bits==Right);++checks;
    assert(!inStick(l,l.pad.x0,l.pad.y0));++checks;
    assert(inStick(l,middle.x,middle.y-radius));++checks;
    assert(!inStick(l,middle.x,middle.y-radius*1.001f));++checks;
    State state;
    Point p[]={{middle.x,middle.y,101},{a.x,a.y,202}};
    assert(state.update(l,p,1,Action::Down)==0);++checks;
    p[0].x=middle.x+radius*2;
    assert(state.update(l,p,1,Action::Move)==Right&&state.position.x==1);++checks;
    assert(state.update(l,p,2,Action::Down,1)==(Right|A));++checks;
    p[1].x=0;p[1].y=0;
    assert(state.update(l,p,2,Action::Move)==(Right|A));++checks;
    assert(state.update(l,p,2,Action::Up,1)==Right);++checks;
    assert(state.update(l,p,1,Action::Up)==0&&state.position.x==0);++checks;
    p[0]={middle.x,middle.y-radius,101};p[1]={a.x,a.y,202};
    assert(state.update(l,p,1,Action::Down)==Up);++checks;
    assert(state.update(l,p,2,Action::Down,1)==(Up|A));++checks;
    assert(state.update(l,p,2,Action::Up,0)==A);++checks;
    p[0]=p[1];
    assert(state.update(l,p,1,Action::Move)==A);++checks;
    assert(state.update(l,p,1,Action::Cancel)==0&&state.owners.empty());++checks;
    std::printf("PASS: %d Android touch control behavior checks\n",checks);
}
