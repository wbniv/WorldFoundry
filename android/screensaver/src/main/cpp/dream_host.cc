#include <android/asset_manager_jni.h>
#include <android/native_window_jni.h>
#include <jni.h>
#include <android/log.h>

#include <atomic>
#include <cstdio>
#include <cstdint>
#include <fcntl.h>
#include <string>
#include <thread>
#include <unistd.h>

#include <hal/hal.h>
#include <hal/android/touch_controls.h>
#include <game/level_menu.h>
#include <hal/phonepad/phonepad_overlay.h>
#include <pigsys/pigsys.hp>
#include <runtime_properties.hpp>

#include "planted_bridge.h"

extern "C" bool WFAndroidEglInit(ANativeWindow* window);
extern "C" void WFAndroidEglTerm();
extern "C" void WFAndroidSetHudEnabled(int enabled);

namespace {
std::atomic<bool> closing{false};
std::atomic<bool> windowReady{false};
AAssetManager* assets = nullptr;

// Planted Tank parameters (planted_bridge.h). Unconfigured, and so inert, for the Aquarium and
// Seahorse flavors, which never call nativeConfigure.
planted_bridge::Bridge plantedBridge;

// The engine's launch-override table, as the bridge sees it.
struct LaunchOverrideSink final : planted_bridge::OverrideSink {
    void set(const std::string& schema, const std::string& key, const std::string& value) override {
        wfprops::launchOverrides().set(schema, key, value);
    }
    void erase(const std::string& schema, const std::string& key) override {
        wfprops::launchOverrides().erase(schema, key);
    }
    uint64_t applications() const override { return wfprops::launchOverrides().applications(); }
};
LaunchOverrideSink launchOverrideSink;

void logLine(FILE* file, const std::string& line) {
    if (file) {
        std::fwrite(line.data(), 1, line.size(), file);
        std::fputc('\n', file);
        std::fflush(file);
    }
    __android_log_write(ANDROID_LOG_INFO, "wf_dream", line.c_str());
}

void bridgeEngineLog(const char* path) {
    int fds[2];
    if (pipe(fds) != 0) return;
    int fileFd = path ? open(path, O_WRONLY | O_CREAT | O_APPEND, 0644) : -1;
    dup2(fds[1], STDOUT_FILENO);
    dup2(fds[1], STDERR_FILENO);
    close(fds[1]);
    std::setvbuf(stdout, nullptr, _IOLBF, 0);
    std::setvbuf(stderr, nullptr, _IOLBF, 0);
    std::thread([readFd = fds[0], fileFd]() {
        FILE* file = fileFd >= 0 ? fdopen(fileFd, "a") : nullptr;
        std::string line;
        char buffer[1024];
        for (ssize_t size; (size = read(readFd, buffer, sizeof(buffer))) > 0;) {
            for (ssize_t i = 0; i < size; ++i) {
                if (buffer[i] == '\n') {
                    logLine(file, line);
                    line.clear();
                } else if (line.size() < 2048) {
                    line.push_back(buffer[i]);
                }
            }
        }
        if (!line.empty()) logLine(file, line);
        if (file) std::fclose(file);
        close(readFd);
    }).detach();
}
}

extern "C" AAssetManager* WFAndroidGetAssetManager() { return assets; }
extern "C" int WFAndroidHasWindow() { return windowReady.load() ? 1 : 0; }
extern "C" int WFAndroidCloseRequested() { return closing.load() ? 1 : 0; }
extern "C" void WFAndroidRequestClose() { closing.store(true); }
// Runs on the game thread once per frame. A Dream is passive: the engine's overlay (the planted
// tank's seed strip, its settings panel, the level menu) must never draw. The engine draws all of
// it through levelmenu::Drawer(), which Display installs once at start-up, so clear it every frame
// rather than editing the engine. Without a drawer the level menu starts level 0 (game.cc).
extern "C" void WFAndroidPumpEvents() {
    if (levelmenu::Drawer()) levelmenu::SetDrawer(nullptr);
    plantedBridge.pump(launchOverrideSink);
}
extern "C" void WFAndroidTouchLayout(int, int, androidtouch::Layout* layout,
                                       uint32_t* held, float* x, float* y) {
    *layout = androidtouch::Layout{};
    *held = 0;
    *x = *y = 0;
}
extern "C" int WFAndroidPhoneOverlayRects(int, int, const PhonepadRect** rects,
                                            int* changed, const bitmaptext::Quad** glyphs,
                                            int* glyphCount) {
    *rects = nullptr;
    *changed = 0;
    *glyphs = nullptr;
    *glyphCount = 0;
    return 0;
}

extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativePrepare(JNIEnv*, jclass) {
    closing.store(false);
    plantedBridge.reset();
}

// Called on the player thread before nativeRun, Planted flavor only, with PlantedConfig.toLine().
extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeConfigure(JNIEnv* env, jclass, jstring line) {
    std::string text;
    if (line) {
        const char* chars = env->GetStringUTFChars(line, nullptr);
        if (chars) {
            text = chars;
            env->ReleaseStringUTFChars(line, chars);
        }
    }
    plantedBridge.configure(text);
}

extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeStop(JNIEnv*, jclass) {
    closing.store(true);
}

extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeRun(
        JNIEnv* env, jclass, jobject manager, jobject surface, jint level, jstring logPath) {
    if (level < 0 || level > 8) return;
    if (logPath) {
        const char* path = env->GetStringUTFChars(logPath, nullptr);
        if (path) {
            bridgeEngineLog(path);
            env->ReleaseStringUTFChars(logPath, path);
        }
    }
    std::fprintf(stderr, "\n=== wf_dream start level %d ===\n", int(level));
    __android_log_print(ANDROID_LOG_INFO, "wf_dream", "start level %d", int(level));
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    if (!window) return;
    assets = AAssetManager_fromJava(env, manager);
    WFAndroidSetHudEnabled(0);
    if (WFAndroidEglInit(window)) {
        windowReady.store(true);
        // The positional argument selects the same TOC index as TankChoice.IDS.
        char arg0[] = "wf_dream";
        char arg1[] = "0";
        arg1[0] = static_cast<char>('0' + level);
        char slotWidth[] = "--vram-slot-width=1024";
        char slotHeight[] = "--vram-slot-height=1024";
        char permWidth[] = "--vram-perm-width=1024";
        char permHeight[] = "--vram-perm-height=1024";
        char vramHeight[] = "--vram-height=1024";
        char noFps[] = "--no-fps";
        char* argv[] = {arg0, slotWidth, slotHeight, permWidth, permHeight, vramHeight, noFps, arg1, nullptr};
        __argc = 8;
        __argv = argv;
        // Tank 0's overrides: the engine applies them when the level registry loads.
        plantedBridge.startFirstTank(launchOverrideSink);
        HALStart(8, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
        std::fprintf(stderr, "wf_dream: HALStart returned\n");
        windowReady.store(false);
        WFAndroidEglTerm();
    }
    assets = nullptr;
    ANativeWindow_release(window);
}
