// Serve the real controller and real plant command state for browser integration tests.
#include <game/plant_settings.h>
#include <hal/phonepad/phonepad.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
int main(int argc,char** argv){if(argc!=3)return 2;phonepad::Config cfg;cfg.bindAddr=0x7f000001u;cfg.port=0;cfg.pin="123456";std::ifstream a(argv[1]),b(argv[2]);std::ostringstream x,y;x<<a.rdbuf();y<<b.rdbuf();cfg.pageHtml=x.str();cfg.layoutJson=y.str();
phonepad::Server server;server.SetCommandHandler([](const std::string& t){planted::command(t);});if(!server.Start(cfg))return 3;planted::state().active=true;planted::regenerate(713,false);std::cout<<server.Port()<<std::endl;long long last=0;
for(;;){long long now=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();server.Poll(now);planted::state().phone=server.PhoneConnected();if(now-last>=50){server.SendText(planted::message());last=now;}std::this_thread::sleep_for(std::chrono::milliseconds(2));}}
