#include "runtime_diagnostics_form.hpp"

namespace wfoptions {
wfprops::Object diagnosticsForm(uint32_t actor, const std::string& title,
                                const std::map<std::string, std::string>& memory) {
    wfprops::Object object; object.actor = actor; object.schema = "RuntimeDiagnostics"; object.title = title;
    auto section = [&](const char* name) { wfprops::Field f; f.kind=5; f.label=name; object.fields.push_back(std::move(f)); };
    auto runtime = [&](uint32_t id,const char* key,const char* label,const char* group,const char* help,
                       int kind,int low,int high,const char* initial,bool readonly) {
        wfprops::Field f; f.id=id;f.key=key;f.label=label;f.group=group;f.help=help;f.kind=uint8_t(kind);
        f.show=kind==4?8:kind==0?2:0;f.minimum=low;f.maximum=high;f.width=kind==3?256:4;
        f.maxLength=kind==3?255:128;f.readonly=readonly;f.initial=initial;
        object.values[id]=f.initial;object.fields.push_back(std::move(f));
    };
    bool memoryStarted=false;
    section("Runtime Options");
#define RUNTIME_FIELD(id,key,label,group,help,kind,low,high,initial,readonly) runtime(id,key,label,group,help,kind,low,high,initial,readonly);
#define MEMORY_FIELD(_id,_key,_label,_low,_high) do { \
    if (!memoryStarted || _id==2004) { section(_id==2004 ? "Level Behavior" : "Level Memory"); memoryStarted=true; } \
    auto found=memory.find(_key);const std::string value=found==memory.end()?"0":found->second; \
    wfprops::Field f;f.id=_id;f.key=_key;f.label=_label;f.group="Load-time configuration"; \
    f.help="RAM on load; rebuild to change.";f.kind=(_high)==1?4:0;f.show=(_high)==1?8:1; \
    f.minimum=_low;f.maximum=_high;f.width=4;f.maxLength=128;f.readonly=true;f.initial=value; \
    object.values[_id]=value;object.fields.push_back(std::move(f)); \
} while (0);
#include "runtime_diagnostics_fields.inc"
#undef MEMORY_FIELD
#undef RUNTIME_FIELD
    return object;
}
}
