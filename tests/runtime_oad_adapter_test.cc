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
    size_t sheet = 0, seed = 0, initialAge = 0;
    for (size_t i = 0; header + (i + 1) * entry <= full.size(); ++i) {
        const auto* e = full.data() + header + i * entry;
        const char* name = reinterpret_cast<const char*>(e + 1);
        if (e[0] == 8 && std::strcmp(name, "Plant growth") == 0) sheet = i;
        if (std::strcmp(name, "Seed") == 0) seed = i;
        if (std::strcmp(name, "Initial age") == 0) initialAge = i;
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
    std::vector<uint8_t> defaults;
    std::string defaultError;
    assert(wfprops::buildOadDefaults(trimmed.data(), trimmed.size(), seedLocation.offset,
                                    1024, defaults, defaultError));
    std::vector<uint8_t> emptyCommon(1024);
    wfprops::Object preview;
    assert(wfprops::buildOadObject(1, "PlantedTankSettings", "Preview", trimmed.data(), trimmed.size(),
                                   sheet, seedLocation.offset, defaults.data(), defaults.size(),
                                   emptyCommon.data(), emptyCommon.size(), preview, defaultError));
    auto previewValue = [&](const char* key) -> std::string {
        for (const auto& f : preview.fields) if (f.stored() && f.key == key) return *preview.get(f.id);
        assert(false); return {};
    };
    assert(previewValue("Seed") == "0" && previewValue("Growth speed") == "3");
    assert(previewValue("Random seed on entry") == "1" && previewValue("Hold seconds") == "120");
    auto savedDefaults = defaults;
    assert(!wfprops::buildOadDefaults(trimmed.data(), trimmed.size(), seedLocation.offset,
                                      1, defaults, defaultError) && defaults == savedDefaults);
    std::vector<uint8_t> payload(1024), common(1024);
    std::vector<wfprops::CommonPage> pages;
    const int32_t authoredSeed = 2147483647;
    std::memcpy(payload.data() + prefix.offset, &authoredSeed, 4);
    wfprops::Object object; std::string error;
    assert(wfprops::buildOadObject(7, "PlantedTankSettings", "Goldie", trimmed.data(), trimmed.size(),
                                    sheet, seedLocation.offset, payload.data(), payload.size(),
                                    common.data(), common.size(), object, error));
    assert(object.actor == 7 && object.title == "Goldie");
    const auto* field = object.field(uint32_t(seed));
    assert(field && field->key == "Seed" && !field->readonly && field->maxLength >= 10);
    assert(*object.get(uint32_t(seed)) == "2147483647");
    std::string applied;
    wfprops::Registry registry;
    unsigned changeCount = 0;
    object.read = [&](uint32_t id, std::string& value) {
        const auto* field = registry.object(7) ? registry.object(7)->field(id) : nullptr;
        return field && wfprops::readOadField(*field, payload.data(), payload.size(),
                                               common.data(), common.size(), pages, value);
    };
    object.apply = [&](const std::map<uint32_t, std::string>& draft, std::string& reason) {
        const auto& value = draft.at(uint32_t(seed));
        if (value == "9") { reason = "backing write failed"; return false; }
        if (!wfprops::applyOadObject(trimmed.data(), trimmed.size(), sheet, seedLocation.offset,
                                     payload.data(), payload.size(), common.data(), common.size(), pages, draft, reason)) return false;
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
    stored = 58; std::memcpy(payload.data() + prefix.offset, &stored, 4);
    std::string direct;
    assert(registry.object(7)->readValue(uint32_t(seed), direct) && direct == "58");
    assert(host.open() && host.form.edit.draft[uint32_t(seed)] == "58");
    assert(host.form.edit.set(uint32_t(seed), "60"));
    stored = 59; std::memcpy(payload.data() + prefix.offset, &stored, 4);
    assert(!host.apply() && host.form.edit.error == "Properties changed; reopen the editor");
    host.close();
    assert(registry.set(7, uint32_t(seed), "58", error));
    std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 58);
    assert(!wfprops::buildOadObject(7, "x", "x", trimmed.data(), trimmed.size(), sheet,
                                     seedLocation.offset, payload.data(), 1,
                                     common.data(), common.size(), object, error));

    // Debug edit-all exposes non-live fields, but omits fields added after an
    // older level's payload. Writes to the remaining fields still work.
    wfprops::Object debug;
    assert(initialAge > seed);
    assert(wfprops::buildOadObject(8, "x", "x", trimmed.data(), trimmed.size(), sheet,
                                  seedLocation.offset, payload.data(), payload.size(),
                                  common.data(), common.size(), debug, error, true, true));
    assert(debug.field(uint32_t(initialAge)) && !debug.field(uint32_t(initialAge))->readonly);
    const size_t oldPayloadSize = prefix.offset + 4;
    assert(wfprops::buildOadObject(8, "x", "x", trimmed.data(), trimmed.size(), sheet,
                                  seedLocation.offset, payload.data(), oldPayloadSize,
                                  common.data(), common.size(), debug, error, true, true));
    assert(debug.field(uint32_t(seed)) && !debug.field(uint32_t(initialAge)));
    auto oldDraft = debug.values;
    oldDraft[uint32_t(seed)] = "41";
    assert(wfprops::applyOadObject(trimmed.data(), trimmed.size(), sheet, seedLocation.offset,
                                   payload.data(), oldPayloadSize, common.data(), common.size(),
                                   pages, oldDraft, error, true));
    std::memcpy(&stored, payload.data() + prefix.offset, 4); assert(stored == 41);

    // A full debug descriptor can legitimately put a stored field at index 0.
    std::vector<uint8_t> zeroOad(full.begin(), full.begin() + header);
    zeroOad.insert(zeroOad.end(), full.begin() + header + seed * entry,
                   full.begin() + header + (seed + 1) * entry);
    std::vector<uint8_t> zeroPayload(4);
    wfprops::Object zeroObject;
    assert(wfprops::buildOadObject(9, "x", "x", zeroOad.data(), zeroOad.size(), 0, 0,
                                  zeroPayload.data(), zeroPayload.size(), common.data(), common.size(),
                                  zeroObject, error, true, true));
    assert(zeroObject.field(0) && registry.add(std::move(zeroObject), error));

    // Put the real live Seed descriptor inside a common block. Two actors
    // start with the same page; an edit must copy only the first actor's page.
    size_t block = SIZE_MAX, end = SIZE_MAX;
    for (size_t i = 0; header + (i + 1) * entry <= full.size(); ++i) {
        const auto type = full[header + i * entry];
        if (type == 17 && block == SIZE_MAX) block = i;
        if (type == 18 && block != SIZE_MAX && end == SIZE_MAX) end = i;
    }
    assert(block != SIZE_MAX && end != SIZE_MAX && end > block);
    std::vector<uint8_t> sharedOad(full.begin(), full.begin() + header);
    auto appendEntry = [&](size_t i) {
        sharedOad.insert(sharedOad.end(), full.begin() + header + i * entry,
                         full.begin() + header + (i + 1) * entry);
    };
    appendEntry(sheet); appendEntry(block); appendEntry(seed); appendEntry(end);
    std::vector<uint8_t> sharedCommon(16), firstPayload(4), secondPayload(4);
    const int32_t originalOffset = 4, initial = 11;
    std::memcpy(firstPayload.data(), &originalOffset, 4);
    std::memcpy(secondPayload.data(), &originalOffset, 4);
    std::memcpy(sharedCommon.data() + originalOffset, &initial, 4);
    wfprops::Object first;
    assert(wfprops::buildOadObject(1, "Test", "First", sharedOad.data(), sharedOad.size(), 100, 0,
                                    firstPayload.data(), firstPayload.size(), sharedCommon.data(), sharedCommon.size(), first, error));
    assert(*first.get(102) == "11");
    std::vector<wfprops::CommonPage> firstPages, secondPages;
    auto draft = first.values; draft[102] = "42";
    assert(wfprops::applyOadObject(sharedOad.data(), sharedOad.size(), 100, 0,
                                   firstPayload.data(), firstPayload.size(), sharedCommon.data(), sharedCommon.size(),
                                   firstPages, draft, error));
    int32_t handle = 0, pageValue = 0, untouched = 0;
    std::memcpy(&handle, firstPayload.data(), 4);
    std::memcpy(&pageValue, firstPages[0].bytes.data(), 4);
    std::memcpy(&untouched, sharedCommon.data() + originalOffset, 4);
    assert(firstPages.size() == 1 && handle == firstPages[0].handle && pageValue == 42 && untouched == 11);
    assert(secondPages.empty() && std::memcmp(secondPayload.data(), &originalOffset, 4) == 0);
    const auto* stableAddress = firstPages[0].bytes.data();
    draft[102] = "73";
    assert(wfprops::applyOadObject(sharedOad.data(), sharedOad.size(), 100, 0,
                                   firstPayload.data(), firstPayload.size(), sharedCommon.data(), sharedCommon.size(),
                                   firstPages, draft, error));
    std::memcpy(&pageValue, firstPages[0].bytes.data(), 4);
    assert(firstPages.size() == 1 && firstPages[0].bytes.data() == stableAddress && pageValue == 73);
    assert(wfprops::readOadField(*first.field(102), firstPayload.data(), firstPayload.size(),
                                 sharedCommon.data(), sharedCommon.size(), firstPages, direct) && direct == "73");
    assert(wfprops::readOadField(*first.field(102), secondPayload.data(), secondPayload.size(),
                                 sharedCommon.data(), sharedCommon.size(), secondPages, direct) && direct == "11");
    draft[102] = "999999999999";
    assert(!wfprops::applyOadObject(sharedOad.data(), sharedOad.size(), 100, 0,
                                    firstPayload.data(), firstPayload.size(), sharedCommon.data(), sharedCommon.size(),
                                    firstPages, draft, error));
    std::memcpy(&pageValue, firstPages[0].bytes.data(), 4); assert(pageValue == 73);
}
