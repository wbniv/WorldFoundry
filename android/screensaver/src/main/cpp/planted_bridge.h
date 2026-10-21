// Planted Tank screensaver host bridge (docs/plans/2026-10-21-planted-tank-screensaver.md,
// Phase 2b). Turns the validated parameter line from PlantedConfig.toLine() into engine launch
// overrides (wfprops::launchOverrides(), schema PlantedTankSettings), tank after tank.
//
// Pure logic only: no Android and no engine includes, so tests/planted_bridge_test.cpp builds it
// with plain g++. The engine adapter (an OverrideSink over wfprops::launchOverrides()) lives in
// dream_host.cc.
//
// Lifecycle, all on the player thread (TankPlayer: nativePrepare, then on the thread
// nativeConfigure and nativeRun):
//   reset()            nativePrepare: unconfigured, inert.
//   configure(line)    nativeConfigure: stores the line; "" is a configured run with defaults.
//   startFirstTank()   nativeRun, before HALStart: sets tank 0's overrides.
//   pump()             WFAndroidPumpEvents, every frame: when the sink's applications() counter
//                      rises, a level registry has just loaded tank k, so set tank k+1's values
//                      (the engine applies them at the next load only).
// When configure() was never called every call is a no-op: the Aquarium and Seahorse flavors
// behave exactly as before.
#pragma once
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace planted_bridge {

constexpr const char* kSchema = "PlantedTankSettings";

// Field keys, exactly as the level's settings.oas names them.
constexpr const char* kSeed = "Seed";
constexpr const char* kRandomSeed = "Random seed on entry";
constexpr const char* kWater = "Water type";
constexpr const char* kSpeed = "Growth speed";
constexpr const char* kAge = "Initial age";
constexpr const char* kTextures = "Textures";
constexpr const char* kSway = "Sway";
constexpr const char* kHold = "Hold seconds";

// 32-bit mix of (seed, k), splitmix32 style: a Weyl step seed + 0x9E3779B9 * (k + 1), then the
// MurmurHash3 fmix32 finaliser (xorshift 16, * 0x85EBCA6B, xorshift 13, * 0xC2B2AE35,
// xorshift 16). Test vectors are in tests/planted_bridge_test.cpp.
uint32_t mix32(uint32_t seed, uint32_t k);

enum class Water { Random = -1, Fresh = 0, Salt = 1 };

struct Params {
    Water water = Water::Random;
    bool hasSeed = false;
    uint32_t seed = 0;
    int speedIndex = 3;       // engine index into paused,0.25,0.5,1,2,4,8; default 1x
    uint32_t hold = 120;      // seconds, 0..86400
    std::string age = "0";    // seconds, 0..240, as decimal text
    bool textures = true;
    bool sway = true;
};

// Parses "key=value;key=value". Unknown keys and bad values are ignored with a line appended to
// `warnings` (when non-null); the default stays in force for that key.
Params parseLine(const std::string& line, std::vector<std::string>* warnings);

// One tank's overrides, derived from the run's parameters.
struct Tank {
    uint32_t index = 0;
    bool hasSeed = false;     // false: the engine draws a fresh seed (Random seed on entry = 1)
    uint32_t seed = 0;
    int water = 0;            // 0 freshwater, 1 saltwater
};

// Tank k of a run: with a seed, tank 0 uses it exactly and tank k>0 uses mix32(seed, k); with
// water=random and a seed, water is the top bit of mix32(seed, k), so the run replays; with
// water=random and no seed, water is bit 0 of `random()`.
Tank tankFor(const Params& params, uint32_t k, const std::function<uint32_t()>& random);

class OverrideSink {
public:
    virtual ~OverrideSink() = default;
    virtual void set(const std::string& schema, const std::string& key, const std::string& value) = 0;
    virtual void erase(const std::string& schema, const std::string& key) = 0;
    virtual uint64_t applications() const = 0;
};

class Bridge {
public:
    using Log = std::function<void(const std::string&)>;
    using Random = std::function<uint32_t()>;
    // Defaults: log to stderr, random from the steady clock mixed with a call counter.
    Bridge();
    Bridge(Log log, Random random);

    void reset();
    void configure(const std::string& line);
    bool configured() const { return configured_; }
    const Params& params() const { return params_; }

    // Sets tank 0's overrides and records the sink's counter. No-op when not configured.
    void startFirstTank(OverrideSink& sink);
    // Per frame. No-op when not configured or startFirstTank() has not run.
    void pump(OverrideSink& sink);

    // Index of the tank whose overrides are currently set (the next tank to load).
    uint32_t pendingTank() const { return pending_; }

private:
    void setTank(OverrideSink& sink, uint32_t k);

    Log log_;
    Random random_;
    bool configured_ = false;
    bool started_ = false;
    std::string line_;
    Params params_;
    uint64_t base_ = 0;       // sink counter when tank 0 was set
    uint64_t seen_ = 0;       // last counter value acted on
    uint32_t pending_ = 0;
};

}  // namespace planted_bridge
