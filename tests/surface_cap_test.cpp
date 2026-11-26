// surface_cap_test: the hidden global setting "Maximum surface height" (wfsource/source/oas/global_settings.inc) is
// applied at load by wfglobals (wfsource/source/game/global_settings.cc) and read by the Android TV host through
// WFMaximumSurfaceHeight(): a holder without the field -> 0, a number 0..4320 -> itself, anything else -> 0, and
// each load starts from 0. The lava lamp sets 1080 so a 4K TV draws it at 1920 x 1080
// (docs/plans/2026-11-26-lava-lamp.md, build record).
#include "../wfsource/source/game/global_settings.hp"
#include <cstdio>

namespace fpscounter { bool enabled = false; }
extern "C" int WFMaximumSurfaceHeight();

static int failures = 0;
static void expect(bool ok, const char* what) { if (!ok) { std::printf("FAIL %s\n", what); ++failures; } }

static int load(const char* value, const char* key = "Maximum surface height") {
    wfprops::Registry registry;
    wfprops::Object object;
    object.actor = 7; object.schema = "LavaLampSettings";
    wfprops::Field field; field.id = 3; field.kind = 1; field.key = key; field.maximum = 4320;
    object.fields.push_back(field);
    object.values[3] = "0";                 // the registry wants every stored field to start with a value
    std::string error;
    if (!registry.add(object, error)) { std::fprintf(stderr, "registry.add: %s\n", error.c_str()); expect(false, "registry.add"); }
    wfprops::Object* holder = registry.object(7);
    if (holder) { if (value) holder->values[3] = value; else holder->values.erase(3); }
    wfglobals::applyAtLoad(registry);
    return WFMaximumSurfaceHeight();
}

int main() {
    expect(load("1080") == 1080, "1080");
    expect(load("0") == 0, "0: no cap");
    expect(load("1080") == 1080 && load(nullptr) == 0, "a load without a value starts from 0");
    expect(load("1080") == 1080 && load("1080", "Show framerate") == 0, "a holder without the field: 0");
    expect(load("5000") == 0, "5000 refused");
    expect(load("-1") == 0, "-1 refused");
    expect(load("10x") == 0, "10x refused");
    std::printf(failures ? "FAIL\n" : "surface cap: PASS\n");
    return failures ? 1 : 0;
}
