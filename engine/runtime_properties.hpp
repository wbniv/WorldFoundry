// Generic OAD-derived instance properties. No editor/debug dependencies.
#pragma once
#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace wfprops {
struct Field {
    uint32_t id=0; uint8_t kind=0,show=0,readonly=0,rule=0;
    int32_t minimum=0,maximum=0;uint32_t scale=0,width=0,maxLength=0;
    std::string key,label,help,group,choices,initial;
    bool stored() const {return kind<5 || kind==8;}
};
struct Object {
    uint32_t actor=0; uint64_t generation=0,revision=0;
    std::string schema,title;std::vector<Field> fields;
    std::map<uint32_t,std::string> values;
    const Field* field(uint32_t id) const;
    const std::string* get(uint32_t id) const;
};
class Registry {
public:
    bool load(const uint8_t* data,size_t size,std::string& error);
    Object* object(uint32_t actor);
    const Object* object(uint32_t actor) const;
    Object* schema(const std::string& name);
    void remove(uint32_t actor);
    bool clone(uint32_t source,uint32_t actor);
    bool set(uint32_t actor,uint32_t field,const std::string& value,std::string& error);
    void clear();
private:
    std::map<uint32_t,Object> objects_;
    uint64_t serial_=0;
};

struct Edit {
    bool open=false;uint64_t session=0,generation=0,revision=0;
    uint32_t actor=0;Registry* registry=nullptr;
    std::map<uint32_t,std::string> draft;std::string error;
    bool begin(Registry& registry,uint32_t actor);
    Object* object() const;
    bool set(uint32_t field,const std::string& value);
    bool validate();
    bool commit();
    void cancel();
};
int validate(const Field& field,const std::string& value);
const char* validationMessage(int status);
std::string json(const std::string& value);
std::string snapshot(const Edit& edit,bool available,bool phone);
bool decode(const std::string& value,std::string& result);
Registry*& activeRegistry();
}
