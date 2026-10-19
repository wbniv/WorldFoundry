#ifndef WF_PLANT_SETTINGS_H
#define WF_PLANT_SETTINGS_H
#include <game/plant_growth.h>
#include "../../../engine/runtime_property_host.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
namespace planted {
struct State {
 bool active=false,salt=false,pending=false,selector=false,sway=true;
 uint32_t seed=0;int speed=3;float age=0,water=0;
 std::array<int,8> actors{};std::vector<plantgrowth::Shoot> shoots;std::array<plantgrowth::Chunk,8> chunks;
 float initialAge=0;bool textures=true,randomEntry=true;
 // Render flag changes refresh cached meshes without regenerating growth.
 unsigned generation=0,geometryGeneration=0; bool explicitSeed=false;unsigned topologySlot=0;
};
inline State& state(){static State s;return s;}
inline float speedValue(int i){constexpr float v[]={0,.25f,.5f,1,2,4,8};return v[std::max(0,std::min(6,i))];}
inline const char* speedLabel(int i){const char* v[]={"Paused","0.25x","0.5x","1x","2x","4x","8x"};return v[std::max(0,std::min(6,i))];}
inline uint32_t freshSeed(){static uint32_t serial=0;uint64_t t=std::chrono::steady_clock::now().time_since_epoch().count();plantgrowth::Random r(uint32_t(t)^uint32_t(t>>32)^++serial);return r.next();}
inline bool parseSeed(const std::string& v,uint32_t& result){if(v.empty()||v.size()>10||v.find_first_not_of("0123456789")!=std::string::npos)return false;uint64_t n=0;for(char c:v){n=n*10+unsigned(c-'0');if(n>UINT32_MAX)return false;}result=uint32_t(n);return true;}
inline void regenerate(uint32_t seed,bool salt){auto& s=state();s.seed=seed;s.salt=salt;s.age=s.water=0;auto started=std::chrono::steady_clock::now();s.shoots=plantgrowth::colonies(seed,salt);auto graphDone=std::chrono::steady_clock::now();s.chunks=plantgrowth::meshes(seed,salt,s.shoots);auto meshDone=std::chrono::steady_clock::now();s.topologySlot=0;s.generation++;s.geometryGeneration++;s.pending=false;std::fprintf(stderr,"PLANTS generation=%u seed=%u mode=%s shoots=%zu vertices=",s.generation,seed,salt?"saltwater":"freshwater",s.shoots.size());size_t verts=0,faces=0;for(const auto& c:s.chunks){verts+=c.vertices.size();faces+=c.faces.size();}std::fprintf(stderr,"%zu triangles=%zu graph_ms=%.3f mesh_ms=%.3f\n",verts,faces,std::chrono::duration<double,std::milli>(graphDone-started).count(),std::chrono::duration<double,std::milli>(meshDone-graphDone).count());}
inline void syncProperties();
inline void registerSettings();
inline void enter(){
 auto& s=state();const bool selected=s.explicitSeed;s.active=true;s.selector=false;
 auto* registry=wfprops::activeRegistry();auto* object=registry?registry->schema("PlantedTankSettings"):nullptr;
 auto value=[&](unsigned id,const std::string& fallback){auto* v=object?object->get(id):nullptr;return v?*v:fallback;};
 if(!selected){
  s.randomEntry=value(7,"1")!="0";uint32_t authored=0;
  s.seed=!s.randomEntry&&parseSeed(value(1,"0"),authored)?authored:freshSeed();
  s.salt=value(2,"0")=="1";s.speed=std::max(0,std::min(6,std::atoi(value(3,"3").c_str())));
  auto age=value(4,"0");char* end=nullptr;double parsed=std::strtod(age.c_str(),&end);
  s.initialAge=end&&end!=age.c_str()&&!*end&&std::isfinite(parsed)&&parsed>=0&&parsed<=240?float(parsed):0;
  s.textures=value(5,"1")!="0";s.sway=value(6,"1")!="0";
 }
 s.explicitSeed=false;regenerate(s.seed,s.salt);s.age=s.initialAge;
 std::fprintf(stderr,"PLANTS settings-source=%s seed=%u water=%s age=%.6g speed=%d textures=%d sway=%d random_entry=%d selector_override=%d\n",object?"RPRP":"legacy-defaults",s.seed,s.salt?"saltwater":"freshwater",s.age,s.speed,int(s.textures),int(s.sway),int(s.randomEntry),int(selected));
 syncProperties();registerSettings();
}
inline wfprops::Form& form();
inline void leave(){wfprops::host().close();auto& s=state();s.active=s.selector=false;s.actors.fill(0);s.shoots.clear();for(auto& c:s.chunks){plantgrowth::Chunk empty;c=std::move(empty);}}
inline wfprops::Form& form(){return wfprops::host().form;}
inline wfprops::Registry& previewProperties(){static wfprops::Registry registry;static bool loaded=false;if(!loaded){const uint8_t bytes[]={
#include "../../../wflevels/aquarium_plants/settings-catalog.inc"
};std::string error;loaded=registry.load(bytes,sizeof(bytes),error);}return registry;}
inline wfprops::Registry& properties(){auto* r=wfprops::activeRegistry();return state().active&&r&&r->schema("PlantedTankSettings")?*r:previewProperties();}
inline void syncProperties(){auto& s=state();auto& r=properties();auto* o=r.schema("PlantedTankSettings");if(!o)return;std::string error;r.set(o->actor,1,std::to_string(s.seed),error);r.set(o->actor,2,s.salt?"1":"0",error);r.set(o->actor,3,std::to_string(s.speed),error);if(o->field(5))r.set(o->actor,5,s.textures?"1":"0",error);if(o->field(6))r.set(o->actor,6,s.sway?"1":"0",error);}
// Simulation callbacks consume committed values; the shared host owns drafts/UI.
inline void registerSettings(){
 wfprops::Consumer consumer;
 consumer.beforeOpen=[](){syncProperties();};
 consumer.beforeCommit=[](wfprops::Form& editor,const std::string& action){
  if(action!="apply"&&action!="regenerate"&&action!="random-seed")return false;
  if(auto* object=editor.edit.object())for(const auto& field:object->fields)if(field.stored()&&field.readonly){
   auto draft=editor.edit.draft.find(field.id);auto* original=object->get(field.id);
   if(!original||draft==editor.edit.draft.end()||draft->second!=*original){editor.edit.error="Plant entry settings are read-only";return false;}
  }
  return action!="random-seed"||editor.edit.set(1,std::to_string(freshSeed()));
 };
 consumer.committed=[](const wfprops::Object& object,const std::string& action){
  auto& s=state();uint32_t seed=0;parseSeed(*object.get(1),seed);
  bool salt=*object.get(2)=="1";int speed=std::atoi(object.get(3)->c_str());
  bool changed=seed!=s.seed||salt!=s.salt;bool force=action!="apply";s.speed=speed;
  bool textures=s.textures,sway=s.sway;
  if(auto* v=object.get(5))textures=*v=="1";
  if(auto* v=object.get(6))sway=*v=="1";
  if(textures!=s.textures||sway!=s.sway)++s.geometryGeneration;
  s.textures=textures;s.sway=sway;
  if(s.selector){if(auto* v=object.get(4))s.initialAge=float(std::atof(v->c_str()));if(auto* v=object.get(7))s.randomEntry=*v=="1";}
  if(s.selector){s.seed=seed;s.salt=salt;s.explicitSeed=true;s.pending=force;}
  else if(force||changed)regenerate(seed,salt);
 };
 wfprops::host().consumer("PlantedTankSettings",std::move(consumer));
}
inline void open(uint32_t openingButtons=0){
 auto& s=state();if(!s.active&&!s.selector)return;registerSettings();
 auto& registry=properties();wfprops::host().bind(&registry);
 if(auto* object=registry.schema("PlantedTankSettings"))wfprops::host().openOwner(object->actor,openingButtons);
}
inline void cancel(){wfprops::host().close();}
inline bool submit(bool random=false,bool /*speedOnly*/=false){return wfprops::host().apply(random?"random-seed":"regenerate");}
inline bool apply(){return wfprops::host().back();}
inline void tick(float dt,float /*phase*/){auto& s=state();if(!s.active||wfprops::host().modal||!std::isfinite(dt))return;dt=dt>.2f?0:std::max(0.f,dt);s.age=std::min(240.f,s.age+dt*speedValue(s.speed));s.water+=dt;}
// Compatibility entry points for level consumers and portable tests.
inline int input(uint32_t buttons,float dt){return state().active&&wfprops::host().gesture(buttons,dt)?1:0;}
inline void command(const std::string& text){if(text=="r:open"){open();return;}wfprops::host().command(text);}
inline std::string message(){return wfprops::host().message();}
}
#endif
