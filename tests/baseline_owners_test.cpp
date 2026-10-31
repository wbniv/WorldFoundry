// The baseline's two settings owners through the real registry, host and runtime-options
// consumer (docs/plans/2026-10-31-baseline-settings-cleanup.md, Risks). Driven by
// tests/test_baseline_field_types.py with the RP01 payload cooked into the built level.
// Usage: baseline-owners <payload> <field-types actor> <runtime-settings actor>
// Prints one "field" line per stored field (registry values after load), then asserts.
#include "runtime_options.hpp"
#include <cassert>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
int main(int argc,char** argv){
 assert(argc==4);std::ifstream input(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)),{});
 const uint32_t types=uint32_t(std::atoi(argv[2])),runtime=uint32_t(std::atoi(argv[3]));
 wfprops::Registry r;std::string error;
 // Every authored initial value passes the engine's own validation, or load fails.
 if(!r.load(bytes.data(),bytes.size(),error)){std::cout<<"load-failed "<<error<<"\n";return 1;}
 for(uint32_t actor:{types,runtime}){
  const auto* o=r.object(actor);assert(o);
  std::cout<<"object "<<actor<<" "<<o->schema<<" fields="<<o->fields.size()<<" title="<<o->title<<"\n";
  for(const auto& f:o->fields)
   std::cout<<"field "<<actor<<" "<<f.id<<" kind="<<int(f.kind)<<" show="<<int(f.show)<<" readonly="<<int(f.readonly)
            <<" key="<<f.key<<" value="<<wfprops::json(o->get(f.id)?*o->get(f.id):"")<<"\n";
 }
 // Both owners reach the chooser: each has an editable field at load.
 assert((r.editableObjects()==std::vector<uint32_t>{types,runtime}));
 std::cout<<"editable "<<types<<" "<<runtime<<"\n";
 // The process-wide runtime values reach the single Runtime settings owner: the consumer
 // installs on it and sync replaces authored values with the backend's effective ones.
 wfoptions::Snapshot globals={{"runtime_show_fps",{"0",true,"FPS overlay"}},{"runtime_fixed_clock",{"1",true,"Clock"}},{"runtime_clock_hz",{"30",true,"Rate"}}};
 int applied=0;
 wfoptions::install(r,{[&](){return globals;},[&](const wfoptions::Changes&,std::string&){return true;},
  [&](const wfoptions::Changes& changes){++applied;for(const auto& c:changes)globals[c.first].value=c.second;}});
 const auto* rs=r.object(runtime);
 assert(*rs->get(1000)=="0"&&*rs->get(1001)=="1"&&*rs->get(1002)=="30");
 assert(!rs->field(1000)->readonly&&!rs->field(1002)->readonly);
 assert(*rs->get(1005)=="unavailable"&&rs->field(1005)->readonly);  // no accessor: read-only
 assert(rs->field(2000)->readonly);                                  // Level Memory stays read-only
 std::cout<<"runtime-sync 1000="<<*rs->get(1000)<<" 1001="<<*rs->get(1001)<<" 1002="<<*rs->get(1002)<<"\n";
 auto& host=wfprops::host();host.bind(&r);
 // Apply on Runtime settings goes through the backend.
 assert(host.openOwner(runtime));assert(host.form.edit.set(1000,"1"));assert(host.apply());
 assert(applied==1&&globals["runtime_show_fps"].value=="1"&&*r.object(runtime)->get(1000)=="1");
 // Field types is a different schema: the runtime consumer never touches it.
 assert(host.openOwner(types));const std::string before=*r.object(types)->get(1);
 assert(host.form.edit.set(1,"8"));
 // The action row has no consumer: the form's action callback reaches Host::apply, which
 // returns false for an unregistered action, so nothing commits and the form stays open.
 const wfprops::Field* action=nullptr;for(const auto& f:r.object(types)->fields)if(f.kind==9)action=&f;
 assert(action&&action->key=="action");
 host.form.action(action->key);
 assert(host.modal&&host.form.edit.open&&*r.object(types)->get(1)==before&&host.form.edit.draft[1]=="8");
 std::cout<<"action-inert key="<<action->key<<" committed="<<*r.object(types)->get(1)<<" draft="<<host.form.edit.draft[1]<<"\n";
 // Apply on Field types commits its draft without the runtime backend.
 assert(host.apply()&&*r.object(types)->get(1)=="8"&&applied==1);
 std::cout<<"field-types-apply 1="<<*r.object(types)->get(1)<<" runtime-applies="<<applied<<"\n";
 host.bind(nullptr);std::cout<<"Baseline owners: load, both editable, runtime sync on one owner, inert action, isolated Apply passed\n";
}
