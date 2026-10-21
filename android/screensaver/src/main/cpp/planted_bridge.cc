// Planted Tank screensaver host bridge: see planted_bridge.h. No Android or engine includes.
#include "planted_bridge.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <utility>

namespace planted_bridge {

uint32_t mix32(uint32_t seed, uint32_t k) {
    uint32_t z = seed + 0x9E3779B9u * (k + 1u);
    z = (z ^ (z >> 16)) * 0x85EBCA6Bu;
    z = (z ^ (z >> 13)) * 0xC2B2AE35u;
    return z ^ (z >> 16);
}

namespace {

std::string trim(const std::string& text) {
    size_t begin = 0, end = text.size();
    while (begin < end && (text[begin] == ' ' || text[begin] == '\t')) ++begin;
    while (end > begin && (text[end - 1] == ' ' || text[end - 1] == '\t')) --end;
    return text.substr(begin, end - begin);
}

bool allDigits(const std::string& text) {
    if (text.empty()) return false;
    for (char c : text) if (c < '0' || c > '9') return false;
    return true;
}

// A whole number 0..max, digits only.
bool parseWhole(const std::string& text, uint64_t max, uint64_t& out) {
    if (!allDigits(text) || text.size() > 19) return false;
    uint64_t value = 0;
    for (char c : text) value = value * 10 + uint64_t(c - '0');
    if (value > max) return false;
    out = value;
    return true;
}

// A plain decimal ("1", "0.25", "30.5"): digits, optionally one '.' and more digits.
bool parseDecimal(const std::string& text, double& out) {
    size_t dot = text.find('.');
    std::string whole = dot == std::string::npos ? text : text.substr(0, dot);
    if (!allDigits(whole)) return false;
    if (dot != std::string::npos && !allDigits(text.substr(dot + 1))) return false;
    char* end = nullptr;
    double value = std::strtod(text.c_str(), &end);
    if (!end || *end || !std::isfinite(value)) return false;
    out = value;
    return true;
}

bool parseBool(const std::string& text, bool& out) {
    if (text == "true" || text == "1") { out = true; return true; }
    if (text == "false" || text == "0") { out = false; return true; }
    return false;
}

const char* waterName(int water) { return water ? "saltwater" : "freshwater"; }

const char* speedName(int index) {
    static const char* const names[] = {"paused", "0.25", "0.5", "1", "2", "4", "8"};
    return index >= 0 && index <= 6 ? names[index] : "?";
}

uint32_t clockRandom() {
    static uint32_t calls = 0;
    uint64_t ticks = uint64_t(std::chrono::steady_clock::now().time_since_epoch().count());
    return mix32(uint32_t(ticks) ^ uint32_t(ticks >> 32), ++calls);
}

}  // namespace

Params parseLine(const std::string& line, std::vector<std::string>* warnings) {
    Params p;
    auto warn = [&](const std::string& text) { if (warnings) warnings->push_back(text); };
    size_t start = 0;
    while (start <= line.size()) {
        size_t stop = line.find(';', start);
        if (stop == std::string::npos) stop = line.size();
        std::string pair = trim(line.substr(start, stop - start));
        start = stop + 1;
        if (pair.empty()) continue;
        size_t eq = pair.find('=');
        if (eq == std::string::npos) { warn("ignored \"" + pair + "\": no '='"); continue; }
        std::string key = trim(pair.substr(0, eq)), value = trim(pair.substr(eq + 1));
        auto bad = [&]() { warn("ignored " + key + "=" + value + ": invalid value"); };
        if (key == "water") {
            if (value == "freshwater" || value == "fresh") p.water = Water::Fresh;
            else if (value == "saltwater" || value == "salt") p.water = Water::Salt;
            else if (value == "random") p.water = Water::Random;
            else bad();
        } else if (key == "seed") {
            uint64_t seed = 0;
            if (value == "random") p.hasSeed = false;
            else if (parseWhole(value, 4294967295ull, seed)) { p.hasSeed = true; p.seed = uint32_t(seed); }
            else bad();
        } else if (key == "speed") {
            static const double speeds[] = {0.25, 0.5, 1, 2, 4, 8};
            double speed = 0;
            int index = -1;
            if (parseDecimal(value, speed))
                for (int i = 0; i < 6; ++i) if (speed == speeds[i]) index = i + 1;
            if (index > 0) p.speedIndex = index; else bad();
        } else if (key == "hold") {
            uint64_t hold = 0;
            if (parseWhole(value, 86400, hold)) p.hold = uint32_t(hold); else bad();
        } else if (key == "age") {
            double age = 0;
            if (parseDecimal(value, age) && age >= 0 && age <= 240) p.age = value; else bad();
        } else if (key == "textures") {
            if (!parseBool(value, p.textures)) bad();
        } else if (key == "sway") {
            if (!parseBool(value, p.sway)) bad();
        } else {
            warn("ignored unknown key \"" + key + "\"");
        }
    }
    return p;
}

Tank tankFor(const Params& params, uint32_t k, const std::function<uint32_t()>& random) {
    Tank t;
    t.index = k;
    t.hasSeed = params.hasSeed;
    if (params.hasSeed) t.seed = k == 0 ? params.seed : mix32(params.seed, k);
    if (params.water == Water::Fresh) t.water = 0;
    else if (params.water == Water::Salt) t.water = 1;
    else if (params.hasSeed) t.water = int(mix32(params.seed, k) >> 31);
    else t.water = int((random ? random() : clockRandom()) & 1u);
    return t;
}

Bridge::Bridge()
    : Bridge([](const std::string& line) { std::fprintf(stderr, "%s\n", line.c_str()); }, nullptr) {}

Bridge::Bridge(Log log, Random random) : log_(std::move(log)), random_(std::move(random)) {
    if (!random_) random_ = clockRandom;
}

void Bridge::reset() {
    configured_ = false;
    started_ = false;
    line_.clear();
    params_ = Params{};
    base_ = seen_ = 0;
    pending_ = 0;
}

void Bridge::configure(const std::string& line) {
    reset();
    configured_ = true;
    line_ = line;
    std::vector<std::string> warnings;
    params_ = parseLine(line, &warnings);
    for (const auto& w : warnings) log_("planted_bridge: " + w);
}

void Bridge::setTank(OverrideSink& sink, uint32_t k) {
    Tank t = tankFor(params_, k, random_);
    if (t.hasSeed) {
        sink.set(kSchema, kRandomSeed, "0");
        sink.set(kSchema, kSeed, std::to_string(t.seed));
    } else {
        sink.set(kSchema, kRandomSeed, "1");
        sink.erase(kSchema, kSeed);
    }
    sink.set(kSchema, kWater, std::to_string(t.water));
    sink.set(kSchema, kSpeed, std::to_string(params_.speedIndex));
    sink.set(kSchema, kHold, std::to_string(params_.hold));
    sink.set(kSchema, kAge, params_.age);
    sink.set(kSchema, kTextures, params_.textures ? "1" : "0");
    sink.set(kSchema, kSway, params_.sway ? "1" : "0");
    pending_ = k;
    log_("planted_bridge: tank " + std::to_string(k) + " water=" + waterName(t.water) +
         " seed=" + (t.hasSeed ? std::to_string(t.seed) : std::string("random")) +
         " speed=" + speedName(params_.speedIndex) + " hold=" + std::to_string(params_.hold));
}

void Bridge::startFirstTank(OverrideSink& sink) {
    if (!configured_) return;
    base_ = seen_ = sink.applications();
    started_ = true;
    log_("planted_bridge: configured \"" + line_ + "\"");
    setTank(sink, 0);
}

void Bridge::pump(OverrideSink& sink) {
    if (!configured_ || !started_) return;
    uint64_t now = sink.applications();
    if (now <= seen_) return;
    seen_ = now;
    // The (now - base_)th load since tank 0 was set has just applied: that was tank now-base_-1.
    setTank(sink, uint32_t(now - base_));
}

}  // namespace planted_bridge
