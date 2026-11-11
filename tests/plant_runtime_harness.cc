// Portable seeded growth and settings contracts, including phone session replay.
#include <game/plant_ui.h>
#include <game/runtime_property_controls.h>
#include <game/ui_font.hp>
#include <cassert>
#include <fstream>
#include <iostream>
int main(int argc,char** argv){
 assert(argc==2);std::ifstream font(argv[1],std::ios::binary);
 std::vector<uint8_t> atlas((std::istreambuf_iterator<char>(font)),{});const char* fontError=nullptr;
 assert(wfui::Load(atlas.data(),atlas.size(),fontError));
 propertyui::TextRequest request;propertyui::textHost().show=[&](const propertyui::TextRequest& value){request=value;return true;};propertyui::textHost().hide=[](uint64_t){};
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
 uint32_t n;assert(planted::parseSeed("2147483647",n)&&n==INT32_MAX);for(auto s:{"2147483648","4294967296","-1","","1e2","1.2"," 1","12345678901"})assert(!planted::parseSeed(s,n));assert(planted::parseSeed("0",n)&&n==0);
 auto& s=planted::state();s.active=true;planted::regenerate(713,false);
 auto actorGeneration=s.generation;auto geometry=s.geometryGeneration;
 planted::applyActorSettings(0,false,5,false,true,false,false);
 assert(s.seed==713&&s.generation==actorGeneration&&s.speed==5&&!s.textures&&s.geometryGeneration==geometry+1);
 planted::applyActorSettings(42,true,2,true,false,true,true);
 assert(s.seed==42&&s.salt&&s.speed==2&&s.textures&&!s.sway&&s.generation==actorGeneration+1);
 wfprops::Registry actorRegistry;wfprops::Object actorSettings;actorSettings.actor=9;actorSettings.schema="PlantedTankSettings";actorSettings.oadBacked=true;
 auto actorField=[&](unsigned id,const char* key,const char* value){wfprops::Field f;f.id=id;f.key=key;actorSettings.fields.push_back(f);actorSettings.values[id]=value;};
 actorField(129,"Seed","56");actorField(130,"Water type","1");actorField(131,"Growth speed","4");
 actorField(132,"Initial age","12");actorField(133,"Textures","0");actorField(134,"Sway","1");actorField(135,"Random seed on entry","0");
 std::string error;assert(actorRegistry.add(std::move(actorSettings),error));wfprops::activeRegistry()=&actorRegistry;
 planted::enter();assert(s.seed==56&&s.salt&&s.speed==4&&s.age==12&&!s.textures&&s.sway);
 assert(*actorRegistry.object(9)->get(129)=="56");wfprops::activeRegistry()=nullptr;
 s.textures=true;s.sway=true;planted::regenerate(713,false);s.speed=3;planted::tick(.1,0);assert(s.age==.1f);s.speed=0;planted::tick(.1,0);assert(s.age==.1f&&s.water==.2f);planted::open();planted::tick(.1,0);assert(s.water==.2f);auto session=wfprops::host().session();
 auto send=[&](const std::string& verb,const std::string& tail=""){planted::command("r:"+std::to_string(planted::form().edit.session)+":"+verb+(tail.empty()?"":":"+tail));};
 auto fieldId=[&](const char* key){auto* f=planted::fieldNamed(*planted::form().edit.object(),key);assert(f);return f->id;};
 auto set=[&](const char* key,const char* value){send("set",std::to_string(fieldId(key))+":"+value);};
 planted::command("r:0:set:1:42");assert(s.seed==713&&wfprops::host().modal);
 set("Seed","2147483647");set("Water type","1");set("Growth speed","4");send("action","100");assert(s.seed==INT32_MAX&&s.salt&&s.speed==4&&!wfprops::host().modal);
 auto generation=s.generation;planted::command("r:"+std::to_string(session)+":action:100");assert(s.generation==generation);
 planted::input(0,.05);assert(planted::input(1,.05)==0);assert(planted::input(0,.05)==1);for(int i=0;i<25;i++){planted::input(1,.05);planted::uiInput(1);}assert(wfprops::host().modal&&!planted::form().drawer);assert(planted::input(0,.05)==0);planted::uiInput(0);assert(!planted::form().drawer);planted::uiInput(1);assert(planted::form().drawer);planted::uiInput(0);
 planted::cancel();planted::open();auto keptAge=s.age;auto keptGeneration=s.generation;set("Growth speed","1");assert(planted::apply());assert(s.age==keptAge&&s.generation==keptGeneration&&s.speed==1&&!wfprops::host().modal);
 planted::open();set("Seed","42");set("Water type","0");assert(planted::apply());assert(s.seed==42&&!s.salt&&s.age==0&&!wfprops::host().modal);
 planted::open();set("Seed","2147483648");assert(!planted::apply()&&wfprops::host().modal);planted::cancel();planted::open();
 auto press=[&](uint32_t button){planted::uiInput(0);planted::uiInput(button);};press(1);assert(planted::form().drawer&&request.mode==3);
 propertyui::completeText(request.session,request.field,"11",true);assert(!planted::form().drawer&&planted::form().value()=="11");
 press(1);assert(planted::form().drawer);
 assert(!planted::apply()&&wfprops::host().modal&&!planted::form().drawer);
 wfprops::host().phone=true;auto draft=planted::form().edit.draft;press(1);assert(planted::form().edit.draft==draft);wfprops::host().phone=false;
 std::vector<PhonepadRect> rects;planted::buildUI(960,540,rects);assert(!rects.empty());for(auto r:rects)assert(r.x0>=0&&r.y0>=0&&r.x1<=960&&r.y1<=540);
 auto thumb=[&](){rects.clear();planted::buildUI(960,540,rects);float x=-1;int count=0;for(auto r:rects)if(r.rgba==0xefce83ffu){x=r.x0;count++;assert(r.x0>=0&&r.x1<=960&&r.y0>=0&&r.y1<=540);}assert(count==1);return x;};
 assert(planted::form().edit.set(fieldId("Growth speed"),"0"));float minimumThumb=thumb();assert(planted::form().edit.set(fieldId("Growth speed"),"6"));assert(thumb()>minimumThumb+400);
 planted::leave();assert(!s.active&&!wfprops::host().modal&&s.chunks[0].vertices.empty());std::cout<<"Plant runtime contracts passed\n";
}
