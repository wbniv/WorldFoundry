// Transport/lifetime harness: no renderer, Android driver or mutation API.
#include "../engine/runtime_diagnostics.hpp"
#include <iostream>
#include <sstream>
#include <poll.h>
#include <unistd.h>
int main() {
    wfdiag::State state;state.mode="game";state.level=0;state.levelGeneration=1;
    int actor=0;wfdiag::ActorCreated(&actor);bool exists=true,freeze=false;
    if(!wfdiag::Start(0))return 2;
    std::cout<<"READY "<<wfdiag::Port()<<std::endl;
    bool running=true;
    while(running) {
        pollfd input{STDIN_FILENO,POLLIN,0};poll(&input,1,5);
        if(input.revents&POLLIN) {
            std::string line;std::getline(std::cin,line);std::istringstream command(line);
            std::string op;command>>op;
            if(op=="receive") {std::string source;uint32_t mask;command>>source>>mask;wfdiag::Receive(source.c_str(),mask,0,0,1);}
            else if(op=="route")wfdiag::Route("game","pending-update");
            else if(op=="consume")wfdiag::Consume("game","level-update",0);
            else if(op=="actor-read")wfdiag::InputRead(1,wfdiag::ActorGeneration(&actor),1909);
            else if(op=="pause"){int value;command>>value;state.paused=value;}
            else if(op=="suspend"){int value;command>>value;state.suspended=value;}
            else if(op=="focus"){int value;command>>value;wfdiag::Focus(value);}
            else if(op=="level")++state.levelGeneration;
            else if(op=="delete"){wfdiag::ActorDeleted(&actor);exists=false;}
            else if(op=="create"){wfdiag::ActorCreated(&actor);exists=true;}
            else if(op=="freeze"){int value;command>>value;freeze=value;}
            else if(op=="stop")running=false;
            else if(op=="restart"){wfdiag::Stop();wfdiag::Start(0);std::cout<<"PORT "<<wfdiag::Port()<<std::endl;}
            else return 3;
            std::cout<<"OK "<<op<<std::endl;
        }
        if(!freeze) {
            ++state.frame;if(!state.paused&&!state.suspended)++state.step;
            state.clockAvailable=true;state.simulationDelta=.05f;state.simulationTime=state.step*.05f;
            wfdiag::Pump(state,[&](const wfdiag::Request& r){
                wfdiag::Snapshot s;
                if(r.actor&&(!exists||wfdiag::ActorGeneration(&actor)!=r.actorGeneration))s.error=exists?"stale-actor":"actor-unavailable";
                s.player.available=exists;s.player.actor=1;s.player.generation=wfdiag::ActorGeneration(&actor);
                s.selected=s.player;s.properties.available=true;s.properties.schema="Fixture";s.properties.actor=1;
                s.properties.revision=4;s.properties.draftOpen=true;s.properties.session=2;
                s.properties.fields.push_back({1,"seed","713","719"});return s;
            });
        }
    }
    wfdiag::Stop();wfdiag::ActorDeleted(&actor);
}
