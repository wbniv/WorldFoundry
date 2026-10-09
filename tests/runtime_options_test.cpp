#include "runtime_options.hpp"
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>
int main(int argc,char** argv){
 assert(argc==2);std::ifstream input(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)),{});
 wfprops::Registry r;std::string error;assert(r.load(bytes.data(),bytes.size(),error));auto& host=wfprops::host();host.bind(&r);
 wfoptions::Snapshot globals={{"runtime_show_fps",{"1",true,"FPS overlay"}},{"runtime_fixed_clock",{"0",true,"Clock"}},{"runtime_clock_hz",{"20",true,"Rate"}},{"runtime_frame_profile",{"0",true,"Enable only"}},{"runtime_script_profile",{"0",false,"Backend unavailable"}},{"runtime_static_mesh",{"On",false,"Cached"}}};
 int applied=0,prepared=0;bool preparationFails=false;
 wfoptions::install(r,{[&](){return globals;},[&](const wfoptions::Changes&,std::string& err){++prepared;if(preparationFails){err="prepare failed";return false;}return true;},[&](const wfoptions::Changes& changes){++applied;for(auto& change:changes)globals[change.first].value=change.second;}});
 assert(*r.object(11)->get(1000)=="1"&&*r.object(22)->get(1005)=="On");
 assert(!r.set(11,1005,"Off",error));assert(!r.set(11,1004,"1",error));
 assert(host.openOwner(11));assert(host.form.edit.set(1000,"0"));assert(globals["runtime_show_fps"].value=="1");host.suspend();assert(applied==0);
 assert(host.openOwner(11));assert(host.form.edit.set(1000,"0"));assert(host.form.edit.set(40,"5"));assert(host.apply());
 assert(applied==1&&prepared==1&&globals["runtime_show_fps"].value=="0");assert(*r.object(11)->get(1000)=="0"&&*r.object(22)->get(1000)=="0");assert(*r.object(11)->get(40)=="5"&&*r.object(22)->get(40)=="-3");
 assert(host.openOwner(22));assert(host.apply());assert(applied==1&&prepared==1);
 assert(host.openOwner(11));host.form.edit.draft[1005]="Off";assert(!host.apply());host.close();assert(globals["runtime_static_mesh"].value=="On");
 assert(host.openOwner(22));assert(host.form.edit.set(1000,"1"));globals["runtime_clock_hz"].value="30";assert(!host.apply());host.close();assert(applied==1);
 assert(host.openOwner(22));for(const auto* bad:{"0","-1","1001","nan","inf"}){host.form.edit.set(1002,bad);assert(!host.apply());}host.close();
 assert(host.openOwner(11));assert(*r.object(22)->get(1002)=="30");assert(host.form.edit.set(1000,"1"));preparationFails=true;assert(!host.apply());assert(globals["runtime_show_fps"].value=="0"&&*r.object(11)->get(1000)=="0");host.close();
 assert(host.openOwner(11));auto stale=host.session();host.close();assert(host.openOwner(22));host.command("r:"+std::to_string(stale)+":set:1000:1");assert(host.form.edit.draft[1000]=="0");
 host.close();preparationFails=false;
 globals["runtime_clock_hz"].value="2000";
 assert(host.openOwner(11));assert(host.form.edit.object()->field(1002)->readonly);assert(*host.form.edit.object()->get(1002)=="2000");
 assert(host.form.edit.set(40,"6"));assert(host.apply());
 globals["runtime_clock_hz"].value="20";
 assert(host.openOwner(22));assert(!host.form.edit.object()->field(1002)->readonly);assert(host.form.edit.object()->field(1002)->kind==0);host.close();
 auto revision=r.object(22)->revision;assert(host.openOwner(22));assert(r.object(22)->revision==revision);
 host.close();host.bind(nullptr);std::cout<<"Runtime options: Apply/Cancel, two-owner synchronization, sample isolation, read-only enforcement, stale globals/session, bounds, unchanged Apply and failed preparation passed\n";
}
