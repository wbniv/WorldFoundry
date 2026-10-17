// Authored, load-time room rendering policy carried by the existing RPRP catalog.
#pragma once
#include "runtime_properties.hpp"

namespace wfprops {
inline bool currentRoomOnly(Registry& registry, std::string& error) {
    error.clear();
    Object* settings = registry.schema("LevelRenderSettings");
    if (!settings) return false; // Legacy levels retain all-active rendering.
    const Field* field = settings->field(1);
    const std::string* value = settings->get(1);
    if (!field || field->key != "Room Render Scope" || field->kind != 2 ||
        field->minimum != 0 || field->maximum != 1 || !field->readonly ||
        !value || (*value != "0" && *value != "1")) {
        error = "LevelRenderSettings: field 1 must be a read-only Room Render Scope enum (0 or 1)";
        return false;
    }
    return *value == "1";
}
}
