#pragma once
// Included once by Android's GL display translation unit after EGL/GLES headers.
#include "gpu_profile.hpp"
#include <GLES2/gl2ext.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <map>
#include <vector>

namespace wf_gpu {
namespace {
constexpr unsigned kQueryCount = 256;
struct Window {
    long long start = 0, end = 0;
    std::vector<double> gpu, wall, cpu, swap;
    unsigned issued = 0, invalid = 0, full = 0, missing = 0;
};
struct Query {
    GLuint id = 0;
    bool pending = false;
    unsigned long frame = 0;
    long long window = 0, submitted = 0;
};
struct State {
    bool enabled = false, initialized = false, supported = false;
    unsigned long frame = 0;
    long long epoch = 0, currentWindow = 0;
    double frameWall = 0, frameCpu = 0;
    int active = -1;
    std::array<Query, kQueryCount> queries{};
    std::map<long long, Window> windows;
    PFNGLGENQUERIESEXTPROC gen = nullptr;
    PFNGLDELETEQUERIESEXTPROC del = nullptr;
    PFNGLBEGINQUERYEXTPROC begin = nullptr;
    PFNGLENDQUERYEXTPROC end = nullptr;
    PFNGLGETQUERYIVEXTPROC info = nullptr;
    PFNGLGETQUERYOBJECTUIVEXTPROC available = nullptr;
    PFNGLGETQUERYOBJECTUI64VEXTPROC result = nullptr;
};
State state;

long long nowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
double cpuMs() {
    timespec t{};
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}
bool hasExtension(const char* name) {
    GLint count = 0;
    glGetIntegerv(GL_NUM_EXTENSIONS, &count);
    for (int i = 0; i < count; ++i) {
        const char* candidate = reinterpret_cast<const char*>(glGetStringi(GL_EXTENSIONS, i));
        if (candidate && !std::strcmp(candidate, name)) return true;
    }
    return false;
}
void initialize() {
    state.initialized = true;
    state.gen = reinterpret_cast<PFNGLGENQUERIESEXTPROC>(eglGetProcAddress("glGenQueriesEXT"));
    state.del = reinterpret_cast<PFNGLDELETEQUERIESEXTPROC>(eglGetProcAddress("glDeleteQueriesEXT"));
    state.begin = reinterpret_cast<PFNGLBEGINQUERYEXTPROC>(eglGetProcAddress("glBeginQueryEXT"));
    state.end = reinterpret_cast<PFNGLENDQUERYEXTPROC>(eglGetProcAddress("glEndQueryEXT"));
    state.info = reinterpret_cast<PFNGLGETQUERYIVEXTPROC>(eglGetProcAddress("glGetQueryivEXT"));
    state.available = reinterpret_cast<PFNGLGETQUERYOBJECTUIVEXTPROC>(eglGetProcAddress("glGetQueryObjectuivEXT"));
    state.result = reinterpret_cast<PFNGLGETQUERYOBJECTUI64VEXTPROC>(eglGetProcAddress("glGetQueryObjectui64vEXT"));
    GLint bits = 0;
    state.supported = hasExtension("GL_EXT_disjoint_timer_query") && state.gen && state.del &&
        state.begin && state.end && state.info && state.available && state.result;
    if (state.supported) {
        state.info(GL_TIME_ELAPSED_EXT, GL_QUERY_COUNTER_BITS_EXT, &bits);
        state.supported = bits >= 30;
    }
    std::fprintf(stderr, "gpu-capability: supported=%d counter-bits=%d vendor=%s renderer=%s version=%s\n",
        int(state.supported), bits, glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION));
    if (state.supported) {
        GLuint ids[kQueryCount];
        state.gen(kQueryCount, ids);
        for (unsigned i = 0; i < kQueryCount; ++i) state.queries[i].id = ids[i];
    }
}
void invalidate() {
    for (auto& q : state.queries) if (q.pending) {
        ++state.windows[q.window].invalid;
        q.pending = false;
    }
}
void poll() {
    if (!state.supported) return;
    GLint disjoint = 0;
    glGetIntegerv(GL_GPU_DISJOINT_EXT, &disjoint);
    if (disjoint) { invalidate(); return; }
    struct Sample { long long window; double ms; };
    std::vector<Sample> samples;
    for (auto& q : state.queries) if (q.pending) {
        GLuint ready = 0;
        state.available(q.id, GL_QUERY_RESULT_AVAILABLE_EXT, &ready);
        if (ready) {
            GLuint64EXT ns = 0;
            state.result(q.id, GL_QUERY_RESULT_EXT, &ns);
            const long long age = nowNs() - q.submitted;
            if (ns > GLuint64EXT(std::max(0LL, age) + 1000000LL))
                ++state.windows[q.window].invalid;
            else samples.push_back({q.window, double(ns) / 1e6});
            q.pending = false;
        } else if (state.frame - q.frame > 240) {
            ++state.windows[q.window].missing;
            q.pending = false;
        }
    }
    glGetIntegerv(GL_GPU_DISJOINT_EXT, &disjoint);
    if (disjoint) {
        invalidate();
        for (const auto& sample : samples) ++state.windows[sample.window].invalid;
    } else {
        for (const auto& sample : samples) state.windows[sample.window].gpu.push_back(sample.ms);
    }
}
void metric(const char* name, std::vector<double> values) {
    if (values.empty()) {
        std::fprintf(stderr, "gpu-metric: %s samples=0\n", name);
        return;
    }
    std::sort(values.begin(), values.end());
    double sum = 0;
    for (double value : values) sum += value;
    std::fprintf(stderr, "gpu-metric: %s samples=%zu mean=%.4f p50=%.4f p95=%.4f max=%.4f ms\n",
        name, values.size(), sum / values.size(), values[values.size() / 2],
        values[(values.size() - 1) * 95 / 100], values.back());
}
void emit(long long id, Window& window) {
    std::fprintf(stderr,
        "gpu-window: id=%lld start-ns=%lld end-ns=%lld supported=%d issued=%u invalid=%u ring-full=%u missing=%u\n",
        id, window.start, window.end, int(state.supported), window.issued, window.invalid,
        window.full, window.missing);
    metric("elapsed", window.gpu);
    metric("frame-wall", window.wall);
    metric("frame-cpu", window.cpu);
    metric("swap-wall", window.swap);
}
} // namespace

