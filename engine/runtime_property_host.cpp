#include "runtime_property_host.hpp"
#include <algorithm>
#include <cmath>
namespace wfprops {
Host& host(){static Host value;return value;}
void Host::bind(Registry* registry){if(registry_==registry)return;close();registry_=registry;}
bool Host::available() const {return registry_&&!registry_->editableObjects().empty();}
void Host::consumer(const std::string& schema,Consumer consumer){consumers_[schema]=std::move(consumer);}
void Host::close(){form.edit.cancel();form.action={};modal=picker=false;owners.clear();selected=0;resetPick();previous_=pickerPrevious_=0;hold_=0;swallow_=true;}
void Host::resetPick(){pick=PickMode::Off;pickCandidates.clear();pickTargets.clear();highlight=-1;highlightActor_=0;group.clear();groupSelected=0;}
void Host::suspend(){close();}
bool Host::open(uint32_t openingButtons){
    if(!available())return false;
    close();
    for(auto actor:registry_->editableObjects()){const auto* o=registry_->object(actor);owners.push_back({actor,o->generation,o->title});}
    if(owners.size()==1)return openOwner(owners[0].actor,openingButtons);
    modal=picker=true;pickerSession_=nextSession();pickerPrevious_=openingButtons;return true;
}
bool Host::openOwner(uint32_t actor,uint32_t openingButtons){
    if(!registry_)return false;
    const auto eligible=registry_->editableObjects();
    if(std::find(eligible.begin(),eligible.end(),actor)==eligible.end())return false;
    auto* object=registry_->object(actor);const auto name=object->schema;
    auto consumer=consumers_.find(name);
    if(consumer!=consumers_.end()&&consumer->second.beforeOpen)consumer->second.beforeOpen();
    if(!form.begin(*registry_,actor,openingButtons))return false;
    picker=false;resetPick();modal=true;previous_=openingButtons;hold_=0;
    form.action=[this](const std::string& action){if(action=="cancel")close();else apply(action);};
    return true;
}
void Host::checkOwner(){
    if(!modal)return;
    if(picker){for(const auto& owner:owners){auto* o=registry_?registry_->object(owner.actor):nullptr;if(!o||o->generation!=owner.generation){close();break;}}}
    else if(!form.edit.object())close();
}
bool Host::apply(const std::string& action){
    checkOwner();if(!modal||picker)return false;
    auto* object=form.edit.object();if(!object)return false;
    auto it=consumers_.find(object->schema);Consumer consumer=it==consumers_.end()?Consumer{}:it->second;
    if(!consumer.committed&&action!="apply")return false;
    if(consumer.beforeCommit&&!consumer.beforeCommit(form,action))return false;
    if(!form.edit.commit())return false;
    Object committed=*object;close();
    if(consumer.committed)consumer.committed(committed,action);
    return true;
}
bool Host::back(){
    checkOwner();
    if(picker){
        // Group -> scene -> chooser list -> closed.
        if(pick==PickMode::Group){pick=PickMode::Scene;group.clear();groupSelected=0;return true;}
        if(pick==PickMode::Scene){resetPick();selected=0;return true;}
        close();return true;
    }
    return modal&&form.back()&&apply();
}
std::vector<wfpick::Entry> Host::candidates() const {
    std::vector<wfpick::Entry> result;
    for(const auto& owner:owners)result.push_back({owner.actor,owner.title});
    return result;
}
void Host::enterPick(){
    if(!modal||!picker||owners.size()<2)return;
    resetPick();pick=PickMode::Scene;refreshPick();
}
void Host::refreshPick(){
    if(!modal||!picker||pick==PickMode::Off)return;
    pickCandidates.clear();pickTargets.clear();highlight=-1;
    wfpick::Camera camera;
    if(!world.camera||!world.locate||!world.camera(camera))return;
    for(const auto& entry:candidates()){
        wfpick::Candidate candidate;
        if(!world.locate(entry.actor,candidate))continue;
        candidate.actor=entry.actor;candidate.label=entry.label;pickCandidates.push_back(candidate);
    }
    pickTargets=wfpick::layout(camera,pickCandidates);
    // Keep the highlight on the same object while it stays in view.
    for(size_t i=0;i<pickTargets.size()&&highlight<0;++i)
        for(auto member:pickTargets[i].members)if(pickCandidates[member].actor==highlightActor_){highlight=int(i);break;}
    if(highlight<0)highlight=wfpick::nearestCentre(pickTargets,camera.width,camera.height);
    highlightActor_=highlight<0?0:pickCandidates[pickTargets[size_t(highlight)].members[0]].actor;
}
void Host::pickMove(wfpick::Direction direction){
    if(pick!=PickMode::Scene)return;
    refreshPick();highlight=wfpick::step(pickTargets,highlight,direction);
    if(highlight>=0)highlightActor_=pickCandidates[pickTargets[size_t(highlight)].members[0]].actor;
}
void Host::pickOk(){
    if(pick==PickMode::Group){if(groupSelected<group.size())openOwner(group[groupSelected]);return;}
    if(pick!=PickMode::Scene)return;
    refreshPick();if(highlight<0)return;
    const auto& members=pickTargets[size_t(highlight)].members;
    if(members.size()==1){openOwner(pickCandidates[members[0]].actor);return;}
    group.clear();for(auto member:members)group.push_back(pickCandidates[member].actor);
    std::sort(group.begin(),group.end());groupSelected=0;pick=PickMode::Group;
}
bool Host::pickHover(float x,float y){
    if(pick!=PickMode::Scene||!world.camera)return false;
    wfpick::Camera camera;wfpick::Ray ray;
    if(!world.camera(camera)||!wfpick::cursorRay(camera,x,y,ray))return false;
    refreshPick();const int hit=wfpick::rayPick(pickCandidates,ray);if(hit<0)return false;
    for(size_t i=0;i<pickTargets.size();++i)
        for(auto member:pickTargets[i].members)if(int(member)==hit){highlight=int(i);highlightActor_=pickCandidates[size_t(hit)].actor;return true;}
    return false;
}
void Host::inputPicker(uint32_t buttons){
    checkOwner();if(!modal||!picker)return;
    auto edge=buttons&~pickerPrevious_;pickerPrevious_=buttons;
    if(pick==PickMode::Scene){
        if(edge&(1u<<11))pickMove(wfpick::Up);
        if(edge&(1u<<12))pickMove(wfpick::Down);
        if(edge&(1u<<13))pickMove(wfpick::Right);
        if(edge&(1u<<14))pickMove(wfpick::Left);
        if(edge&1)pickOk();
        return;
    }
    if(pick==PickMode::Group){
        if(edge&(1u<<11))groupSelected=groupSelected?groupSelected-1:0;
        if(edge&(1u<<12)&&!group.empty())groupSelected=std::min(groupSelected+1,group.size()-1);
        if(edge&1)pickOk();
        return;
    }
    // Row 0 is Pick in 3D; rows 1..N are the owners.
    if(edge&(1u<<11))selected=selected?selected-1:0;
    if(edge&(1u<<12))selected=std::min(selected+1,owners.size());
    if(edge&1){if(selected==0)enterPick();else openOwner(owners[selected-1].actor,buttons);}
}
bool Host::gesture(uint32_t buttons,float dt){
    checkOwner();bool a=buttons&1,was=previous_&1;bool tap=false;
    if(swallow_){if(!buttons)swallow_=false;previous_=buttons;hold_=0;return false;}
    if(!modal&&available()){
        // Directional OK chords remain level controls, including baseline reset.
        if(a&&!(buttons&~1u)){if(std::isfinite(dt))hold_+=std::max(0.f,std::min(.2f,dt));if(hold_>=1){open(buttons);hold_=0;}}
        else if(!a&&was){tap=hold_>0&&hold_<1;hold_=0;}
        else hold_=0;
    }
    previous_=buttons;return tap;
}
void Host::command(const std::string& text){
    checkOwner();if(text=="r:open"){if(!modal)open();return;}
    if(!modal)return;
    if(!picker){form.command(text);return;}
    const std::string prefix="r:"+std::to_string(pickerSession_)+":";
    if(text.compare(0,prefix.size(),prefix))return;
    const auto verb=text.substr(prefix.size());
    if(verb=="cancel"||verb=="apply"){close();return;}
    if(verb=="pick"){enterPick();return;}
    if(verb=="list"){resetPick();selected=0;return;}
    if(verb=="back"){back();return;}
    if(verb=="ok"){pickOk();return;}
    if(verb.compare(0,5,"move:")==0){
        const auto d=verb.substr(5);
        if(pick==PickMode::Group){
            if(d=="up")groupSelected=groupSelected?groupSelected-1:0;
            else if(d=="down"&&!group.empty())groupSelected=std::min(groupSelected+1,group.size()-1);
            return;
        }
        if(d=="up")pickMove(wfpick::Up);else if(d=="down")pickMove(wfpick::Down);
        else if(d=="left")pickMove(wfpick::Left);else if(d=="right")pickMove(wfpick::Right);
        return;
    }
    if(verb.compare(0,7,"select:")==0){const auto id=verb.substr(7);for(const auto& owner:owners)if(id==std::to_string(owner.actor)){openOwner(owner.actor);break;}}
}
std::string Host::message() const {
    if(!picker)return "r:"+snapshot(form.edit,available(),phone);
    std::string result="r:{\"available\":true,\"open\":true,\"picker\":true,\"phone\":"+std::string(phone?"true":"false")+",\"session\":"+std::to_string(pickerSession_)+",\"title\":\"Choose an object\",\"error\":\"\",\"fields\":[],\"objects\":[";
    bool first=true;for(const auto& owner:owners){if(!first)result+=',';first=false;result+="{\"actor\":"+std::to_string(owner.actor)+",\"title\":"+json(owner.title)+"}";}
    result+="],\"pick\":\""+std::string(pick==PickMode::Scene?"scene":pick==PickMode::Group?"group":"off")+"\"";
    if(pick!=PickMode::Off){
        std::string label;
        if(highlight>=0&&size_t(highlight)<pickTargets.size()){
            const auto& members=pickTargets[size_t(highlight)].members;
            label=members.size()==1?pickCandidates[members[0]].label:std::to_string(members.size())+" objects here";
        }
        result+=",\"highlight\":"+json(label)+",\"inView\":"+std::to_string(pickTargets.size())+",\"group\":[";
        first=true;for(auto actor:group){if(!first)result+=',';first=false;std::string title;for(const auto& owner:owners)if(owner.actor==actor)title=owner.title;result+="{\"actor\":"+std::to_string(actor)+",\"title\":"+json(title)+"}";}
        result+="],\"groupSelected\":"+std::to_string(groupSelected);
    }
    return result+"}";
}
}
