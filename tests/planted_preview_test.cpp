#include "planted_preview.hpp"
#include "runtime_properties.hpp"
#include <cassert>
#include <string>

int main() {
    auto& registry = planted::oadPreviewProperties();
    auto* object = registry.schema("PlantedTankSettings");
    assert(object);
    auto id = [&](const char* key) {
        for (const auto& field : object->fields) if (field.stored() && field.key == key) return field.id;
        assert(false); return uint32_t(0);
    };
    assert(*object->get(id("Growth speed")) == "3");
    assert(*object->get(id("Hold seconds")) == "120");
    assert(*object->get(id("Random seed on entry")) == "1");
    std::string error;
    assert(registry.set(object->actor, id("Seed"), "123", error));
    assert(*object->get(id("Seed")) == "123");
}
