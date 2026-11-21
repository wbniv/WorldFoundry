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
#include <vector>

#include <hal/hal.h>
#include <hal/android/touch_controls.h>
#include <game/level_menu.h>
#include <hal/phonepad/phonepad_overlay.h>
#include <pigsys/pigsys.hp>
#include <runtime_properties.hpp>

#include "planted_bridge.h"

extern "C" bool WFAndroidEglInit(ANativeWindow* window);
extern "C" void WFAndroidEglTerm();
extern "C" void WFAndroidSetSurfaceSize(int width, int height);
extern "C" void WFAndroidSetHudEnabled(int enabled);

namespace {
std::atomic<bool> closing{false};
std::atomic<bool> windowReady{false};
AAssetManager* assets = nullptr;
ANativeWindow* activeWindow = nullptr;
int surfaceWidth = 0;
int surfaceHeight = 0;

// TankPlayer.start(-1), ClocksActivity's launcher with no LEVEL extra: leave out the positional
// level so a shell-menu.fth bundle shows the engine's chooser, and keep the menu drawer installed.
// docs/plans/2026-11-21-tide-harbour-clock.md, "The bundle and the chooser".
constexpr int kShowMenu = -1;
std::atomic<bool> showMenu{false};

// The number of levels in the APK's cd.iff: its TOC less SHEL, the trailing UIFT and a MENU
// (cdpack's layout: SHEL, the levels, [MENU], UIFT). -1 when the asset or its TOC is unreadable.
int bundleLevelCount(AAssetManager* manager) {
    AAsset* asset = AAssetManager_open(manager, "cd.iff", AASSET_MODE_RANDOM);
    if (!asset) return -1;
    std::vector<uint8_t> sector(2048);           // DiskFileCD::_SECTOR_SIZE: the TOC sector
    const int got = AAsset_read(asset, sector.data(), sector.size());
    AAsset_close(asset);
    std::vector<levelmenu::TocEntry> toc;
    if (got <= 0 || !levelmenu::ParseToc(sector.data(), size_t(got), &toc)) return -1;
    size_t n = toc.size();
    if (n > 0 && toc[n - 1].tag == levelmenu::Tag("UIFT")) --n;
    if (n > 0 && toc[n - 1].tag == levelmenu::Tag("MENU")) --n;
    if (n < 2 || toc.front().tag != levelmenu::Tag("SHEL")) return -1;
    return int(n) - 1;
}

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
// The exception is kShowMenu, a launcher asking for the chooser: there the drawer stays.
extern "C" void WFAndroidPumpEvents() {
    if (activeWindow) {
        const int width = ANativeWindow_getWidth(activeWindow);
        const int height = ANativeWindow_getHeight(activeWindow);
        if (width > 0 && height > 0 && (width != surfaceWidth || height != surfaceHeight)) {
            WFAndroidSetSurfaceSize(width, height);
            __android_log_print(ANDROID_LOG_INFO, "wf_dream", "surface resized: %dx%d", width, height);
            surfaceWidth = width;
            surfaceHeight = height;
        }
    }
    if (!showMenu.load() && levelmenu::Drawer()) levelmenu::SetDrawer(nullptr);
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
// One engine launch override, schema + OAD field key + value: the engine validates it against the
// field and applies it when the level's registry loads. Level-agnostic (LevelSettings sends them);
// the Planted bridge is a separate, Planted-specific path and is not involved.
static std::string toStdString(JNIEnv* env, jstring text) {
    std::string out;
    if (!text) return out;
    const char* chars = env->GetStringUTFChars(text, nullptr);
    if (chars) {
        out = chars;
        env->ReleaseStringUTFChars(text, chars);
    }
    return out;
}

extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeLaunchOverride(
        JNIEnv* env, jclass, jstring schema, jstring key, jstring value) {
    launchOverrideSink.set(toStdString(env, schema), toStdString(env, key), toStdString(env, value));
}

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
    // The index bound is the bundle's own length (it was the Aquarium's hard-coded 10). An index
    // outside it is the caller's error: say so and start nothing, never another level.
    AAssetManager* bundleAssets = AAssetManager_fromJava(env, manager);
    const int levels = bundleLevelCount(bundleAssets);
    if (levels <= 0 || level < kShowMenu || level >= levels) {
        __android_log_print(ANDROID_LOG_ERROR, "wf_dream",
                            "level %d rejected: cd.iff holds %d levels (-1 shows the menu)", int(level), levels);
        return;
    }
    showMenu.store(level == kShowMenu);
    if (logPath) {
        const char* path = env->GetStringUTFChars(logPath, nullptr);
        if (path) {
            bridgeEngineLog(path);
            env->ReleaseStringUTFChars(logPath, path);
        }
    }
    std::fprintf(stderr, "\n=== wf_dream start level %d of %d ===\n", int(level), levels);
    __android_log_print(ANDROID_LOG_INFO, "wf_dream", "start level %d", int(level));
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    if (!window) return;
    assets = AAssetManager_fromJava(env, manager);
    WFAndroidSetHudEnabled(0);
    if (WFAndroidEglInit(window)) {
        activeWindow = window;
        surfaceWidth = ANativeWindow_getWidth(window);
        surfaceHeight = ANativeWindow_getHeight(window);
        windowReady.store(true);
        // The positional argument selects the same TOC index as the package's LevelCatalog;
        // kShowMenu leaves it out (argv ends one early), so a shell-menu bundle asks the player.
        char arg0[] = "wf_dream";
        // Decimal, not one ASCII digit: index 10 (Sea Stars) as '0' + 10 is ':', which atoi()
        // reads as 0, so the Dream played the Clownfish tank. The engine parses it with atoi.
        char arg1[12];
        std::snprintf(arg1, sizeof arg1, "%d", int(level));
        char slotWidth[] = "--vram-slot-width=1024";
        char slotHeight[] = "--vram-slot-height=1024";
        char permWidth[] = "--vram-perm-width=1024";
        char permHeight[] = "--vram-perm-height=1024";
        // The same VRAM page as the aquarium app (android/app/src/aquarium/assets/wf_args.txt).
        // The reef tanks carry 1024-wide textures, which the 1024 default width rejects
        // (rmuv.hpi asserts w < VRAMWidth); tests/test_dream_host_vram.py keeps the two in step.
        char vramWidth[] = "--vram-width=2048";
        char vramHeight[] = "--vram-height=2048";
        char noFps[] = "--no-fps";
        char* argv[] = {arg0, slotWidth, slotHeight, permWidth, permHeight, vramWidth, vramHeight, noFps, arg1, nullptr};
        const int argc = level == kShowMenu ? 8 : 9;
        argv[argc] = nullptr;
        __argc = argc;
        __argv = argv;
        // Tank 0's overrides: the engine applies them when the level registry loads.
        plantedBridge.startFirstTank(launchOverrideSink);
        HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
        std::fprintf(stderr, "wf_dream: HALStart returned\n");
        windowReady.store(false);
        activeWindow = nullptr;
        WFAndroidEglTerm();
    }
    assets = nullptr;
    ANativeWindow_release(window);
}
