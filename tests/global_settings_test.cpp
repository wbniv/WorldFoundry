// The engine's table of global settings (wfsource/source/game/global_settings.cc): which field does what, and the
// difference between a level loading and a player applying a change. Built and run by `task test-global-settings`
// in wf-linux-test:local with plain g++: no renderer, no engine. docs/plans/2026-11-22-global-level-settings.md.
#undef NDEBUG  // the checks below carry side effects
#include <cassert>
#include <cstdio>
#include <string>

#include <game/global_settings.hp>

namespace fpscounter { bool enabled = false; }   // the overlay's flag; the real one is in fps_overlay.cc

namespace {
int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)

// A holder with one stored field, as a level's settings object presents it after loading.
wfprops::Object holder(uint32_t actor, const std::string& key, const std::string& value, uint8_t kind = 0) {
    wfprops::Object object;
    object.actor = actor;
    object.schema = "TestSettings";
    wfprops::Field field;
    field.id = 130;
    field.kind = kind;
    field.key = field.label = key;
    object.fields.push_back(field);
    object.values[130] = value;
    return object;
}

bool add(wfprops::Registry& registry, wfprops::Object object) {
    std::string error;
    return registry.add(std::move(object), error);
}
}  // namespace

int main() {
    // A level loads with the setting ticked: the overlay comes on.
    {
        fpscounter::enabled = false;
        wfprops::Registry registry;
        CHECK(add(registry, holder(5, "Show framerate", "1")));
        wfglobals::applyAtLoad(registry);
        CHECK(fpscounter::enabled);
    }
    // A level loads with it at its default (off): that is no opinion, so what the command line or the runtime options
    // chose stays.
    {
        fpscounter::enabled = true;
        wfprops::Registry registry;
        CHECK(add(registry, holder(5, "Show framerate", "0")));
        wfglobals::applyAtLoad(registry);
        CHECK(fpscounter::enabled);
    }
    // A level with no holder changes nothing.
    {
        fpscounter::enabled = true;
        wfprops::Registry registry;
        wfglobals::applyAtLoad(registry);
        CHECK(fpscounter::enabled);
        fpscounter::enabled = false;
        wfglobals::applyAtLoad(registry);
        CHECK(!fpscounter::enabled);
    }
    // The player applies a change: exactly what the form says, on or off.
    {
        fpscounter::enabled = false;
        wfglobals::applyChanged(holder(5, "Show framerate", "1"));
        CHECK(fpscounter::enabled);
        wfglobals::applyChanged(holder(5, "Show framerate", "0"));
        CHECK(!fpscounter::enabled);
    }
    // Two holders that disagree at load: any ticked one turns it on.
    {
        fpscounter::enabled = false;
        wfprops::Registry registry;
        CHECK(add(registry, holder(5, "Show framerate", "0")));
        CHECK(add(registry, holder(6, "Show framerate", "1")));
        wfglobals::applyAtLoad(registry);
        CHECK(fpscounter::enabled);
    }
    // A field with another key, or one that is not stored (a button, a label), is not the global setting.
    {
        fpscounter::enabled = false;
        wfglobals::applyChanged(holder(5, "Something else", "1"));
        CHECK(!fpscounter::enabled);
        wfglobals::applyChanged(holder(5, "Show framerate", "1", 9));   // kind 9: an action, not a stored value
        CHECK(!fpscounter::enabled);
    }
    // A holder whose value is missing (never read) does nothing and does not crash.
    {
        fpscounter::enabled = true;
        wfprops::Object object = holder(5, "Show framerate", "0");
        object.values.clear();
        wfglobals::applyChanged(object);
        CHECK(fpscounter::enabled);
    }
    std::printf("global_settings: %d checks passed\n", checks);
    return 0;
}