double wallMs() { return double(nowNs()) / 1e6; }
void enable() { state.enabled = true; }
bool enabled() { return state.enabled; }
void beginFrame() {
    if (!state.enabled) return;
    const long long now = nowNs();
    if (!state.epoch) state.epoch = now;
    state.currentWindow = (now - state.epoch) / 5000000000LL;
    auto& window = state.windows[state.currentWindow];
    if (!window.start) {
        window.start = state.epoch + state.currentWindow * 5000000000LL;
        window.end = window.start + 5000000000LL;
    }
    ++state.frame;
    state.frameWall = double(now) / 1e6;
    state.frameCpu = cpuMs();
}
void beginGpu(int width, int height) {
    if (!state.enabled || !state.epoch) return;
    if (!state.initialized) {
        initialize();
        std::fprintf(stderr, "gpu-surface: viewport=%dx%d\n", width, height);
    }
    poll();
    if (!state.supported || state.active >= 0) return;
    for (unsigned i = 0; i < kQueryCount; ++i) if (!state.queries[i].pending) {
        auto& q = state.queries[i];
        q.frame = state.frame;
        q.window = state.currentWindow;
        q.submitted = nowNs();
        state.begin(GL_TIME_ELAPSED_EXT, q.id);
        state.active = int(i);
        ++state.windows[q.window].issued;
        return;
    }
    ++state.windows[state.currentWindow].full;
}
void endGpu() {
    if (state.enabled && state.active >= 0) {
        state.end(GL_TIME_ELAPSED_EXT);
        state.queries[state.active].pending = true;
        state.active = -1;
    }
}
void swapSample(double ms) {
    if (state.enabled && state.epoch) state.windows[state.currentWindow].swap.push_back(ms);
}
void endFrame() {
    if (!state.enabled || !state.epoch) return;
    // Editor frames may render without swapping; never carry an active query
    // into the next frame.
    endGpu();
    auto& window = state.windows[state.currentWindow];
    window.wall.push_back(wallMs() - state.frameWall);
    window.cpu.push_back(cpuMs() - state.frameCpu);
    for (auto it = state.windows.begin(); it != state.windows.end() && it->first + 2 <= state.currentWindow;) {
        for (auto& q : state.queries) if (q.pending && q.window == it->first) {
            ++it->second.missing;
            q.pending = false;
        }
        emit(it->first, it->second);
        it = state.windows.erase(it);
    }
}
void reset(bool contextLost) {
    if (!state.enabled) return;
    if (state.active >= 0 && !contextLost) state.end(GL_TIME_ELAPSED_EXT);
    invalidate();
    if (!contextLost && state.del) for (auto& q : state.queries) if (q.id) state.del(1, &q.id);
    for (auto& entry : state.windows) emit(entry.first, entry.second);
    const bool enabled = state.enabled;
    state = State{};
    state.enabled = enabled;
}
}
