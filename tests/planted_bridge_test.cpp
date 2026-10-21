// Planted Tank host bridge, pure logic (android/screensaver/src/main/cpp/planted_bridge.*;
// docs/plans/2026-10-21-planted-tank-screensaver.md, Phase 2b). Built and run by
// `task test-planted-bridge` in wf-linux-test:local with plain g++: no Android, no engine.
#undef NDEBUG  // the checks below carry side effects
#include "planted_bridge.h"
#include <cassert>
#include <cstdio>
#include <map>
#include <set>

using namespace planted_bridge;

namespace {
struct FakeSink : OverrideSink {
    std::map<std::string, std::string> values;  // key -> value, schema checked on the way in
    uint64_t counter = 0;
    int writes = 0;
    void set(const std::string& schema, const std::string& key, const std::string& value) override {
        assert(schema == kSchema); values[key] = value; ++writes;
    }
    void erase(const std::string& schema, const std::string& key) override {
        assert(schema == kSchema); values.erase(key); ++writes;
    }
    uint64_t applications() const override { return counter; }
    const std::string& at(const char* key) const { auto it = values.find(key); assert(it != values.end()); return it->second; }
    bool has(const char* key) const { return values.count(key) != 0; }
};

struct Harness {
    std::vector<std::string> log;
    uint32_t next = 0;
    Bridge bridge{[this](const std::string& l) { log.push_back(l); }, [this]() { return next++; }};
};

int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)
}

