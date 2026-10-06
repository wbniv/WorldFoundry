#include "runtime_property_host.hpp"
#include <algorithm>
#include <cmath>
namespace wfprops {
Host& host(){static Host value;return value;}
void Host::bind(Registry* registry){if(registry_==registry)return;close();registry_=registry;}
bool Host::available() const {return registry_&&!registry_->editableObjects().empty();}
void Host::consumer(const std::string& schema,Consumer consumer){consumers_[schema]=std::move(consumer);}
void Host::close(){form.edit.cancel();form.action={};modal=picker=false;owners.clear();selected=0;previous_=pickerPrevious_=0;hold_=0;swallow_=true;}
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
    picker=false;modal=true;previous_=openingButtons;hold_=0;
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
bool Host::back(){checkOwner();if(picker){close();return true;}return modal&&form.back()&&apply();}
void Host::inputPicker(uint32_t buttons){
    checkOwner();if(!modal||!picker)return;
    auto edge=buttons&~pickerPrevious_;pickerPrevious_=buttons;
    if(edge&(1u<<11))selected=selected?selected-1:0;
    if(edge&(1u<<12))selected=std::min(selected+1,owners.size()-1);
    if(edge&1)openOwner(owners[selected].actor,buttons);
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
    if(verb.compare(0,7,"select:")==0){const auto id=verb.substr(7);for(const auto& owner:owners)if(id==std::to_string(owner.actor)){openOwner(owner.actor);break;}}
}
std::string Host::message() const {
    if(!picker)return "r:"+snapshot(form.edit,available(),phone);
    std::string result="r:{\"available\":true,\"open\":true,\"picker\":true,\"phone\":"+std::string(phone?"true":"false")+",\"session\":"+std::to_string(pickerSession_)+",\"title\":\"Choose an object\",\"error\":\"\",\"fields\":[],\"objects\":[";
    bool first=true;for(const auto& owner:owners){if(!first)result+=',';first=false;result+="{\"actor\":"+std::to_string(owner.actor)+",\"title\":"+json(owner.title)+"}";}
    return result+"]}";
}
}
