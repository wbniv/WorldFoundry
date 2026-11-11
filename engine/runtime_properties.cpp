#include "runtime_properties.hpp"
#include "runtime_property_presentation.hpp"
#include <algorithm>
#include <limits>

extern "C" int wf_attr_check(uint32_t,int32_t,int32_t,uint32_t,uint32_t,uint32_t,uint32_t,const uint8_t*,size_t,const uint8_t*,size_t);
namespace wfprops {
const Field* Object::field(uint32_t id) const {for(const auto& f:fields)if(f.id==id&&f.stored())return &f;return nullptr;}
const std::string* Object::get(uint32_t id) const {auto i=values.find(id);return i==values.end()?nullptr:&i->second;}
bool Object::readValue(uint32_t id,std::string& value) const {if(read)return read(id,value);const auto* current=get(id);if(!current)return false;value=*current;return true;}
bool Object::refresh(){if(!read)return true;auto updated=values;for(auto& item:updated)if(!readValue(item.first,item.second))return false;if(updated!=values){values=std::move(updated);++revision;}return true;}
Registry*& activeRegistry(){static Registry* registry=nullptr;return registry;}
int validate(const Field& f,const std::string& v){if(f.kind==8)return v==f.initial?0:1;if(presentation(f)==Control::Path&&!relativePath(v))return 6;return wf_attr_check(f.kind,f.minimum,f.maximum,f.scale,f.width,f.maxLength,f.rule,reinterpret_cast<const uint8_t*>(f.choices.data()),f.choices.size(),reinterpret_cast<const uint8_t*>(v.data()),v.size());}
const char* validationMessage(int s){switch(s){case 1:return "Enter a valid value for this field";case 2:return "Value is outside the field range";case 3:return "Choose one of the listed values";case 4:return "Text is too long";case 5:return "Enter a seed from 0 to 4294967295";case 6:return "Enter a relative path: names separated by /";default:return "Invalid property value";}}
bool Registry::add(Object object,std::string& error){
    if(!object.actor||objects_.count(object.actor)){error="Duplicate or invalid property object";return false;}
    std::map<uint32_t,bool> seen;
    for(const auto& field:object.fields)if(field.stored()){
        if((!field.id&&!object.oadBacked)||seen.count(field.id)||!object.values.count(field.id)){error="Invalid property fields";return false;}
        seen[field.id]=true;
    }
    object.generation=++serial_;object.revision=0;objects_.emplace(object.actor,std::move(object));error.clear();return true;
}
Object* Registry::object(uint32_t actor){auto i=objects_.find(actor);return i==objects_.end()?nullptr:&i->second;}
const Object* Registry::object(uint32_t actor) const {auto i=objects_.find(actor);return i==objects_.end()?nullptr:&i->second;}
Object* Registry::schema(const std::string& name){for(auto& pair:objects_)if(pair.second.schema==name)return &pair.second;return nullptr;}
std::vector<uint32_t> Registry::editableObjects() const {
    std::vector<uint32_t> result;
    for(const auto& pair:objects_)for(const auto& field:pair.second.fields)
        if(!field.readonly && (field.stored() || field.kind==9)){result.push_back(pair.first);break;}
    return result;
}
void Registry::remove(uint32_t actor){objects_.erase(actor);}
bool Registry::clone(uint32_t source,uint32_t actor){auto* initial=object(source);if(!initial||!actor||initial->oadBacked||initial->apply)return false;Object copy=*initial;copy.actor=actor;copy.generation=++serial_;copy.revision=0;objects_[actor]=std::move(copy);return true;}
void Registry::clear(){objects_.clear();++serial_;}
bool Registry::set(uint32_t actor,uint32_t id,const std::string& v,std::string& error){auto* o=object(actor);const Field* f=o?o->field(id):nullptr;if(!f||f->readonly){error="Property is not editable";return false;}int s=validate(*f,v);if(s){error=validationMessage(s);return false;}if(!o->refresh()){error="Could not read property values";return false;}if(o->values[id]!=v){auto draft=o->values;draft[id]=v;if(o->apply&&!o->apply(draft,error))return false;o->values=std::move(draft);++o->revision;if(o->changed)o->changed({id});}error.clear();return true;}
void LaunchOverrides::set(std::string schema,std::string key,std::string value){std::lock_guard<std::mutex> lock(mutex_);values_[{std::move(schema),std::move(key)}]=std::move(value);}
void LaunchOverrides::erase(const std::string& schema,const std::string& key){std::lock_guard<std::mutex> lock(mutex_);values_.erase({schema,key});}
void LaunchOverrides::clear(){std::lock_guard<std::mutex> lock(mutex_);values_.clear();}
std::vector<std::string> LaunchOverrides::applyObjectLocked(Object& o) const {
    std::vector<std::string> rejected;
    for(const auto& entry:values_){
        const std::string& schema=entry.first.first;const std::string& key=entry.first.second;const std::string& value=entry.second;
        if(o.schema!=schema)continue;
        const Field* f=nullptr;for(const auto& candidate:o.fields)if(candidate.key==key&&candidate.stored()){f=&candidate;break;}
        std::string reason;
        if(!f)reason="no such field";
        else if(!o.refresh())reason="could not read property values";
        else if(int status=validate(*f,value))reason=validationMessage(status);
        else if(o.values[f->id]!=value){
            auto draft=o.values;draft[f->id]=value;
            if(o.apply&&!o.apply(draft,reason)){if(reason.empty())reason="could not apply value";}
            else{o.values=std::move(draft);++o.revision;if(o.changed)o.changed({f->id});}
        }
        if(!reason.empty())rejected.push_back(schema+"."+key+"="+value+": "+reason);
    }
    return rejected;
}
std::vector<std::string> LaunchOverrides::applyObject(Object& object) const {
    std::lock_guard<std::mutex> lock(mutex_);return applyObjectLocked(object);
}
std::vector<std::string> LaunchOverrides::apply(Registry& registry) const {
    std::lock_guard<std::mutex> lock(mutex_);std::vector<std::string> rejected;
    for(const auto& entry:values_){
        const std::string& schema=entry.first.first;const std::string& key=entry.first.second;const std::string& value=entry.second;
        std::string reason;
        for(auto& pair:registry.objects_){
            Object& o=pair.second;if(o.schema!=schema)continue;
            const Field* f=nullptr;for(const auto& candidate:o.fields)if(candidate.key==key&&candidate.stored()){f=&candidate;break;}
            if(!f){if(reason.empty())reason="no such field";continue;}
            if(!o.refresh()){if(reason.empty())reason="could not read property values";continue;}
            if(int status=validate(*f,value)){if(reason.empty())reason=validationMessage(status);continue;}
            std::string& current=o.values[f->id];if(current!=value){
                auto draft=o.values;draft[f->id]=value;std::string applyError;
                if(o.apply&&!o.apply(draft,applyError)){if(reason.empty())reason=applyError.empty()?"could not apply value":applyError;continue;}
                o.values=std::move(draft);++o.revision;if(o.changed)o.changed({f->id});
            }
        }
        if(!reason.empty())rejected.push_back(schema+"."+key+"="+value+": "+reason);
    }
    ++applications_;return rejected;
}
LaunchOverrides& launchOverrides(){static LaunchOverrides overrides;return overrides;}
uint64_t nextSession(){static uint64_t next=0;return ++next;}
bool Edit::begin(Registry& r,uint32_t a){cancel();Object* o=r.object(a);if(!o||!o->refresh())return false;session=nextSession();registry=&r;actor=a;generation=o->generation;revision=o->revision;draft=o->values;open=true;return true;}
Object* Edit::object() const {Object* o=registry?registry->object(actor):nullptr;return o&&o->generation==generation?o:nullptr;}
bool Edit::set(uint32_t id,const std::string& value){auto* o=object();const Field* f=o?o->field(id):nullptr;if(!open||!f||f->readonly||value.size()>65536)return false;draft[id]=value;error.clear();return true;}
bool Edit::validate(){auto* o=object();if(!open||!o||o->revision!=revision){error="Properties changed; reopen the editor";return false;}if(o->read)for(const auto& current:o->values){std::string actual;if(!o->readValue(current.first,actual)||actual!=current.second){error="Properties changed; reopen the editor";return false;}}for(const auto& f:o->fields)if(f.stored()){auto i=draft.find(f.id);if(i==draft.end()){error="Missing property value";return false;}int s=wfprops::validate(f,i->second);if(s){error=f.label+": "+validationMessage(s);return false;}}error.clear();return true;}
bool Edit::commit(){if(!validate())return false;auto* o=object();if(o->values!=draft){std::vector<uint32_t> changed;for(const auto& item:draft){auto old=o->values.find(item.first);if(old==o->values.end()||old->second!=item.second)changed.push_back(item.first);}if(o->apply&&!o->apply(draft,error))return false;o->values=draft;++o->revision;if(o->changed)o->changed(changed);}open=false;return true;}
void Edit::cancel(){open=false;registry=nullptr;draft.clear();error.clear();}
std::string json(const std::string& v){std::string out="\"";const char* hex="0123456789abcdef";for(unsigned char c:v){if(c=='"'||c=='\\'){out+='\\';out+=c;}else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}else out+=c;}return out+'"';}
std::string snapshot(const Edit& e,bool available,bool phone){auto* o=e.object();std::string s="{\"available\":"+std::string(available?"true":"false")+",\"open\":"+(e.open?"true":"false")+",\"phone\":"+(phone?"true":"false")+",\"session\":"+std::to_string(e.session)+",\"error\":"+json(e.error)+",\"title\":"+json(o?o->title:"")+",\"fields\":[";bool first=true;if(o)for(const auto& f:o->fields){if(!first)s+=',';first=false;auto i=e.draft.find(f.id);s+="{\"id\":"+std::to_string(f.id)+",\"kind\":"+std::to_string(f.kind)+",\"show\":"+std::to_string(f.show)+",\"rule\":"+std::to_string(f.rule)+",\"readonly\":"+(f.readonly?"true":"false")+",\"min\":"+std::to_string(f.minimum)+",\"max\":"+std::to_string(f.maximum)+",\"scale\":"+std::to_string(f.scale)+",\"maxLength\":"+std::to_string(f.maxLength)+",\"key\":"+json(f.key)+",\"label\":"+json(f.label)+",\"help\":"+json(f.help)+",\"choices\":"+json(f.choices)+",\"value\":"+json(i==e.draft.end()?"":i->second)+"}";}return s+"]}";}
bool decode(const std::string& in,std::string& out){out.clear();auto digit=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='A'&&c<='F')return c-'A'+10;if(c>='a'&&c<='f')return c-'a'+10;return -1;};for(size_t i=0;i<in.size();i++){if(in[i]=='%'){if(i+2>=in.size())return false;int a=digit(in[++i]),b=digit(in[++i]);if(a<0||b<0)return false;out+=char(a*16+b);}else out+=in[i];}return true;}
}
