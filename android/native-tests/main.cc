// WF Native Tests: a NativeActivity that runs a fixed suite of native test programs and writes their
// output to <external files>/wf.log, which the chromecast coordinator's `check` workflow returns as
// evidence (it saves the last 4 MB of that file). Plan: docs/plans/2026-11-26-device-native-test-route.md.
//
// Each test is an existing program's main() compiled into this library under its own name
// (-Dmain=...), so the source is the same file the PC and WebAssembly targets build. stdout and
// stderr point at wf.log for the whole run; a test that reads stdin gets a file the build generated.
// The framing lines are what scripts/device_native_tests.py `collect` checks and splits:
//
//   === wf-native-tests <version> start abi=<abi>
//   === begin <test>
//   ... the test's own output ...
//   === end <test> rc=<n> ms=<elapsed>
//   === wf-native-tests done tests=<n> failed=<m>
//
// The window is one colour: amber while running, green when every test returned 0, red otherwise,
// with a strip along the bottom that grows per finished test, so the job's screenshot states the outcome.
#include <android/log.h>
#include <android/native_window.h>
#include <android/window.h>
#include <android_native_app_glue.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

int wf_nt_cpuinfo();                                  // cpuinfo.cc
int wf_nt_fmaf_probe();                               // fmaf_probe.cc
int wf_nt_forth_math_dump_main();                     // tests/forth_math_dump.cpp
int wf_nt_forth_math_vm_cost_main(int, char**);       // the HOST in tests/forth_math_vm_cost.py

#include "suite_inputs.inc"                           // generated: kVmCostBootstrap, kVmCostRequests

