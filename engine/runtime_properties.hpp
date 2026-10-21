// Generic OAD-derived instance properties. No editor/debug dependencies.
#pragma once
#include <atomic>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <utility>
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
    std::vector<uint32_t> editableObjects() const;
    void remove(uint32_t actor);
    bool clone(uint32_t source,uint32_t actor);
    bool set(uint32_t actor,uint32_t field,const std::string& value,std::string& error);
    void clear();
private:
    friend class LaunchOverrides;
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
uint64_t nextSession();

// Values a host sets before a level activates (docs/plans/2026-10-21-planted-tank-screensaver.md,
// Phase 2c). Applied to every object whose schema matches, each time a level registry loads,
// before activeRegistry() is set and before any script runs. Keys are field keys (RP01
// Field::key, the OAS field name), never numeric ids. An override whose schema is absent from
// the level is skipped silently (most levels lack most schemas); a key the matching schema
// lacks, or a value that fails wfprops::validate, is reported and leaves the old value.
class LaunchOverrides {
public:
    void set(std::string schema,std::string key,std::string value);
    void erase(const std::string& schema,const std::string& key);
    void clear();
    // Writes each valid override into the matching objects, read-only fields included, and
    // bumps the revision of each object it changes. Returns "schema.key=value: reason" for
    // each override it rejects. Counts one application per call.
    std::vector<std::string> apply(Registry& registry) const;
    // Number of apply() calls so far: a host compares it to detect that a new level loaded.
    uint64_t applications() const {return applications_.load();}
private:
    mutable std::mutex mutex_;   // the host may write from a JNI/UI thread
    std::map<std::pair<std::string,std::string>,std::string> values_;
    mutable std::atomic<uint64_t> applications_{0};
};
LaunchOverrides& launchOverrides();
}
