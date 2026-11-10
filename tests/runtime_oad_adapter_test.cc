#include "runtime_oad_adapter.hpp"
#include "oad_field_location.h"
#include "runtime_property_host.hpp"
#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    assert(argc == 2);
    std::ifstream input(argv[1], std::ios::binary);
    std::vector<uint8_t> full((std::istreambuf_iterator<char>(input)), {});
    constexpr size_t header = 80, entry = 1491;
    assert(full.size() >= header && (full.size() - header) % entry == 0);
    size_t sheet = 0, seed = 0;
    for (size_t i = 0; header + (i + 1) * entry <= full.size(); ++i) {
        const auto* e = full.data() + header + i * entry;
        const char* name = reinterpret_cast<const char*>(e + 1);
        if (e[0] == 8 && std::strcmp(name, "Plant growth") == 0) sheet = i;
        if (std::strcmp(name, "Seed") == 0) seed = i;
    }
    assert(sheet > 0 && seed > sheet);
    WfOadFieldLocation prefix{}, seedLocation{};
    assert(wf_attr_oad_field_location(full.data(), full.size(), seed, 0, &seedLocation) == 0);
    // Seed is the first stored field after its sheet.
    assert(seedLocation.common_pointer == -1);
    std::vector<uint8_t> trimmed(full.begin(), full.begin() + header);
    trimmed.insert(trimmed.end(), full.begin() + header + sheet * entry, full.end());
    assert(wf_attr_oad_field_location(trimmed.data(), trimmed.size(), seed - sheet,
                                      seedLocation.offset, &prefix) == 0);
    std::vector<uint8_t> payload(1024), common(1024);
    const int32_t authoredSeed = 2147483647;
    std::memcpy(payload.data() + prefix.offset, &authoredSeed, 4);
    wfprops::Object object; std::string error;
    assert(wfprops::buildOadObject(7, "PlantedTankSettings", "Goldie", trimmed.data(), trimmed.size(),
                                    sheet, seedLocation.offset, payload.data(), payload.size(),
                                    common.data(), common.size(), object, error));
    assert(object.actor == 7 && object.title == "Goldie");
    const auto* field = object.field(uint32_t(seed));
    assert(field && field->key == "Seed" && !field->readonly);
    assert(*object.get(uint32_t(seed)) == "2147483647");
    std::string applied;
    wfprops::Registry registry;
    unsigned changeCount = 0;
    object.apply = [&](const std::map<uint32_t, std::string>& draft, std::string& reason) {
        const auto& value = draft.at(uint32_t(seed));
        if (value == "9") { reason = "backing write failed"; return false; }
        if (!wfprops::applyOadObject(trimmed.data(), trimmed.size(), sheet, seedLocation.offset,
                                     payload.data(), payload.size(), common.data(), common.size(), draft, reason)) return false;
        applied = value; return true;
    };
    object.changed = [&](const std::vector<uint32_t>& fields) {
        assert((fields == std::vector<uint32_t>{uint32_t(seed)}));
        assert(registry.object(7) && *registry.object(7)->get(uint32_t(seed)) == applied);
        ++changeCount;
    };
    assert(registry.add(std::move(object), error));
    wfprops::Edit edit;
    assert(edit.begin(registry, 7) && edit.set(uint32_t(seed), "42") && edit.commit());
    assert(applied == "42" && *registry.object(7)->get(uint32_t(seed)) == "42");
    assert(changeCount == 1);
    int32_t stored = 0; std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 42);
    assert(edit.begin(registry, 7) && edit.set(uint32_t(seed), "9") && !edit.commit());
    assert(edit.error == "backing write failed" && *registry.object(7)->get(uint32_t(seed)) == "42");
    assert(changeCount == 1);
    std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 42);
    wfprops::LaunchOverrides overrides;
    overrides.set("PlantedTankSettings", "Seed", "73");
    assert(overrides.applyObject(*registry.object(7)).empty());
    assert(overrides.applications() == 0);
    std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 73);
    overrides.set("PlantedTankSettings", "Seed", "9");
    assert(!overrides.applyObject(*registry.object(7)).empty());
    assert(*registry.object(7)->get(uint32_t(seed)) == "73");
    edit.cancel();
    wfprops::Host host; bool legacyCalled = false;
    host.consumer("PlantedTankSettings", wfprops::Consumer{[&](){legacyCalled = true;}, {}, {}});
    host.bind(&registry); assert(host.open() && !host.picker && !legacyCalled);
    assert(host.form.edit.set(uint32_t(seed), "37") && host.apply() && !legacyCalled);
    std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 37);
    assert(!wfprops::buildOadObject(7, "x", "x", trimmed.data(), trimmed.size(), sheet,
                                     seedLocation.offset, payload.data(), 1,
                                     common.data(), common.size(), object, error));
}
