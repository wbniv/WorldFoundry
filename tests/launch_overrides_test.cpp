// wfprops::LaunchOverrides (docs/plans/2026-10-21-planted-tank-screensaver.md, Phase 2c).
// Built and run by `task test-launch-overrides` in wf-linux-test:local.
#undef NDEBUG  // the checks below carry side effects
#include "runtime_properties.hpp"
#include <cassert>
#include <cstdio>
#include <thread>
namespace {
struct Writer {
    std::vector<uint8_t> bytes;
    void number(uint32_t n){for(int i=0;i<4;++i)bytes.push_back(uint8_t(n>>(8*i)));}
    void byte(uint8_t b){bytes.push_back(b);}
    void text(const std::string& s){number(uint32_t(s.size()));bytes.insert(bytes.end(),s.begin(),s.end());}
    void field(uint32_t id,uint8_t kind,uint8_t readonly,uint8_t rule,int32_t lo,int32_t hi,uint32_t width,uint32_t maxLength,const std::string& key,const std::string& initial){
        number(id);byte(kind);byte(0);byte(readonly);byte(rule);number(uint32_t(lo));number(uint32_t(hi));number(0);number(width);number(maxLength);
        text(key);text(key);text("");text("");text("");text(initial);}
    void plants(uint32_t actor){
        number(actor);text("PlantedTankSettings");text("Planted tank");number(3);
        field(1,3,0,1,0,0,0,10,"Seed","0");                 // uint32 decimal seed
        field(3,0,0,0,0,6,4,0,"Growth speed","0");          // int 0..6
        field(4,0,1,0,0,240,4,0,"Initial age","0");         // read-only int 0..240
    }
};
std::vector<uint8_t> catalog(){
    Writer w;w.bytes={'R','P','0','1'};w.number(3);w.plants(1);w.plants(2);
    // A second schema with a same-named field: overrides must not cross schemas.
    w.number(3);w.text("OtherSettings");w.text("Other");w.number(1);w.field(1,3,0,1,0,0,0,10,"Seed","0");
    return w.bytes;
}
void load(wfprops::Registry& r){auto b=catalog();std::string error;bool ok=r.load(b.data(),b.size(),error);if(!ok)std::fprintf(stderr,"load: %s\n",error.c_str());assert(ok);}
const std::string& value(wfprops::Registry& r,uint32_t actor,uint32_t id){return *r.object(actor)->get(id);}
}
int main(){
    wfprops::Registry r;load(r);std::string error;
    wfprops::LaunchOverrides o;assert(o.applications()==0);
    // Empty table: nothing changes, nothing reported, still one application.
    assert(o.apply(r).empty());assert(o.applications()==1);
    assert(value(r,1,1)=="0"&&r.object(1)->revision==0&&r.object(3)->revision==0);
    // Matching objects (both instances of the schema) take the value; the other schema does not.
    o.set("PlantedTankSettings","Seed","123");o.set("PlantedTankSettings","Growth speed","5");
    assert(o.apply(r).empty());assert(o.applications()==2);
    for(uint32_t a:{1u,2u}){assert(value(r,a,1)=="123"&&value(r,a,3)=="5"&&r.object(a)->revision==2);}
    assert(value(r,3,1)=="0"&&r.object(3)->revision==0);
    // Re-applying identical values does not bump the revision.
    assert(o.apply(r).empty());assert(r.object(1)->revision==2);
    // A value that fails validation is reported and leaves the old value.
    o.set("PlantedTankSettings","Growth speed","9");
    auto rejected=o.apply(r);assert(rejected.size()==1);
    std::printf("rejected: %s\n",rejected[0].c_str());
    assert(rejected[0]==std::string("PlantedTankSettings.Growth speed=9: ")+wfprops::validationMessage(2));
    assert(value(r,1,3)=="5"&&value(r,2,3)=="5");
    o.set("PlantedTankSettings","Seed","4294967296");rejected=o.apply(r);assert(rejected.size()==2&&value(r,1,1)=="123");
    o.set("PlantedTankSettings","Seed","123");o.set("PlantedTankSettings","Growth speed","5");
    // Read-only fields accept an override; ordinary edits stay refused.
    o.set("PlantedTankSettings","Initial age","150");assert(o.apply(r).empty());
    assert(value(r,1,4)=="150"&&value(r,2,4)=="150");assert(!r.set(1,4,"10",error)&&value(r,1,4)=="150");
    // A schema the level lacks is skipped silently; an unknown key on a present schema is reported.
    o.set("NoSuchSchema","Seed","1");assert(o.apply(r).empty());
    o.set("PlantedTankSettings","Bogus","1");rejected=o.apply(r);
    assert(rejected.size()==1&&rejected[0]=="PlantedTankSettings.Bogus=1: no such field");
    o.erase("PlantedTankSettings","Bogus");assert(o.apply(r).empty());
    // A second Registry::load (the next level) starts from cooked values; apply restores the overrides.
    load(r);assert(value(r,1,1)=="0"&&value(r,1,4)=="0");
    uint64_t before=o.applications();assert(o.apply(r).empty());assert(o.applications()==before+1);
    for(uint32_t a:{1u,2u}){assert(value(r,a,1)=="123"&&value(r,a,3)=="5"&&value(r,a,4)=="150");}
    // erase removes one override; clear removes all.
    o.erase("PlantedTankSettings","Seed");load(r);o.apply(r);assert(value(r,1,1)=="0"&&value(r,1,3)=="5");
    o.clear();load(r);assert(o.apply(r).empty());assert(value(r,1,3)=="0"&&value(r,1,4)=="0"&&r.object(1)->revision==0);
    // The process-wide table is one instance.
    assert(&wfprops::launchOverrides()==&wfprops::launchOverrides());
    // Thread-safety smoke test: two host threads write while the game thread applies.
    {
        wfprops::LaunchOverrides t;uint64_t start=t.applications();
        auto writer=[&t](const char* key,int span){for(int i=0;i<20000;++i){t.set("PlantedTankSettings",key,std::to_string(i%span));if(i%97==0)t.erase("PlantedTankSettings","Bogus");}};
        std::thread a(writer,"Seed",1000),b(writer,"Growth speed",7);
        for(int i=0;i<2000;++i){load(r);assert(t.apply(r).empty());}
        a.join();b.join();assert(t.applications()==start+2000);
        t.set("PlantedTankSettings","Seed","42");load(r);assert(t.apply(r).empty()&&value(r,2,1)=="42");
    }
    std::printf("launch_overrides_test: PASS\n");
    return 0;
}
