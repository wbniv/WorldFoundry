// The Seahorses sheet (fields 8 and 9) round-trips through the planted tank's settings host:
// Apply commits every field generically (Edit::commit), so the Director's `8 property@` /
// `9 property@` see the new values, although planted::registerSettings' committed callback
// only interprets fields 1-7. docs/plans/2026-10-16-saltwater-seahorses.md, Phase 3 (Settings).
#include <game/plant_settings.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"FAIL %s:%d %s\n",__FILE__,__LINE__,#x);std::exit(1);}}while(0)
// What scripting_zforth.cc's property@ (syscall 178) returns for a field: (value, ok).
static double propertyAt(const wfprops::Object& o,unsigned id,bool& ok){
 const auto* d=o.field(id);const auto* v=o.get(id);ok=d&&v;if(!ok)return 0;
 if(d->kind<3)return std::strtod(v->c_str(),nullptr);
 if(d->kind==4)return *v=="1"?1:0;
 ok=false;return 0;
}
int main(){
 auto& registry=planted::previewProperties();
 auto* o=registry.schema("PlantedTankSettings");CHECK(o);
 CHECK(o->field(8)&&o->field(9));
 bool ok=false;
 CHECK(propertyAt(*o,8,ok)==2&&ok);                      // default 2 pairs
 CHECK(propertyAt(*o,9,ok)==1&&ok);                      // greeting on
 auto& s=planted::state();s.active=true;planted::regenerate(713,true);
 planted::syncProperties();planted::registerSettings();wfprops::host().bind(&registry);
 const auto seed=*o->get(1);
 // Each count, through the host's Apply and through the TV form's Back-applies path.
 for(int count:{0,1,2}){
  for(int path=0;path<2;++path){
   CHECK(wfprops::host().openOwner(o->actor));
   CHECK(wfprops::host().form.edit.set(8,std::to_string(count)));
   CHECK(wfprops::host().form.edit.set(9,count==1?"0":"1"));
   CHECK(path==0?wfprops::host().apply():planted::apply());
   CHECK(!wfprops::host().modal);
   CHECK(propertyAt(*o,8,ok)==count&&ok);
   CHECK(propertyAt(*o,9,ok)==(count==1?0:1)&&ok);
   CHECK(*o->get(1)==seed&&s.salt);                       // the plant fields are untouched
  }
 }
 // A plant-only Apply keeps the seahorse fields.
 CHECK(wfprops::host().openOwner(o->actor));
 CHECK(wfprops::host().form.edit.set(3,"5"));
 CHECK(wfprops::host().apply());
 CHECK(s.speed==5&&propertyAt(*o,8,ok)==2&&propertyAt(*o,9,ok)==1);
 // Out-of-range counts are refused, not committed.
 CHECK(wfprops::host().openOwner(o->actor));
 bool refused=!wfprops::host().form.edit.set(8,"3")||!wfprops::host().apply();
 CHECK(refused&&propertyAt(*o,8,ok)==2);
 wfprops::host().close();
 std::printf("seahorse settings round-trip ok\n");
 return 0;
}
