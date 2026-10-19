#include <game/plant_settings.h>
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>
int main(int argc,char** argv){
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;assert(registry.load(bytes.data(),bytes.size(),error));wfprops::host().bind(&registry);wfprops::activeRegistry()=&registry;
 auto* object=registry.schema("PlantedTankSettings");assert(object);
 uint32_t seed=0;assert(planted::parseSeed(*object->get(1),seed));bool random=object->get(7)&&*object->get(7)=="1";
 bool salt=*object->get(2)=="1";int speed=std::atoi(object->get(3)->c_str());float age=object->get(4)?std::atof(object->get(4)->c_str()):0;
 bool textures=!object->get(5)||*object->get(5)=="1",sway=!object->get(6)||*object->get(6)=="1";
 planted::enter();auto& state=planted::state();assert(state.randomEntry==random);assert(random||state.seed==seed);assert(state.salt==salt&&state.speed==speed&&state.age==age&&state.textures==textures&&state.sway==sway);
 auto generation=state.generation,geometry=state.geometryGeneration;planted::open();auto& edit=wfprops::host().form.edit;
 assert(edit.set(5,textures?"0":"1"));assert(edit.set(6,sway?"0":"1"));assert(state.textures==textures&&state.sway==sway);planted::cancel();assert(state.generation==generation);
 planted::open();assert(edit.set(5,textures?"0":"1"));assert(edit.set(6,sway?"0":"1"));assert(edit.set(3,"6"));assert(planted::apply());
 assert(state.textures!=textures&&state.sway!=sway&&state.speed==6&&state.age==age&&state.generation==generation&&state.geometryGeneration==geometry+1);
 planted::open();assert(!edit.set(4,"241"));edit.draft[4]="1";assert(!planted::apply());planted::cancel();assert(state.age==age&&state.generation==generation);
 planted::tick(.1f,0);assert(std::fabs(state.age-std::min(240.f,age+.8f))<.0001f);
 planted::open();float pausedAge=state.age;planted::tick(.1f,0);assert(state.age==pausedAge);edit.draft[7]=random?"0":"1";assert(!planted::apply());planted::cancel();assert(state.randomEntry==random);
 planted::open();assert(edit.set(1,"4294967295"));assert(edit.set(2,salt?"0":"1"));assert(planted::apply());assert(state.seed==UINT32_MAX&&state.salt!=salt&&state.age==0&&state.generation==generation+1);
 planted::leave();wfprops::host().bind(nullptr);wfprops::activeRegistry()=nullptr;std::cout<<"Plant RPRP entry, seed bounds, age, water, speed, rendering flags, Apply/Cancel, read-only timing and regeneration passed\n";
}
