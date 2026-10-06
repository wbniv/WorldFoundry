#include "runtime_properties.hpp"
#include <algorithm>
#include <cstring>
#include <limits>

extern "C" int wf_attr_check(uint32_t,int32_t,int32_t,uint32_t,uint32_t,uint32_t,uint32_t,const uint8_t*,size_t,const uint8_t*,size_t);
namespace wfprops {
namespace {
struct Reader {
    const uint8_t* p;size_t left;bool valid=true;
    uint32_t number(){if(left<4){valid=false;return 0;}uint32_t n=uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;p+=4;left-=4;return n;}
    uint8_t byte(){if(!left){valid=false;return 0;}--left;return *p++;}
    std::string text(){uint32_t n=number();if(!valid||n>left||n>65536){valid=false;return {}; }std::string s(reinterpret_cast<const char*>(p),n);p+=n;left-=n;return s;}
};
}
const Field* Object::field(uint32_t id) const {for(const auto& f:fields)if(f.id==id&&f.stored())return &f;return nullptr;}
const std::string* Object::get(uint32_t id) const {auto i=values.find(id);return i==values.end()?nullptr:&i->second;}
Registry*& activeRegistry(){static Registry* registry=nullptr;return registry;}
int validate(const Field& f,const std::string& v){if(f.kind==8)return v==f.initial?0:1;return wf_attr_check(f.kind,f.minimum,f.maximum,f.scale,f.width,f.maxLength,f.rule,reinterpret_cast<const uint8_t*>(f.choices.data()),f.choices.size(),reinterpret_cast<const uint8_t*>(v.data()),v.size());}
const char* validationMessage(int s){switch(s){case 1:return "Enter a valid value for this field";case 2:return "Value is outside the field range";case 3:return "Choose one of the listed values";case 4:return "Text is too long";case 5:return "Enter a seed from 0 to 4294967295";default:return "Invalid property value";}}
bool Registry::load(const uint8_t* data,size_t size,std::string& error){
    if(size<8||std::memcmp(data,"RP01",4)){error="Unsupported property catalog";return false;}
    Reader r{data+4,size-4};uint32_t count=r.number();if(count>4096){error="Too many property objects";return false;}
    std::map<uint32_t,Object> loaded;
    for(uint32_t i=0;i<count&&r.valid;i++){
        Object o;o.actor=r.number();o.schema=r.text();o.title=r.text();o.generation=++serial_;
        uint32_t n=r.number();if(!o.actor||n>16384||loaded.count(o.actor)){r.valid=false;break;}
        for(uint32_t j=0;j<n&&r.valid;j++){
            Field f;f.id=r.number();f.kind=r.byte();f.show=r.byte();f.readonly=r.byte();f.rule=r.byte();
            f.minimum=int32_t(r.number());f.maximum=int32_t(r.number());f.scale=r.number();f.width=r.number();f.maxLength=r.number();
            f.key=r.text();f.label=r.text();f.help=r.text();f.group=r.text();f.choices=r.text();f.initial=r.text();
            if(f.kind>10||f.id>32767||(f.stored()&&(!f.id||o.values.count(f.id)||validate(f,f.initial)))){r.valid=false;break;}
            if(f.stored())o.values[f.id]=f.initial;
            o.fields.push_back(std::move(f));
        }loaded.emplace(o.actor,std::move(o));
    }
    if(!r.valid||r.left){error="Malformed property catalog";return false;}
    objects_=std::move(loaded);error.clear();return true;
}
Object* Registry::object(uint32_t actor){auto i=objects_.find(actor);return i==objects_.end()?nullptr:&i->second;}
const Object* Registry::object(uint32_t actor) const {auto i=objects_.find(actor);return i==objects_.end()?nullptr:&i->second;}
Object* Registry::schema(const std::string& name){for(auto& pair:objects_)if(pair.second.schema==name)return &pair.second;return nullptr;}
void Registry::remove(uint32_t actor){objects_.erase(actor);}
bool Registry::clone(uint32_t source,uint32_t actor){auto* initial=object(source);if(!initial||!actor)return false;Object copy=*initial;copy.actor=actor;copy.generation=++serial_;copy.revision=0;objects_[actor]=std::move(copy);return true;}
void Registry::clear(){objects_.clear();++serial_;}
bool Registry::set(uint32_t actor,uint32_t id,const std::string& v,std::string& error){auto* o=object(actor);const Field* f=o?o->field(id):nullptr;if(!f||f->readonly){error="Property is not editable";return false;}int s=validate(*f,v);if(s){error=validationMessage(s);return false;}if(o->values[id]!=v){o->values[id]=v;++o->revision;}error.clear();return true;}
bool Edit::begin(Registry& r,uint32_t a){cancel();Object* o=r.object(a);if(!o)return false;static uint64_t next=0;session=++next;registry=&r;actor=a;generation=o->generation;revision=o->revision;draft=o->values;open=true;return true;}
Object* Edit::object() const {Object* o=registry?registry->object(actor):nullptr;return o&&o->generation==generation?o:nullptr;}
bool Edit::set(uint32_t id,const std::string& value){auto* o=object();const Field* f=o?o->field(id):nullptr;if(!open||!f||f->readonly||value.size()>65536)return false;draft[id]=value;error.clear();return true;}
bool Edit::validate(){auto* o=object();if(!open||!o||o->revision!=revision){error="Properties changed; reopen the editor";return false;}for(const auto& f:o->fields)if(f.stored()){auto i=draft.find(f.id);if(i==draft.end()){error="Missing property value";return false;}int s=wfprops::validate(f,i->second);if(s){error=f.label+": "+validationMessage(s);return false;}}error.clear();return true;}
bool Edit::commit(){if(!validate())return false;auto* o=object();if(o->values!=draft){o->values=draft;++o->revision;}open=false;return true;}
void Edit::cancel(){open=false;registry=nullptr;draft.clear();error.clear();}
std::string json(const std::string& v){std::string out="\"";const char* hex="0123456789abcdef";for(unsigned char c:v){if(c=='"'||c=='\\'){out+='\\';out+=c;}else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}else out+=c;}return out+'"';}
std::string snapshot(const Edit& e,bool available,bool phone){auto* o=e.object();std::string s="{\"available\":"+std::string(available?"true":"false")+",\"open\":"+(e.open?"true":"false")+",\"phone\":"+(phone?"true":"false")+",\"session\":"+std::to_string(e.session)+",\"error\":"+json(e.error)+",\"title\":"+json(o?o->title:"")+",\"fields\":[";bool first=true;if(o)for(const auto& f:o->fields){if(!first)s+=',';first=false;auto i=e.draft.find(f.id);s+="{\"id\":"+std::to_string(f.id)+",\"kind\":"+std::to_string(f.kind)+",\"show\":"+std::to_string(f.show)+",\"rule\":"+std::to_string(f.rule)+",\"readonly\":"+(f.readonly?"true":"false")+",\"min\":"+std::to_string(f.minimum)+",\"max\":"+std::to_string(f.maximum)+",\"scale\":"+std::to_string(f.scale)+",\"maxLength\":"+std::to_string(f.maxLength)+",\"key\":"+json(f.key)+",\"label\":"+json(f.label)+",\"help\":"+json(f.help)+",\"choices\":"+json(f.choices)+",\"value\":"+json(i==e.draft.end()?"":i->second)+"}";}return s+"]}";}
bool decode(const std::string& in,std::string& out){out.clear();auto digit=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='A'&&c<='F')return c-'A'+10;if(c>='a'&&c<='f')return c-'a'+10;return -1;};for(size_t i=0;i<in.size();i++){if(in[i]=='%'){if(i+2>=in.size())return false;int a=digit(in[++i]),b=digit(in[++i]);if(a<0||b<0)return false;out+=char(a*16+b);}else out+=in[i];}return true;}
}