namespace {

constexpr int kSuiteVersion = 2;
constexpr const char* kTag = "WFNativeTests";

#if defined(__aarch64__)
constexpr const char* kAbi = "arm64-v8a";
#elif defined(__arm__)
constexpr const char* kAbi = "armeabi-v7a";
#else
constexpr const char* kAbi = "unknown";
#endif

std::string g_internal;                               // app-private scratch for generated inputs

bool write_file(const std::string& path, const unsigned char* data, size_t size)
{
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    const bool ok = std::fwrite(data, 1, size, f) == size;
    return std::fclose(f) == 0 && ok;
}

int run_cpuinfo() { return wf_nt_cpuinfo(); }
int run_forth_math_dump() { return wf_nt_forth_math_dump_main(); }
int run_fmaf_probe() { return wf_nt_fmaf_probe(); }

int run_forth_math_vm_cost()
{
    const std::string boot = g_internal + "/vm-cost-bootstrap.fth";
    const std::string reqs = g_internal + "/vm-cost-requests.txt";
    if (!write_file(boot, kVmCostBootstrap, sizeof kVmCostBootstrap) ||
        !write_file(reqs, kVmCostRequests, sizeof kVmCostRequests)) {
        std::printf("cannot write the generated inputs under %s: %s\n", g_internal.c_str(), std::strerror(errno));
        return 2;
    }
    if (!std::freopen(reqs.c_str(), "r", stdin)) {
        std::printf("cannot open %s as stdin: %s\n", reqs.c_str(), std::strerror(errno));
        return 2;
    }
    char arg0[] = "forth-math-vm-cost";
    std::string arg1 = boot;
    char* argv[] = {arg0, arg1.data(), nullptr};
    return wf_nt_forth_math_vm_cost_main(2, argv);
}

struct Test {
    const char* name;
    int (*run)();
};
const Test kTests[] = {
    {"cpuinfo", run_cpuinfo},
    {"forth-math-dump", run_forth_math_dump},
    {"forth-math-vm-cost", run_forth_math_vm_cost},
    {"fmaf-probe", run_fmaf_probe},
};
constexpr int kCount = sizeof kTests / sizeof kTests[0];

std::atomic<int> g_finished{0};
std::atomic<int> g_failed{0};
std::atomic<bool> g_done{false};
std::atomic<bool> g_started{false};                   // once per process, across activity restarts

void suite(std::string wf_log)
{
    if (!std::freopen(wf_log.c_str(), "w", stdout)) {
        __android_log_print(ANDROID_LOG_ERROR, kTag, "cannot open %s: %s", wf_log.c_str(), std::strerror(errno));
        g_failed = kCount;
        g_done = true;
        return;
    }
    std::freopen(wf_log.c_str(), "a", stderr);
    static char buffer[1 << 16];
    std::setvbuf(stdout, buffer, _IOFBF, sizeof buffer);
    std::printf("=== wf-native-tests %d start abi=%s\n", kSuiteVersion, kAbi);
    std::fflush(stdout);
    __android_log_print(ANDROID_LOG_INFO, kTag, "start version=%d abi=%s log=%s", kSuiteVersion, kAbi, wf_log.c_str());
    for (const Test& t : kTests) {
        std::printf("=== begin %s\n", t.name);
        std::fflush(stdout);
        const auto t0 = std::chrono::steady_clock::now();
        const int rc = t.run();
        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
        std::fflush(stdout);
        std::printf("=== end %s rc=%d ms=%lld\n", t.name, rc, (long long)ms);
        std::fflush(stdout);
        __android_log_print(rc ? ANDROID_LOG_ERROR : ANDROID_LOG_INFO, kTag, "end %s rc=%d ms=%lld", t.name, rc, (long long)ms);
        if (rc) ++g_failed;
        ++g_finished;
    }
    std::printf("=== wf-native-tests done tests=%d failed=%d\n", kCount, g_failed.load());
    std::fflush(stdout);
    __android_log_print(ANDROID_LOG_INFO, kTag, "done tests=%d failed=%d", kCount, g_failed.load());
    g_done = true;
}

void paint(ANativeWindow* window)
{
    if (!window) return;
    ANativeWindow_setBuffersGeometry(window, 0, 0, WINDOW_FORMAT_RGBX_8888);
    ANativeWindow_Buffer b;
    if (ANativeWindow_lock(window, &b, nullptr) != 0) return;
    const bool done = g_done.load();
    const uint32_t colour = !done ? 0xFF1F79B7u                 // ABGR in memory order R,G,B,X: amber
                          : g_failed.load() ? 0xFF3030C5u        // red
                                            : 0xFF5A852Fu;       // green
    const uint32_t strip = 0xFFDDDDDDu;
    const int strip_h = b.height / 24;
    const int strip_w = b.width * g_finished.load() / kCount;
    auto* px = static_cast<uint32_t*>(b.bits);
    for (int y = 0; y < b.height; ++y) {
        uint32_t* row = px + (size_t)y * b.stride;
        const bool in_strip = y >= b.height - strip_h;
        for (int x = 0; x < b.width; ++x) row[x] = (in_strip && x < strip_w) ? strip : colour;
    }
    ANativeWindow_unlockAndPost(window);
}

void on_cmd(android_app* app, int32_t cmd)
{
    if (cmd == APP_CMD_INIT_WINDOW || cmd == APP_CMD_WINDOW_REDRAW_NEEDED || cmd == APP_CMD_CONFIG_CHANGED)
        paint(app->window);
}

}  // namespace

void android_main(android_app* app)
{
    app->onAppCmd = on_cmd;
    ANativeActivity_setWindowFlags(app->activity, AWINDOW_FLAG_KEEP_SCREEN_ON | AWINDOW_FLAG_FULLSCREEN, 0);
    if (!g_started.exchange(true)) {
        const char* external = app->activity->externalDataPath;
        g_internal = app->activity->internalDataPath ? app->activity->internalDataPath : "";
        if (!external || !*external || g_internal.empty()) {
            __android_log_print(ANDROID_LOG_ERROR, kTag, "no external or internal data path; nothing to write to");
            g_failed = kCount;
            g_done = true;
        } else {
            std::thread(suite, std::string(external) + "/wf.log").detach();
        }
    }
    int painted_finished = -1;
    bool painted_done = false;
    while (!app->destroyRequested) {
        int events;
        android_poll_source* source;
        if (ALooper_pollOnce(100, nullptr, &events, reinterpret_cast<void**>(&source)) >= 0 && source)
            source->process(app, source);
        if (g_finished.load() != painted_finished || g_done.load() != painted_done) {
            painted_finished = g_finished.load();
            painted_done = g_done.load();
            paint(app->window);
        }
    }
}
