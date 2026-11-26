// The engine's side of the settings every level offers: one row per global in oas/global_settings.inc.
// docs/plans/2026-11-22-global-level-settings.md.
#include "global_settings.hp"

#include <cstddef>
#include <cstdio>
#include <cstdlib>
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
// Maximum surface height (hidden): draw at most this many rows; the Android TV host gives the window a buffer that
// size and the compositor scales it up (android/screensaver/src/main/cpp/dream_host.cc). 0: the display's size.
// The lava lamp asks for 1080 so a 4K TV holds its refresh (docs/plans/2026-11-26-lava-lamp.md, build record).
int gMaximumSurfaceHeight = 0;

void maximumSurfaceHeight(const std::string& value, bool)
{
    char* end = nullptr;
    const long rows = std::strtol(value.c_str(), &end, 10);
    if (value.empty() || *end != '\0' || rows < 0 || rows > 4320) {
        std::fprintf(stderr, "GLOBAL-SETTINGS: Maximum surface height must be 0 to 4320, got '%s'\n", value.c_str());
        gMaximumSurfaceHeight = 0;
        return;
    }
    gMaximumSurfaceHeight = int(rows);
    if (rows > 0) std::fprintf(stderr, "VIEW maximum surface height %d\n", gMaximumSurfaceHeight);
}

const Row kRows[] = {
    {"Show framerate", showFramerate},
    {"Maximum surface height", maximumSurfaceHeight},
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
    gMaximumSurfaceHeight = 0;                          // a level without the field draws at the display's size
    for (const uint32_t actor : registry.editableObjects())
        if (const wfprops::Object* holder = registry.object(actor)) apply(*holder, true);
}
}  // namespace wfglobals

// The level's Maximum surface height, read by the Android TV host every frame.
extern "C" int WFMaximumSurfaceHeight() { return wfglobals::gMaximumSurfaceHeight; }
