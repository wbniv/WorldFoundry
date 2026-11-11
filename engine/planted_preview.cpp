#include "planted_preview.hpp"
#include "runtime_oad_adapter.hpp"
#include "oad_field_location.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {
#include "planted_oad.inc"
constexpr size_t header = 80, entry = 1491;

struct Preview {
    std::vector<uint8_t> descriptor, payload, common;
    std::vector<wfprops::CommonPage> pages;
    wfprops::Registry registry;
    uint32_t first = 0, prefix = 0;

    Preview() : common(4) {
        size_t sheet = SIZE_MAX, seed = SIZE_MAX;
        for (size_t i = 0; header + (i + 1) * entry <= sizeof(plantedOad); ++i) {
            const auto* record = plantedOad + header + i * entry;
            if (record[0] == 8 && !std::strcmp(reinterpret_cast<const char*>(record + 1), "Plant growth")) sheet = i;
            if (!std::strcmp(reinterpret_cast<const char*>(record + 1), "Seed")) seed = i;
        }
        WfOadFieldLocation location{};
        if (sheet == SIZE_MAX || seed == SIZE_MAX ||
            wf_attr_oad_field_location(plantedOad, sizeof(plantedOad), seed, 0, &location) || location.common_pointer >= 0)
            fail("invalid planted settings descriptor");
        first = uint32_t(sheet); prefix = location.offset;
        descriptor.assign(plantedOad, plantedOad + header);
        descriptor.insert(descriptor.end(), plantedOad + header + sheet * entry, plantedOad + sizeof(plantedOad));
        std::string error;
        if (!wfprops::buildOadDefaults(descriptor.data(), descriptor.size(), prefix, 1024, payload, error)) fail(error);
        wfprops::Object object;
        if (!wfprops::buildOadObject(1, "PlantedTankSettings", "Planted Tank", descriptor.data(), descriptor.size(),
                                     first, prefix, payload.data(), payload.size(), common.data(), common.size(),
                                     object, error)) fail(error);
        object.apply = [this](const std::map<uint32_t, std::string>& values, std::string& reason) {
            return wfprops::applyOadObject(descriptor.data(), descriptor.size(), first, prefix, payload.data(), payload.size(),
                                           common.data(), common.size(), pages, values, reason);
        };
        // The selector still uses its plant-specific actions; level actors use
        // their own hook and never call this preview consumer.
        object.oadBacked = false;
        wfprops::Field section; section.kind = 5; section.label = "Actions"; object.fields.push_back(section);
        wfprops::Field action; action.kind = 9; action.id = 100; action.key = "regenerate"; action.label = "Regenerate"; object.fields.push_back(action);
        action.id = 101; action.key = "random-seed"; action.label = "New random seed"; object.fields.push_back(action);
        if (!registry.add(std::move(object), error)) fail(error);
    }
    [[noreturn]] static void fail(const std::string& error) {
        std::fprintf(stderr, "planted preview: %s\n", error.c_str()); std::abort();
    }
};
}
namespace planted { wfprops::Registry& oadPreviewProperties() { static Preview preview; return preview.registry; } }
