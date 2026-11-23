// The engine's side of the settings every level offers: one row per global in oas/global_settings.inc.
// docs/plans/2026-11-22-global-level-settings.md.
#include "global_settings.hp"

#include <cstddef>
#include <string>

// The flag the overlay checks every frame (defined in fps_overlay.cc). Declared here, not included, so this file
// and its host test (tests/global_settings_test.cpp) need no renderer or font headers.
namespace fpscounter { extern bool enabled; }

namespace wfglobals
{
namespace
{
// What one global does. `atLoad` is true when the level has just loaded, false after the player applied a change.
struct Row
{
    const char* key;                                    // the field's key in global_settings.inc
    void (*apply)(const std::string& value, bool atLoad);
};

void showFramerate(const std::string& value, bool atLoad)
{
    if (value == "1") fpscounter::enabled = true;
    else if (!atLoad) fpscounter::enabled = false;      // unticked on purpose; at load "off" is only the default
}

// Add a global here and in global_settings.inc, nowhere else.
const Row kRows[] = {
    {"Show framerate", showFramerate},
};

void apply(const wfprops::Object& holder, bool atLoad)
{
    for (const Row& row : kRows) {
        for (const wfprops::Field& field : holder.fields) {
            if (!field.stored() || field.key != row.key) continue;
            if (const std::string* value = holder.get(field.id)) row.apply(*value, atLoad);
            break;
        }
    }
}
}  // namespace

void applyChanged(const wfprops::Object& holder) { apply(holder, false); }

void applyAtLoad(const wfprops::Registry& registry)
{
    for (const uint32_t actor : registry.editableObjects())
        if (const wfprops::Object* holder = registry.object(actor)) apply(*holder, true);
}
}  // namespace wfglobals
