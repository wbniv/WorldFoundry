// Portable seeded growth and settings contracts, including phone session replay.
#include <game/plant_ui.h>
#include <cassert>
#include <iostream>
int main(){
 for(bool salt:{false,true})for(unsigned seed:{0u,1u,713u,4294967295u}){
 auto a=plantgrowth::colonies(seed,salt),b=plantgrowth::colonies(seed,salt);
 assert(a.size()==384&&a.size()==b.size());
 for(size_t i=0;i<a.size();i++){assert(a[i].x==b[i].x&&a[i].y==b[i].y&&a[i].birth==b[i].birth);if(i>=16){assert(a[i].parent>=0&&size_t(a[i].parent)<i);assert(a[i].birth>a[a[i].parent].birth);assert(a[i].kind==a[a[i].parent].kind);}}
 auto c=plantgrowth::meshes(seed,salt,a);
 for(auto& ch:c){assert(ch.vertices.size()<30000&&ch.faces.size()<32000);
 for(auto& v:ch.vertices){assert(std::isfinite(v.u)&&std::isfinite(v.v)&&v.u>=4.f/255&&v.u<=235.f/255&&v.v>=20.f/255&&v.v<=251.f/255);}
 for(auto& v:ch.vertices)for(float age:{0.f,30.f,150.f,240.f})for(float water:{0.f,3.f,100.f}){auto p=plantgrowth::deformed(v,age,water);assert(std::isfinite(p.x)&&p.x>-5.969f&&p.x<5.969f&&p.y>-1.524f&&p.y<1.524f&&p.z>=.635f&&p.z<4.826f);if(age<=v.birth&&v.birth>0)assert(p.x==v.root.x&&p.y==v.root.y&&p.z==v.root.z);}
 for(auto& f:ch.faces)assert(f.a<ch.vertices.size()&&f.b<ch.vertices.size()&&f.c<ch.vertices.size());}
 }
 uint32_t n;assert(planted::parseSeed("4294967295",n)&&n==UINT32_MAX);for(auto s:{"4294967296","-1","","1e2","1.2"," 1","12345678901"})assert(!planted::parseSeed(s,n));assert(planted::parseSeed("0",n)&&n==0);
 auto& s=planted::state();s.active=true;planted::regenerate(713,false);s.speed=3;planted::tick(.1,0);assert(s.age==.1f);s.speed=0;planted::tick(.1,0);assert(s.age==.1f&&s.water==.2f);planted::open();planted::tick(.1,0);assert(s.water==.2f);auto session=planted::form().edit.session;
 auto send=[&](const std::string& verb,const std::string& tail=""){planted::command("r:"+std::to_string(planted::form().edit.session)+":"+verb+(tail.empty()?"":":"+tail));};
 planted::command("r:0:set:1:42");assert(s.seed==713&&wfprops::host().modal);
 send("set","1:4294967295");send("set","2:1");send("set","3:4");send("action","100");assert(s.seed==UINT32_MAX&&s.salt&&s.speed==4&&!wfprops::host().modal);
 auto generation=s.generation;planted::command("r:"+std::to_string(session)+":action:100");assert(s.generation==generation);
 planted::input(0,.05);assert(planted::input(1,.05)==0);assert(planted::input(0,.05)==1);for(int i=0;i<25;i++)planted::input(1,.05);assert(wfprops::host().modal);assert(planted::input(0,.05)==0);
 planted::cancel();planted::open();auto keptAge=s.age;auto keptGeneration=s.generation;send("set","3:1");assert(planted::apply());assert(s.age==keptAge&&s.generation==keptGeneration&&s.speed==1&&!wfprops::host().modal);
 planted::open();send("set","1:42");send("set","2:0");assert(planted::apply());assert(s.seed==42&&!s.salt&&s.age==0&&!wfprops::host().modal);
 planted::open();send("set","1:4294967296");assert(!planted::apply()&&wfprops::host().modal);planted::cancel();planted::open();
 auto press=[&](uint32_t button){planted::uiInput(0);planted::uiInput(button);};press(1);assert(planted::form().drawer);press(1);assert(planted::form().value()=="1");press(1);assert(planted::form().value()=="11");
 press(1u<<14);assert(planted::form().key==0);press(1u<<13);assert(planted::form().key==1);press(1u<<12);assert(planted::form().key==4);press(1u<<11);assert(planted::form().key==1);
 assert(!planted::apply()&&wfprops::host().modal&&!planted::form().drawer);
 wfprops::host().phone=true;auto draft=planted::form().edit.draft;press(1);assert(planted::form().edit.draft==draft);wfprops::host().phone=false;
 std::vector<PhonepadRect> rects;planted::buildUI(960,540,rects);assert(!rects.empty());for(auto r:rects)assert(r.x0>=0&&r.y0>=0&&r.x1<=960&&r.y1<=540);
 planted::leave();assert(!s.active&&!wfprops::host().modal&&s.chunks[0].vertices.empty());std::cout<<"Plant runtime contracts passed\n";
}
