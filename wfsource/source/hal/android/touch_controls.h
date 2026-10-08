// Shared Android control geometry and pointer-release logic; no platform calls.
#ifndef WF_ANDROID_TOUCH_CONTROLS_H
#define WF_ANDROID_TOUCH_CONTROLS_H
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <vector>
namespace androidtouch {
constexpr uint32_t A=1, B=2, C=4, D=8;
constexpr uint32_t Up=1u<<11, Down=1u<<12, Right=1u<<13, Left=1u<<14;
struct Rect {
    float x0=0,y0=0,x1=0,y1=0;
    bool contains(float x,float y) const {return x>=x0&&x<x1&&y>=y0&&y<y1;}
};
struct Control {Rect rect;uint32_t bit;const char* label;};
struct Layout {Control controls[8]{};Rect pad;float cell=0;bool valid=false;};
struct Point {float x,y;int id=0;};
struct Stick {float x=0,y=0;uint32_t bits=0;};
inline float stickRadius(const Layout& l){return l.cell*1.2f;}
inline Stick stick(const Layout& l,float x,float y) {
    const float radius=stickRadius(l);
    if(!l.valid||radius<=0)return {};
    float dx=(x-(l.pad.x0+l.pad.x1)/2)/radius;
    float dy=(y-(l.pad.y0+l.pad.y1)/2)/radius;
    const float distance=std::hypot(dx,dy);
    if(distance>1){dx/=distance;dy/=distance;}
    return {dx,dy,(dx<-.5f?Left:dx>.5f?Right:0)|(dy<-.5f?Up:dy>.5f?Down:0)};
}
inline bool inStick(const Layout& l,float x,float y) {
    const float dx=x-(l.pad.x0+l.pad.x1)/2,dy=y-(l.pad.y0+l.pad.y1)/2;
    const float radius=stickRadius(l);
    return l.valid&&dx*dx+dy*dy<=radius*radius*1.000001f;
}
inline Layout layout(float w,float h,float density,float bottomInset=0) {
    Layout l;
    if(w<=0||h<=0||density<=0)return l;
    const float margin=12*density;
    const float bottom=h-std::max(bottomInset,24*density)-6*density;
    const float availableH=bottom-margin;
    float cell=std::max(48*density,std::min(64*density,availableH*.15f));
    cell=std::min(cell,std::min(availableH/3,(w-3*margin)/5.4f));
    if(cell<=0)return l;
    l.cell=cell;l.valid=true;
    const float padCell=stickRadius(l)*2/3;
    l.pad={margin,bottom-3*padCell,margin+3*padCell,bottom};
    auto square=[&](float x,float y,float edge){return Rect{x,y,x+edge,y+edge};};
    l.controls[0]={square(margin,l.pad.y0+padCell,padCell),Left,"<"};
    l.controls[1]={square(margin+2*padCell,l.pad.y0+padCell,padCell),Right,">"};
    l.controls[2]={square(margin+padCell,l.pad.y0,padCell),Up,"^"};
    l.controls[3]={square(margin+padCell,l.pad.y0+2*padCell,padCell),Down,"v"};
    const float edge=1.2f*cell,x=w-margin-edge,y=bottom-edge;
    l.controls[4]={square(x,y,edge),A,"A"};
    l.controls[5]={square(x,y-edge,edge),B,"B"};
    l.controls[6]={square(x-edge,y,edge),C,"C"};
    l.controls[7]={square(x-edge,y-edge,edge),D,"D"};
    return l;
}
inline uint32_t hit(const Layout& l,float x,float y) {
    if(!l.valid)return 0;
    if(inStick(l,x,y))return stick(l,x,y).bits;
    for(int i=4;i<8;++i)if(l.controls[i].rect.contains(x,y))return l.controls[i].bit;
    return 0;
}
inline uint32_t buttons(const Layout& l,const Point* points,size_t count,int released=-1,bool clear=false) {
    if(clear)return 0;
    uint32_t mask=0;
    for(size_t i=0;i<count;++i)if(int(i)!=released)mask|=hit(l,points[i].x,points[i].y);
    return mask;
}
// Match the Aquarium browser pad: one captured stick thumb plus independent
// captured action fingers; sliding outside a control doesn't release it.
enum class Action {Down,Move,Up,Cancel};
struct State {
    struct Owner {int id;uint32_t bit;bool joystick;};
    std::vector<Owner> owners;
    Stick position;
    void clear(){owners.clear();position={};}
    uint32_t update(const Layout& l,const Point* points,size_t count,Action action,int changed=0) {
        if(action==Action::Cancel){clear();return 0;}
        if(changed>=0&&size_t(changed)<count) {
            const auto& p=points[changed];
            if(action==Action::Up) {
                owners.erase(std::remove_if(owners.begin(),owners.end(),[&](const Owner& o){return o.id==p.id;}),owners.end());
            } else if(action==Action::Down) {
                bool taken=false;for(const auto& o:owners)if(o.joystick)taken=true;
                if(inStick(l,p.x,p.y)) {if(!taken)owners.push_back({p.id,0,true});}
                else for(int i=4;i<8;++i)if(l.controls[i].rect.contains(p.x,p.y)) {
                    owners.push_back({p.id,l.controls[i].bit,false});break;
                }
            }
        }
        position={};uint32_t mask=0;
        for(const auto& o:owners)for(size_t i=0;i<count;++i)if(points[i].id==o.id) {
            if(o.joystick){position=stick(l,points[i].x,points[i].y);mask|=position.bits;}
            else mask|=o.bit;
            break;
        }
        return mask;
    }
};
} // namespace androidtouch
#endif
