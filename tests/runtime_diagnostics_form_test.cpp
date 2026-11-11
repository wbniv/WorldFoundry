#include "runtime_diagnostics_form.hpp"
#include "runtime_options.hpp"
#include <cassert>

int main() {
    std::map<std::string,std::string> memory{{"memory_object_heap_bytes","400000"},
        {"memory_permanent_asset_bytes","2000000"},{"memory_room_asset_bytes","8000000"},
        {"memory_active_room_slots","3"},{"memory_doom_stick","1"},{"memory_bungee_camera","1"}};
    auto object=wfoptions::diagnosticsForm(9,"Runtime settings",memory);
    assert(object.fields.size()>80 && *object.get(2000)=="400000" && object.field(2000)->readonly);
    wfprops::Registry registry;std::string error;assert(registry.add(std::move(object),error));
    auto& host=wfprops::host();host.bind(&registry);
    wfoptions::Snapshot snapshot={{"runtime_show_fps",{"1",true,"FPS"}},
        {"runtime_clock_hz",{"20",true,"Rate"}},{"runtime_static_mesh",{"On",false,"Cached"}}};
    bool applied=false;
    wfoptions::install(registry,{[&](){return snapshot;},[](const wfoptions::Changes&,std::string&){return true;},
        [&](const wfoptions::Changes& changes){applied=true;for(const auto& item:changes)snapshot[item.first].value=item.second;}},"RuntimeDiagnostics");
    assert(host.openOwner(9));
    assert(*registry.object(9)->get(1005)=="On" && registry.object(9)->field(1005)->readonly);
    assert(host.form.edit.set(1000,"0") && host.apply() && applied && snapshot["runtime_show_fps"].value=="0");
    assert(host.openOwner(9));assert(host.form.edit.set(1000,"1"));host.close();
    assert(snapshot["runtime_show_fps"].value=="0");host.bind(nullptr);
}
