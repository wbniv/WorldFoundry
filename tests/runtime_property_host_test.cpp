#include "runtime_property_host.hpp"
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>
#include <map>
int main(int argc,char** argv){
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;assert(registry.load(bytes.data(),bytes.size(),error));
 assert((registry.editableObjects()==std::vector<uint32_t>{11,22}));
 wfprops::Host host;host.bind(&registry);host.gesture(0,.05);
 // A directional OK chord remains a level action, even when held.
 for(int i=0;i<30;++i)host.gesture(2049,.05);assert(!host.modal);
 host.gesture(0,.05);
 for(int i=0;i<25;++i)host.gesture(1,.05);
 assert(host.modal&&host.picker&&host.owners.size()==2);
 auto pickerSession=host.session();host.inputPicker(1);assert(host.picker);
 // Row 0 is Pick in 3D; the owners follow it.
 assert(host.selected==0);host.inputPicker(0);host.inputPicker(4096);host.inputPicker(0);host.inputPicker(4096);host.inputPicker(0);host.inputPicker(1);
 assert(!host.picker&&host.form.edit.actor==22&&!host.form.drawer);
 auto session=host.session();assert(session!=pickerSession);
 host.command("r:"+std::to_string(pickerSession)+":set:40:8");
 assert(host.form.edit.draft[40]=="-3");
 host.command("r:"+std::to_string(session)+":set:40:8");assert(host.form.edit.draft[40]=="8");
 host.command("r:"+std::to_string(session)+":set:64:0.5");
 assert(host.apply());assert(*registry.object(22)->get(40)=="8"&&*registry.object(11)->get(40)=="-3");
 assert(host.waitingForRelease());host.gesture(2048,.05);assert(host.waitingForRelease());host.gesture(0,.05);assert(!host.waitingForRelease());
 assert(host.openOwner(11));host.form.edit.set(40,"13");assert(!host.apply()&&host.modal);
 host.close();assert(*registry.object(11)->get(40)=="-3");
 assert(host.openOwner(11));auto oldSession=host.session();host.form.edit.set(40,"7");host.suspend();
 assert(!host.modal);host.openOwner(22);host.command("r:"+std::to_string(oldSession)+":apply");assert(host.modal);
 // A deleted/recreated instance cannot inherit an old draft or picker selection.
 registry.remove(22);assert(registry.clone(11,22));host.checkOwner();assert(!host.modal);
 assert(host.open());registry.remove(22);host.command("r:"+std::to_string(host.session())+":select:11");assert(!host.modal);
 host.openOwner(11);assert(registry.set(11,40,"1",error));assert(!host.apply());host.close();
 assert(host.open());assert(!host.picker);host.close();host.bind(nullptr);assert(!host.available());
 // Load-time settings remain queryable without taking the level's held OK.
 wfprops::Registry readonlyRegistry=registry;
 auto* readonlyOwner=readonlyRegistry.object(11);
 for(auto& field:readonlyOwner->fields)field.readonly=1;
 wfprops::Host readonlyHost;readonlyHost.bind(&readonlyRegistry);readonlyHost.gesture(0,.05);
 assert(readonlyRegistry.editableObjects().empty()&&!readonlyHost.available());
 assert(*readonlyOwner->get(40)=="1");
 for(int i=0;i<25;++i)readonlyHost.gesture(1,.05);
 assert(!readonlyHost.modal&&!readonlyHost.open());readonlyHost.gesture(0,.05);
 // One editable field restores the gesture; other fields stay ghosted.
 for(auto& field:readonlyOwner->fields)if(field.id==40)field.readonly=0;
 assert((readonlyRegistry.editableObjects()==std::vector<uint32_t>{11}));
 for(int i=0;i<25;++i)readonlyHost.gesture(1,.05);
 assert(readonlyHost.modal&&!readonlyHost.picker);
 for(const auto& field:readonlyHost.form.edit.object()->fields)
     if(field.id!=40)assert(field.readonly);
 readonlyHost.close();readonlyHost.gesture(0,.05);
 // An enabled action is sufficient, but a ghosted action is not.
 for(auto& field:readonlyOwner->fields)field.readonly=1;
 wfprops::Field action;action.kind=9;action.key="apply";action.label="Apply";
 readonlyOwner->fields.push_back(action);
 assert(readonlyHost.available()&&readonlyHost.open());readonlyHost.close();
 readonlyOwner->fields.back().readonly=1;
 assert(!readonlyHost.available()&&!readonlyHost.open());
 // ---- Pick in 3D (docs/plans/2026-10-16-runtime-object-editing.md, Phase P)
 {
  wfprops::Registry fresh;assert(fresh.load(bytes.data(),bytes.size(),error));
  wfprops::Host pick;pick.bind(&fresh);
  std::map<uint32_t,wfpick::Vec3> where={{11,{0,0,-10}},{22,{3,0,-10}}};bool cameraOn=true;
  pick.world.camera=[&](wfpick::Camera& c){if(!cameraOn)return false;for(int i=0;i<16;++i)c.view[i]=c.proj[i]=0;c.view[0]=c.view[5]=c.view[10]=c.view[15]=1;
   const float f=1.732f,n=.1f,far=100;c.proj[0]=f*9/16;c.proj[5]=f;c.proj[10]=(far+n)/(n-far);c.proj[11]=-1;c.proj[14]=2*far*n/(n-far);return true;};
  pick.world.locate=[&](uint32_t actor,wfpick::Candidate& c){auto it=where.find(actor);if(it==where.end())return false;c.position=it->second;return true;};
  auto press=[&](uint32_t b){pick.inputPicker(0);pick.inputPicker(b);pick.inputPicker(0);};
  // The interface the redesign swaps: (actor id, label) per chooser object.
  assert(pick.open()&&pick.picker&&pick.selected==0);
  auto entries=pick.candidates();assert(entries.size()==2&&entries[0].actor==11&&entries[1].actor==22&&!entries[0].label.empty());
  press(1);assert(pick.pick==wfprops::PickMode::Scene&&pick.pickTargets.size()==2);
  // First highlight: nearest the screen centre (actor 11 sits on it).
  assert(pick.pickCandidates[pick.pickTargets[size_t(pick.highlight)].members[0]].actor==11);
  assert(pick.message().find("\"pick\":\"scene\"")!=std::string::npos);
  press(1u<<14);assert(pick.pickCandidates[pick.pickTargets[size_t(pick.highlight)].members[0]].actor==11); // nothing to the left
  press(1u<<13);assert(pick.pickCandidates[pick.pickTargets[size_t(pick.highlight)].members[0]].actor==22);
  pick.refreshPick();assert(pick.pickCandidates[pick.pickTargets[size_t(pick.highlight)].members[0]].actor==22); // stable per frame
  press(1);assert(!pick.picker&&pick.pick==wfprops::PickMode::Off&&pick.form.edit.actor==22);
  pick.close();
  // Back: scene -> chooser list -> closed.
  assert(pick.open());press(1);assert(pick.pick==wfprops::PickMode::Scene);
  assert(pick.back()&&pick.modal&&pick.picker&&pick.pick==wfprops::PickMode::Off&&pick.selected==0);
  assert(pick.back()&&!pick.modal);
  // Same spot: one bracket, "2 objects here"; OK opens a short list of just those.
  where[22]={0,0,-10};assert(pick.open());press(1);
  assert(pick.pickTargets.size()==1&&pick.pickTargets[0].members.size()==2&&pick.pickTargets[0].gear);
  assert(pick.message().find("2 objects here")!=std::string::npos);
  press(1);assert(pick.pick==wfprops::PickMode::Group&&(pick.group==std::vector<uint32_t>{11,22})&&pick.groupSelected==0);
  assert(pick.back()&&pick.pick==wfprops::PickMode::Scene);press(1);assert(pick.pick==wfprops::PickMode::Group);
  press(4096);assert(pick.groupSelected==1);press(1);assert(!pick.picker&&pick.form.edit.actor==22);pick.close();
  // Nothing in view (behind the camera, or no camera): OK does nothing, Back returns to the list.
  where[11]={0,0,5};where[22]={0,0,6};assert(pick.open());press(1);
  assert(pick.pick==wfprops::PickMode::Scene&&pick.pickTargets.empty()&&pick.highlight==-1);
  press(1);press(1u<<13);assert(pick.modal&&pick.picker&&pick.pick==wfprops::PickMode::Scene);
  assert(pick.back()&&pick.pick==wfprops::PickMode::Off&&pick.modal);pick.close();
  cameraOn=false;where[11]={0,0,-10};assert(pick.open());press(1);assert(pick.pickTargets.empty());pick.close();cameraOn=true;
  // Phone: Pick in 3D, the D-pad, OK and List drive the same state.
  where[22]={3,0,-10};assert(pick.open());const std::string prefix="r:"+std::to_string(pick.session())+":";
  pick.command(prefix+"pick");assert(pick.pick==wfprops::PickMode::Scene);
  pick.command(prefix+"move:right");assert(pick.pickCandidates[pick.pickTargets[size_t(pick.highlight)].members[0]].actor==22);
  assert(pick.message().find("\"highlight\":")!=std::string::npos);
  pick.command(prefix+"list");assert(pick.pick==wfprops::PickMode::Off&&pick.picker);
  pick.command(prefix+"pick");pick.command(prefix+"ok");assert(!pick.picker&&pick.form.edit.actor==11);pick.close();
 }
 std::cout<<"Generic host: selection, isolation, input release, stale sessions, deletion, revision, teardown and Pick in 3D passed\n";
}