int main() {
    // ---- mix32: documented vectors (also computed independently in Python) ----
    CHECK(mix32(0, 0) == 0x92ca2f0eu);
    CHECK(mix32(0, 1) == 0x3cd6e3f3u);
    CHECK(mix32(713, 0) == 0x101d0edau);
    CHECK(mix32(713, 1) == 0xd121a56bu);
    CHECK(mix32(713, 2) == 0xcb260c1fu);
    CHECK(mix32(713, 3) == 0x331c8c49u);
    CHECK(mix32(4294967295u, 1) == 0xfc2fb9b6u);
    CHECK(mix32(123456789u, 100) == 0x3d3667bbu);
    CHECK(mix32(713, 5) == mix32(713, 5));
    { std::set<uint32_t> seen; for (uint32_t k = 0; k < 1000; ++k) seen.insert(mix32(713, k)); CHECK(seen.size() == 1000); }

    // ---- parseLine: empty line is all defaults ----
    {
        std::vector<std::string> w;
        Params p = parseLine("", &w);
        CHECK(w.empty());
        CHECK(p.water == Water::Random && !p.hasSeed && p.speedIndex == 3 && p.hold == 120);
        CHECK(p.age == "0" && p.textures && p.sway);
    }
    // Every key, in PlantedConfig.toLine() order and spelling.
    {
        std::vector<std::string> w;
        Params p = parseLine("water=saltwater;seed=4294967295;speed=0.25;hold=86400;age=30.5;textures=false;sway=false", &w);
        CHECK(w.empty());
        CHECK(p.water == Water::Salt && p.hasSeed && p.seed == 4294967295u);
        CHECK(p.speedIndex == 1 && p.hold == 86400 && p.age == "30.5" && !p.textures && !p.sway);
    }
    // Speed index mapping, water aliases, seed=random.
    {
        const char* speeds[] = {"0.25", "0.5", "1", "2", "4", "8"};
        for (int i = 0; i < 6; ++i) CHECK(parseLine(std::string("speed=") + speeds[i], nullptr).speedIndex == i + 1);
        CHECK(parseLine("water=fresh", nullptr).water == Water::Fresh);
        CHECK(parseLine("water=salt", nullptr).water == Water::Salt);
        CHECK(parseLine("water=freshwater", nullptr).water == Water::Fresh);
        CHECK(parseLine("water=random", nullptr).water == Water::Random);
        CHECK(!parseLine("seed=random", nullptr).hasSeed);
        Params z = parseLine("seed=0;hold=0;age=0", nullptr);
        CHECK(z.hasSeed && z.seed == 0 && z.hold == 0 && z.age == "0");
    }
    // Defensive: unknown keys, bad values and junk are logged and leave defaults.
    {
        std::vector<std::string> w;
        Params p = parseLine("colour=blue;seed=4294967296;speed=0;speed=3;hold=86401;age=241;age=-1;"
                             "water=lake;textures=maybe;garbage;;seed=12a", &w);
        CHECK(w.size() == 11);
        CHECK(p.water == Water::Random && !p.hasSeed && p.speedIndex == 3 && p.hold == 120);
        CHECK(p.age == "0" && p.textures && p.sway);
        CHECK(w[0].find("unknown key \"colour\"") != std::string::npos);
    }

    // ---- tankFor: fixed seed, random seed, water bit ----
    {
        Params p = parseLine("seed=713", nullptr);
        auto never = []() -> uint32_t { assert(!"random used with a fixed seed"); return 0; };
        Tank t0 = tankFor(p, 0, never), t1 = tankFor(p, 1, never), t2 = tankFor(p, 2, never);
        CHECK(t0.hasSeed && t0.seed == 713);               // tank 0 uses the seed exactly
        CHECK(t1.seed == 0xd121a56bu && t2.seed == 0xcb260c1fu);
        CHECK(t0.water == 0 && t1.water == 1 && t2.water == 1 && tankFor(p, 3, never).water == 0);  // top bit of mix32
        // Replays: the same parameters give the same run.
        for (uint32_t k = 0; k < 50; ++k) {
            Tank a = tankFor(p, k, never), b = tankFor(parseLine("seed=713", nullptr), k, never);
            CHECK(a.seed == b.seed && a.water == b.water);
        }
        // A fixed water type wins over the mix bit.
        CHECK(tankFor(parseLine("seed=713;water=freshwater", nullptr), 1, never).water == 0);
        CHECK(tankFor(parseLine("seed=713;water=saltwater", nullptr), 3, never).water == 1);
    }
    {
        Params p = parseLine("", nullptr);
        uint32_t n = 0;
        auto counter = [&n]() { return n++; };
        Tank a = tankFor(p, 0, counter), b = tankFor(p, 1, counter), c = tankFor(p, 2, counter);
        CHECK(!a.hasSeed && !b.hasSeed && !c.hasSeed);
        CHECK(a.water == 0 && b.water == 1 && c.water == 0 && n == 3);  // bit 0 of the random source
        Params fixed = parseLine("water=saltwater", nullptr);
        CHECK(tankFor(fixed, 7, counter).water == 1 && n == 3);          // fixed water draws nothing
    }

    // ---- Bridge: inert when not configured ----
    {
        Harness h; FakeSink s;
        h.bridge.startFirstTank(s);
        for (int i = 0; i < 5; ++i) { s.counter++; h.bridge.pump(s); }
        CHECK(s.writes == 0 && s.values.empty() && h.log.empty() && !h.bridge.configured());
        // Configured, then reset (nativePrepare): inert again.
        h.bridge.configure("seed=1");
        h.bridge.reset();
        h.bridge.startFirstTank(s);
        h.bridge.pump(s);
        CHECK(s.writes == 0 && h.log.empty());
    }
    // pump() before startFirstTank() does nothing either.
    {
        Harness h; FakeSink s;
        h.bridge.configure("");
        s.counter = 4; h.bridge.pump(s);
        CHECK(s.writes == 0);
    }

    // ---- Bridge: empty line, random seed per tank ----
    {
        Harness h; FakeSink s;
        s.counter = 0;
        h.bridge.configure("");
        CHECK(h.bridge.configured());
        h.bridge.startFirstTank(s);
        CHECK(s.at(kRandomSeed) == "1" && !s.has(kSeed));
        CHECK(s.at(kWater) == "0" && s.at(kSpeed) == "3" && s.at(kHold) == "120");
        CHECK(s.at(kAge) == "0" && s.at(kTextures) == "1" && s.at(kSway) == "1");
        CHECK(h.log.back() == "planted_bridge: tank 0 water=freshwater seed=random speed=1 hold=120");
        // No load yet: nothing changes.
        int writes = s.writes; size_t lines = h.log.size();
        h.bridge.pump(s); h.bridge.pump(s);
        CHECK(s.writes == writes && h.log.size() == lines && h.bridge.pendingTank() == 0);
        // First load (tank 0) applies: set tank 1.
        s.counter = 1; h.bridge.pump(s);
        CHECK(h.bridge.pendingTank() == 1 && s.at(kWater) == "1");
        CHECK(h.log.back() == "planted_bridge: tank 1 water=saltwater seed=random speed=1 hold=120");
        h.bridge.pump(s);
        CHECK(h.bridge.pendingTank() == 1 && h.log.size() == lines + 1);
    }

    // ---- Bridge: fixed seed, counter state machine (first load, jump by 2, no change) ----
    {
        Harness h; FakeSink s;
        s.counter = 7;                      // a prior registry load in this process
        s.values[kSeed] = "stale";
        h.bridge.configure("water=random;seed=713;speed=8;hold=5;age=12.5;textures=false;sway=true");
        h.bridge.startFirstTank(s);
        CHECK(s.at(kRandomSeed) == "0" && s.at(kSeed) == "713" && s.at(kWater) == "0");
        CHECK(s.at(kSpeed) == "6" && s.at(kHold) == "5" && s.at(kAge) == "12.5");
        CHECK(s.at(kTextures) == "0" && s.at(kSway) == "1");
        CHECK(h.log.back() == "planted_bridge: tank 0 water=freshwater seed=713 speed=8 hold=5");
        s.counter = 8; h.bridge.pump(s);    // tank 0 loaded
        CHECK(h.bridge.pendingTank() == 1 && s.at(kSeed) == std::to_string(0xd121a56bu) && s.at(kWater) == "1");
        s.counter = 10; h.bridge.pump(s);   // two loads in one pump: tanks 1 and 2 loaded, set 3 only
        CHECK(h.bridge.pendingTank() == 3 && s.at(kSeed) == std::to_string(0x331c8c49u) && s.at(kWater) == "0");
        size_t lines = h.log.size();
        h.bridge.pump(s);                   // no change
        CHECK(h.log.size() == lines && h.bridge.pendingTank() == 3);
        CHECK(h.log.back() == "planted_bridge: tank 3 water=freshwater seed=857508937 speed=8 hold=5");
        // Configured but random seed after a fixed one (new run): the stale Seed override goes.
        h.bridge.reset(); h.bridge.configure("water=saltwater");
        h.bridge.startFirstTank(s);
        CHECK(!s.has(kSeed) && s.at(kRandomSeed) == "1" && s.at(kWater) == "1");
    }

    // ---- Bridge: a bad key is logged at configure, the run still goes ----
    {
        Harness h; FakeSink s;
        h.bridge.configure("seed=9;cycles=3");
        CHECK(h.log.size() == 1 && h.log[0] == "planted_bridge: ignored unknown key \"cycles\"");
        h.bridge.startFirstTank(s);
        CHECK(s.at(kSeed) == "9");
    }

    std::printf("planted_bridge_test: %d checks passed\n", checks);
    return 0;
}
