#include "runtime_property_host.hpp"
#include <hal/phonepad/phonepad.h>
#include <fstream>
#include <iterator>
#include <sstream>
#include <iostream>
#include <thread>
int main(int argc,char** argv){
 if(argc!=4)return 2;
 std::ifstream file(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;if(!registry.load(bytes.data(),bytes.size(),error))return 3;
 // Authored colour-field fixture for the generic UI tests; no gameplay consumer.
 for(auto actor:registry.editableObjects()){auto* object=registry.object(actor);wfprops::Field field;field.id=201;field.kind=0;field.show=7;field.width=4;field.maximum=0xffffff;field.key=field.label="Tint";field.initial="5801868";object->fields.push_back(field);object->values[field.id]=field.initial;}
 wfprops::Host host;host.bind(&registry);
 phonepad::Config cfg;cfg.bindAddr=0x7f000001u;cfg.port=0;cfg.pin="123456";
 std::ifstream html(argv[2]),layout(argv[3]);std::ostringstream page,json;page<<html.rdbuf();json<<layout.rdbuf();cfg.pageHtml=page.str();cfg.layoutJson=json.str();
 phonepad::Server server;server.SetCommandHandler([&](const std::string& command){host.command(command);});if(!server.Start(cfg))return 4;
 std::cout<<server.Port()<<std::endl;long long last=0;
 for(;;){auto now=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();server.Poll(now);host.phone=server.PhoneConnected();host.checkOwner();if(now-last>=50){server.SendText(host.message());last=now;}std::this_thread::sleep_for(std::chrono::milliseconds(2));}
}
