// Serve the real controller and real plant command state for browser integration tests.
#include <game/plant_settings.h>
#include <hal/phonepad/phonepad.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
int main(int argc,char** argv){if(argc!=3&&argc!=4)return 2;bool controls=argc==4;phonepad::Config cfg;cfg.bindAddr=0x7f000001u;cfg.port=0;cfg.pin="123456";std::ifstream a(argv[1]),b(argv[2]);std::ostringstream x,y;x<<a.rdbuf();y<<b.rdbuf();cfg.pageHtml=x.str();cfg.layoutJson=y.str();
wfprops::Form generic;auto& registry=planted::previewProperties();auto* owner=registry.schema("PlantedTankSettings");
if(controls){owner->title="Generic control fixtures";owner->fields.clear();owner->values.clear();
wfprops::Field color;color.id=201;color.kind=0;color.show=7;color.width=4;color.maximum=0xffffff;color.key="Tint";color.label="Tint";color.initial="5801868";owner->fields.push_back(color);owner->values[color.id]=color.initial;
wfprops::Field name;name.id=202;name.kind=3;name.maxLength=32;name.key="Name";name.label="Name";name.initial="River garden";owner->fields.push_back(name);owner->values[name.id]=name.initial;
color.id=203;color.readonly=1;color.key="LockedTint";color.label="Locked tint";owner->fields.push_back(color);owner->values[color.id]=color.initial;
name.id=204;name.readonly=1;name.key="LockedName";name.label="Locked name";owner->fields.push_back(name);owner->values[name.id]=name.initial;
name.id=205;name.readonly=0;name.rule=2;name.maxLength=4096;name.key="Notes";name.label="Notes";name.initial="First line\nSecond line";owner->fields.push_back(name);owner->values[name.id]=name.initial;
generic.action=[&](const std::string& action){if(action=="apply")generic.edit.commit();else if(action=="cancel")generic.edit.cancel();};}
phonepad::Server server;server.SetCommandHandler([&](const std::string& t){if(!controls)planted::command(t);else if(t=="r:open")generic.begin(registry,owner->actor);else generic.command(t);});if(!server.Start(cfg))return 3;planted::state().active=true;if(!controls){planted::regenerate(713,false);planted::registerSettings();wfprops::host().bind(&planted::properties());}std::cout<<server.Port()<<std::endl;long long last=0;
for(;;){long long now=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();server.Poll(now);wfprops::host().phone=server.PhoneConnected();if(now-last>=50){server.SendText(controls?"r:"+wfprops::snapshot(generic.edit,true,server.PhoneConnected()):planted::message());last=now;}std::this_thread::sleep_for(std::chrono::milliseconds(2));}}
