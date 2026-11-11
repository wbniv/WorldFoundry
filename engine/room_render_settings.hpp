// Authored, load-time room rendering policy from the level settings actor.
#pragma once
#include "runtime_properties.hpp"
#include <cstdlib>
#include <string>

namespace wfprops {
inline bool currentRoomOnly(Registry& registry, std::string& error) {
    error.clear();
    Object* settings = registry.schema("LevelRenderSettings");
    if (!settings) return false; // Legacy levels retain all-active rendering.
    const Field* field = nullptr;
    for (const auto& candidate : settings->fields) if (candidate.stored() && candidate.key == "Room Render Scope") { field = &candidate; break; }
    const std::string* value = field ? settings->get(field->id) : nullptr;
    if (!field || field->kind != 2 ||
        field->minimum != 0 || field->maximum != 1 || !field->readonly ||
        !value || (*value != "0" && *value != "1")) {
        error = "LevelRenderSettings: Room Render Scope must be a read-only enum (0 or 1)";
        return false;
    }
    return *value == "1";
}

// LevelRenderSettings "Authored aspect" and "Maximum aspect" (gfx/authored_view.hp),
// found by key, so they can sit at any field id next to Room Render Scope. A level
// without the schema or the field gets 0 (off: today's 60 degree view); a value that
// is not a number >= 0 is reported and treated as 0. `found` says whether the level
// carried the field.
inline float aspectSetting(Registry& registry, const char* key, bool& found, std::string& error) {
    found = false;
    const Object* settings = registry.schema("LevelRenderSettings");
    if (!settings) return 0.0f;
    for (const Field& field : settings->fields) {
        if (field.key != key) continue;
        found = true;
        const std::string* value = settings->get(field.id);
        if (!value || value->empty()) return 0.0f;
        char* end = nullptr;
        const float f = std::strtof(value->c_str(), &end);
        if (end == value->c_str() || *end != '\0' || !(f >= 0.0f) || f > 100.0f) {
            error = "LevelRenderSettings: " + std::string(key) + " must be a number >= 0 (0 is off), got " + *value;
            return 0.0f;
        }
        return f;
    }
    return 0.0f;
}
}
