#include "runtime_property_host.hpp"
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>
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
 host.inputPicker(0);host.inputPicker(4096);host.inputPicker(0);host.inputPicker(1);
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
 std::cout<<"Generic host: selection, isolation, input release, stale sessions, deletion, revision and teardown passed\n";
}
