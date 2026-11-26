// surface_cap_test: LevelRenderSettings "Maximum surface height" (engine/room_render_settings.hpp) is read as the
// level asks: absent object or field -> 0, a number 0..4320 -> itself, anything else -> 0 with an error.
// The lava lamp sets 1080 so a 4K TV draws it at 1920 x 1080 (docs/plans/2026-11-26-lava-lamp.md, build record).
#include "room_render_settings.hpp"
#include <cstdio>

static int failures = 0;
static void expect(bool ok, const char* what) { if (!ok) { std::printf("FAIL %s\n", what); ++failures; } }

static wfprops::Registry with(const char* value, const char* key = "Maximum surface height") {
    wfprops::Registry registry;
    wfprops::Object object;
    object.actor = 7; object.schema = "LevelRenderSettings";
    wfprops::Field field; field.id = 3; field.kind = 1; field.key = key; field.maximum = 4320;
    object.fields.push_back(field);
    object.values[3] = "0";       // the registry wants every stored field to start with a value
    std::string error;
    if (!registry.add(object, error)) { std::fprintf(stderr, "registry.add: %s\n", error.c_str()); expect(false, "registry.add"); }
    // the value as the level's data holds it, unvalidated (the reader is what is under test)
    wfprops::Object* settings = registry.schema("LevelRenderSettings");
    if (settings) { if (value) settings->values[3] = value; else settings->values.erase(3); }
    return registry;
}

int main() {
    std::string error;
    wfprops::Registry empty;
    expect(wfprops::maximumSurfaceHeight(empty, error) == 0 && error.empty(), "no LevelRenderSettings: 0");
    { auto r = with("1080"); expect(wfprops::maximumSurfaceHeight(r, error) == 1080 && error.empty(), "1080"); }
    { auto r = with("0"); expect(wfprops::maximumSurfaceHeight(r, error) == 0 && error.empty(), "0: no cap"); }
    { auto r = with(nullptr); expect(wfprops::maximumSurfaceHeight(r, error) == 0 && error.empty(), "no value: 0"); }
    { auto r = with("1080", "Maximum aspect"); expect(wfprops::maximumSurfaceHeight(r, error) == 0, "other field only: 0"); }
    { auto r = with("5000"); error.clear(); expect(wfprops::maximumSurfaceHeight(r, error) == 0 && !error.empty(), "5000 refused"); }
    { auto r = with("-1"); error.clear(); expect(wfprops::maximumSurfaceHeight(r, error) == 0 && !error.empty(), "-1 refused"); }
    { auto r = with("10x"); error.clear(); expect(wfprops::maximumSurfaceHeight(r, error) == 0 && !error.empty(), "10x refused"); }
    std::printf(failures ? "FAIL\n" : "surface cap: PASS\n");
    return failures ? 1 : 0;
}
