// Engine state is copied here on the game thread; the I/O worker never sees a Level.
#include "debug_server.hp"
#ifdef WF_RUNTIME_DIAGNOSTICS
#include "../runtime_diagnostics.hpp"
#include "level.hp"
#include "actor.hp"
#include <physics/physicalobject.hp>
#include <game/plant_settings.h>
#include <pigsys/pigsys.hp>
#include <cstdio>
#include <algorithm>

namespace {
wfdiag::State state;
wfdiag::ActorState actorState(Level* level,Actor* actor) {
    wfdiag::ActorState result;if(!actor)return result;
    result.available=true;result.actor=actor->GetActorIndex();
    result.generation=wfdiag::ActorGeneration(actor);
    const auto& p=actor->currentPos();const auto& v=actor->GetPhysicalAttributes().LinVelocity();
    result.position={{p.X().AsFloat(),p.Y().AsFloat(),p.Z().AsFloat()}};
    result.velocity={{v.X().AsFloat(),v.Y().AsFloat(),v.Z().AsFloat()}};
    if(level){auto iter=level->GetActiveRooms().GetObjectIter(ROOM_OBJECT_LIST_UPDATE);
        for(;!iter.Empty();++iter)if(&*iter==actor){result.active=true;break;}}
    result.visible=actor->isVisible();return result;
}
wfdiag::Snapshot capture(Level* level,const wfdiag::Request& request) {
    wfdiag::Snapshot result;
    Actor* player=nullptr;
    if(level&&level->mainCharacter()&&IsActor(level->mainCharacter()))player=static_cast<Actor*>(level->mainCharacter());
    result.player=actorState(level,player);
    Actor* selected=player;
    if(request.actor) {
        if(!level||request.actor>=level->GetObjectList().Size()){result.error="actor-unavailable";return result;}
        auto* object=level->GetObjectList()[request.actor];
        if(!object||!IsActor(object)){result.error="actor-unavailable";return result;}
        selected=static_cast<Actor*>(object);
        if(wfdiag::ActorGeneration(selected)!=request.actorGeneration){result.error="stale-actor";return result;}
    }
    result.selected=actorState(level,selected);
    auto* registry=wfprops::host().registry();
    auto& edit=wfprops::host().form.edit;
    const wfprops::Object* object=nullptr;
    if(registry) {
        if(request.actor)object=registry->object(uint32_t(request.actor));
        else if(edit.open&&edit.registry==registry)object=registry->object(edit.actor);
        else if(selected)object=registry->object(uint32_t(selected->GetActorIndex()));
        if(!object&&!request.actor){auto owners=registry->editableObjects();if(!owners.empty())object=registry->object(owners.front());}
    }
    if(object) {
        auto& p=result.properties;p.available=true;p.actor=object->actor;p.generation=object->generation;
        p.revision=object->revision;p.schema=object->schema;
        p.draftOpen=edit.open&&edit.registry==registry&&edit.actor==object->actor&&edit.generation==object->generation;
        p.session=p.draftOpen?edit.session:0;p.error=p.draftOpen?edit.error:"";
        for(const auto& f:object->fields)if(f.stored()) {
            if(p.fields.size()==wfdiag::MaxFields){p.truncated=true;break;}
            wfdiag::FieldState field;field.id=f.id;field.key=f.key;
            if(const auto* value=object->get(f.id))field.committed=*value;
            if(request.draft&&p.draftOpen){auto it=edit.draft.find(f.id);if(it!=edit.draft.end())field.draft=it->second;}
            // Never silently present a truncated property value as effective state.
            if(field.committed.size()>4096||field.draft.size()>4096){result.error="field-too-large";return result;}
            p.fields.push_back(std::move(field));
        }
    }
    return result;
}
}
void DebugServer_Start(int port){
    static bool cleanupRegistered=false;
    if(port>0&&!wfdiag::Start(port))std::fprintf(stderr,"[diagnostics] loopback listener failed port=%d\n",port);
    if(!cleanupRegistered){sys_atexit([](int){wfdiag::Stop();});cleanupRegistered=true;}
}
void DebugServer_Stop(){wfdiag::Stop();}
void DebugServer_DrainQueue(Level&){}
void DebugServer_BroadcastState(Level&){}
void DebugServer_BroadcastPerf(float,int){}
void DebugServer_BroadcastMailboxes(Level&){}
bool DebugServer_IsPaused(){return false;}
bool DebugServer_GetInputOverride(int,int32_t*){return false;}
void DebugServer_DiagnosticLevel(int level){++state.levelGeneration;state.level=level;state.mode="loading";wfdiag::Boundary(state);}
void DebugServer_DiagnosticBegin(bool simulation,const char* mode,int cursor){
    ++state.frame;if(simulation)++state.step;state.mode=mode;state.cursor=cursor;
    wfdiag::Boundary(state);
}
void DebugServer_DiagnosticSimulation(){++state.step;wfdiag::Boundary(state);wfdiag::Route("game","awaiting-level-update");}
void DebugServer_DiagnosticPump(Level* level,bool suspended){
    const auto& settings=wfprops::host();state.suspended=suspended;state.paused=suspended||settings.modal||settings.waitingForRelease()||state.mode=="selector";
    state.modal=settings.modal?(settings.picker?"object-picker":settings.phone?"phone-form":settings.form.drawer?"keypad":"form"):"none";
    state.session=settings.modal?settings.session():0;
    wfdiag::Pump(state,[&](const wfdiag::Request& request){return capture(level,request);});
}
#endif
