#ifndef WF_PLANT_SETTINGS_H
#define WF_PLANT_SETTINGS_H
#include <game/plant_growth.h>
#include "../../../engine/runtime_property_form.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
namespace planted {
struct State {
 bool active=false,modal=false,phone=false,salt=false,draftSalt=false,pending=false,selector=false,sway=true;
 uint32_t seed=0,session=0; int speed=3,draftSpeed=3,focus=0;float age=0,water=0,hold=0;uint32_t previous=0;
 std::string draft,error;std::array<int,8> actors{};std::vector<plantgrowth::Shoot> shoots;std::array<plantgrowth::Chunk,8> chunks;
 uint32_t profileSeed=0;bool fixedSeed=false;float profileAge=-1;int profileSpeed=-1,profileWater=-1;
 unsigned generation=0; bool explicitSeed=false,seedTyped=false,profileSway=true,profileTexture=true,adjustSpeed=false,swallowA=false;unsigned topologySlot=0;
};
inline State& state(){static State s;return s;}
inline float speedValue(int i){constexpr float v[]={0,.25f,.5f,1,2,4,8};return v[std::max(0,std::min(6,i))];}
inline const char* speedLabel(int i){const char* v[]={"Paused","0.25x","0.5x","1x","2x","4x","8x"};return v[std::max(0,std::min(6,i))];}
inline uint32_t freshSeed(){static uint32_t serial=0;uint64_t t=std::chrono::steady_clock::now().time_since_epoch().count();plantgrowth::Random r(uint32_t(t)^uint32_t(t>>32)^++serial);return r.next();}
inline bool parseSeed(const std::string& v,uint32_t& result){if(v.empty()||v.size()>10||v.find_first_not_of("0123456789")!=std::string::npos)return false;uint64_t n=0;for(char c:v){n=n*10+unsigned(c-'0');if(n>UINT32_MAX)return false;}result=uint32_t(n);return true;}
inline void regenerate(uint32_t seed,bool salt){auto& s=state();s.seed=seed;s.salt=salt;s.age=s.water=0;auto started=std::chrono::steady_clock::now();s.shoots=plantgrowth::colonies(seed,salt);auto graphDone=std::chrono::steady_clock::now();s.chunks=plantgrowth::meshes(seed,salt,s.shoots);auto meshDone=std::chrono::steady_clock::now();s.topologySlot=0;s.generation++;s.previous=0;s.hold=0;s.swallowA=true;s.modal=false;s.pending=false;s.error.clear();std::fprintf(stderr,"PLANTS generation=%u seed=%u mode=%s shoots=%zu vertices=",s.generation,seed,salt?"saltwater":"freshwater",s.shoots.size());size_t verts=0,faces=0;for(const auto& c:s.chunks){verts+=c.vertices.size();faces+=c.faces.size();}std::fprintf(stderr,"%zu triangles=%zu graph_ms=%.3f mesh_ms=%.3f\n",verts,faces,std::chrono::duration<double,std::milli>(graphDone-started).count(),std::chrono::duration<double,std::milli>(meshDone-graphDone).count());}
inline void syncProperties();
inline void enter(){auto& s=state();s.active=true;s.modal=false;s.selector=false;s.previous=0;s.hold=0;uint32_t seed=s.explicitSeed?s.seed:freshSeed();s.explicitSeed=false;const char* fixed=std::getenv("WF_PLANT_SEED");uint32_t n;if(fixed&&parseSeed(fixed,n))seed=n;if(const char* m=std::getenv("WF_PLANT_WATER"))s.salt=std::string(m)=="saltwater";if(s.fixedSeed)seed=s.profileSeed;if(s.profileWater>=0)s.salt=s.profileWater;regenerate(seed,s.salt);if(s.profileAge>=0)s.age=s.profileAge;if(s.profileSpeed>=0)s.speed=s.profileSpeed;if(const char* a=std::getenv("WF_PLANT_AGE"))s.age=std::max(0.f,float(std::atof(a)));if(const char* p=std::getenv("WF_PLANT_SPEED"))s.speed=std::max(0,std::min(6,std::atoi(p)));s.sway=s.profileSway&&!(std::getenv("WF_PLANT_SWAY")&&std::string(std::getenv("WF_PLANT_SWAY"))=="0");syncProperties();}
inline wfprops::Form& form();
inline void leave(){form().edit.cancel();auto& s=state();s.active=s.modal=s.selector=false;s.actors.fill(0);s.shoots.clear();for(auto& c:s.chunks){plantgrowth::Chunk empty;c=std::move(empty);}}
inline wfprops::Form& form(){static wfprops::Form f;return f;}
inline wfprops::Registry& previewProperties(){static wfprops::Registry registry;static bool loaded=false;if(!loaded){const uint8_t bytes[]={
#include "../../../wflevels/aquarium_plants/settings-catalog.inc"
};std::string error;loaded=registry.load(bytes,sizeof(bytes),error);}return registry;}
inline wfprops::Registry& properties(){auto* r=wfprops::activeRegistry();return state().active&&r&&r->schema("PlantedTankSettings")?*r:previewProperties();}
inline void syncProperties(){auto& s=state();auto& r=properties();auto* o=r.schema("PlantedTankSettings");if(!o)return;std::string error;r.set(o->actor,1,std::to_string(s.seed),error);r.set(o->actor,2,s.salt?"1":"0",error);r.set(o->actor,3,std::to_string(s.speed),error);}
inline void cancel(){auto& s=state();form().edit.cancel();s.modal=false;s.error.clear();s.previous=0;s.hold=0;s.swallowA=true;}
inline bool commitProperties(bool force=false,bool random=false){auto& s=state();auto& e=form().edit;if(!e.open)return false;if(random)e.set(1,std::to_string(freshSeed()));if(!e.validate())return false;
 uint32_t seed=0;parseSeed(e.draft[1],seed);bool salt=e.draft[2]=="1";int speed=std::atoi(e.draft[3].c_str());if(!e.commit())return false;
 bool changed=seed!=s.seed||salt!=s.salt;s.speed=speed;if(s.selector){s.seed=seed;s.salt=salt;s.explicitSeed=true;s.pending=force;}else if(force||changed)regenerate(seed,salt);cancel();return true;}
inline void open(){auto& s=state();if(!s.active&&!s.selector)return;syncProperties();auto& registry=properties();auto* o=registry.schema("PlantedTankSettings");if(!o||!form().begin(registry,o->actor))return;s.modal=true;s.session=uint32_t(form().edit.session);s.previous=0;s.hold=0;
 form().action=[](const std::string& action){if(action=="cancel")cancel();else if(action=="apply")commitProperties();else if(action=="regenerate")commitProperties(true);else if(action=="random-seed")commitProperties(true,true);};}
inline bool submit(bool random=false,bool /*speedOnly*/=false){return commitProperties(true,random);}
inline bool apply(){if(!form().back())return false;return commitProperties();}
inline void tick(float dt,float /*phase*/){auto& s=state();if(!s.active||s.modal||!std::isfinite(dt))return;dt=dt>.2f?0:std::max(0.f,dt);s.age=std::min(240.f,s.age+dt*speedValue(s.speed));s.water+=dt;}
// 0 means no tap; 1 preserves the normal camera tap, 2 opens settings.
inline int input(uint32_t buttons,float dt){auto& s=state();if(!s.active)return 0;bool a=buttons&1,was=s.previous&1;int tap=0;if(s.swallowA){if(!a)s.swallowA=false;s.previous=buttons;s.hold=0;return 0;}if(a){s.hold+=std::max(0.f,std::min(.2f,dt));if(s.hold>=1&&!s.modal){open();s.hold=2;}}else if(was){if(s.hold>0&&s.hold<1&&!s.modal)tap=1;s.hold=0;}s.previous=buttons;return tap;}
inline void command(const std::string& text){if(text=="r:open"){open();return;}form().command(text);}
inline std::string message(){auto& s=state();return "r:"+wfprops::snapshot(form().edit,s.active||s.selector,s.phone);}
}
#endif
