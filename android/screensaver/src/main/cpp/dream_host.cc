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
#include <hal/_input.h>
#include <hal/android/key_map.h>
#include <hal/android/touch_controls.h>
#include <game/level_menu.h>
#include <hal/phonepad/phonepad_overlay.h>
#include <pigsys/pigsys.hp>
#include <runtime_properties.hpp>
#include <runtime_property_host.hpp>

#include "menu_key_latch.h"
#include "touch_bridge.h"
#include "planted_bridge.h"

extern "C" bool WFAndroidEglInit(ANativeWindow* window);
extern "C" void WFAndroidEglTerm();
extern "C" void WFAndroidSetSurfaceSize(int width, int height);
extern "C" void WFAndroidSetHudEnabled(int enabled);
extern "C" void WFAndroidSetBundleAsset(const char* name);   // hal/android/asset_accessor_aasset.cc

namespace {
std::atomic<bool> closing{false};
std::atomic<bool> windowReady{false};
AAssetManager* assets = nullptr;
ANativeWindow* activeWindow = nullptr;
int surfaceWidth = 0;
int surfaceHeight = 0;

// Optional per-flavor override of one VRAM size: the flavor's assets/wf_args.txt, one `--vram-...=N` per line
// (the aquarium app's file format). Only the clocks flavor ships one: Cuckoo Village packs its textures into a
// 2048 x 1024 page, which the default 1024 x 1024 slot rejects (FatalError: LoadTexture ... does not fit its
// VRAM slot). Every other flavor has no file and keeps the defaults below. Returns true and fills `out` when
// the file has a line starting with `prefix`.
bool vramOverride(const char* prefix, char* out, size_t capacity) {
    if (!assets) return false;
    AAsset* file = AAssetManager_open(assets, "wf_args.txt", AASSET_MODE_BUFFER);
    if (!file) return false;
    const std::string text(static_cast<const char*>(AAsset_getBuffer(file)), size_t(AAsset_getLength(file)));
    AAsset_close(file);
    const std::string want(prefix);
    bool found = false;
    for (size_t pos = 0; pos < text.size();) {
        size_t end = text.find('\n', pos);
        if (end == std::string::npos) end = text.size();
        std::string line = text.substr(pos, end - pos);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        if (line.compare(0, want.size(), want) == 0 && line.size() < capacity) {
            std::snprintf(out, capacity, "%s", line.c_str());
            found = true;
        }
        pos = end + 1;
    }
    return found;
}


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

// The launcher menu (docs/plans/2026-11-21-one-aquarium-app.md). TankPlayer.MENU as the level runs
// the playable menu bundle (assets/menu-cd.iff, the Aquarium app's aquarium-menu-cd.iff) with no
// positional level, so its shell asks the player, and keeps the engine's menu drawer. Every other
// level index is the Dream path, exactly as before: cd.iff, a positional level, no overlay.
constexpr int kMenuLevel = -1;      // TankPlayer.MENU: "show the engine's menu", from either app
constexpr const char* kMenuBundleAsset = "menu-cd.iff";
std::atomic<bool> menuMode{false};
// Remote keys from AquariumActivity (UI thread), applied on the game thread in WFAndroidPumpEvents.
// Held keys plus a latch of presses not yet read, so a tap shorter than one frame (a Chromecast HD
// frame can be 200 ms) still reaches the menu (docs/plans/2026-11-21-menu-key-latch.md).
MenuKeyLatch menuKeys;
TouchBridge touchBridge;   // the on-screen controller on a phone; its buttons go through menuKeys
bool menuSelectorWasVisible = false;   // game thread only
std::atomic<bool> backPending{false};
std::atomic<bool> leaveRequested{false};

// Back, on the game thread, as the game app's NativeActivity host does it
// (hal/android/native_app_entry.cc): an open settings form closes first; Back in a tank returns
// to the menu; Back on the menu leaves (the engine exits, and TankPlayer finishes the activity).
void applyMenuBack() {
    if (wfprops::host().modal) {
        wfprops::host().back();
    } else if (levelmenu::SelectorVisible()) {
        __android_log_write(ANDROID_LOG_INFO, "wf_dream", "Back on the menu: leaving the app");
        leaveRequested.store(true);
        closing.store(true);
    } else if (levelmenu::MenuRunning()) {
        __android_log_write(ANDROID_LOG_INFO, "wf_dream", "Back in a tank: returning to the menu");
        levelmenu::RequestReturn();
    }
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
// The menu is the one exception: it keeps the drawer and takes the remote's keys.
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
    if (menuMode.load()) {            // the launcher menu, in either app: it keeps the drawer and takes the remote
        // A tank starting from the menu, or the menu coming back, drops presses not yet read.
        const bool selectorVisible = levelmenu::SelectorVisible();
        if (selectorVisible != menuSelectorWasVisible) {
            menuSelectorWasVisible = selectorVisible;
            menuKeys.clearLatch();
        }
        HALInjectJoystickButtons(menuKeys.takeFrame());
        if (backPending.exchange(false)) applyMenuBack();
    } else if (levelmenu::Drawer()) {
        levelmenu::SetDrawer(nullptr);
    }
    plantedBridge.pump(launchOverrideSink);
}
// The on-screen controller (joystick and A to D) is drawn while the menu, or a tank started from it, runs on a
// touchscreen phone. The Dream and the TV draw nothing. docs/plans/2026-11-22-aquarium-clocks-touch-controls.md.
extern "C" void WFAndroidTouchLayout(int w, int h, androidtouch::Layout* layout,
                                       uint32_t* held, float* x, float* y) {
    if (!menuMode.load()) {
        *layout = androidtouch::Layout{};
        *held = 0;
        *x = *y = 0;
        return;
    }
    touchBridge.layout(w, h, layout, held, x, y);
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
    leaveRequested.store(false);
    backPending.store(false);
    menuKeys.clear();
    touchBridge.reset();
    plantedBridge.reset();
}

// A remote key while the launcher menu runs (UI thread). Returns true when the engine uses the key,
// so the activity consumes it; any other key keeps its system meaning.
extern "C" JNIEXPORT jboolean JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeKey(JNIEnv*, jclass, jint keyCode, jboolean down) {
    const uint32_t mask = WFAndroidMapKeyCode(keyCode);
    if (!mask || !menuMode.load()) return JNI_FALSE;
    if (down) menuKeys.keyDown(mask);
    else menuKeys.keyUp(mask);
    return JNI_TRUE;
}

// Whether this device draws the on-screen controller (a touchscreen and no TV) and its density scale; once per player.
extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeTouchConfigure(JNIEnv*, jclass, jboolean enabled, jfloat density) {
    touchBridge.configure(enabled == JNI_TRUE, density);
}

// One touch event on the surface view (UI thread): the controller's buttons become the same joystick bits as the
// remote's keys. Returns true when the controller took the event.
extern "C" JNIEXPORT jboolean JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeTouch(JNIEnv* env, jclass, jint action, jint actionIndex,
                                                          jint viewWidth, jint viewHeight, jintArray ids,
                                                          jfloatArray xs, jfloatArray ys) {
    if (!touchBridge.enabled() || !menuMode.load()) return JNI_FALSE;
    const jsize count = env->GetArrayLength(ids);
    const size_t n = static_cast<size_t>(count);
    std::vector<jint> id(n);
    std::vector<jfloat> x(n), y(n);
    env->GetIntArrayRegion(ids, 0, count, id.data());
    env->GetFloatArrayRegion(xs, 0, count, x.data());
    env->GetFloatArrayRegion(ys, 0, count, y.data());
    std::vector<androidtouch::Point> points(n);
    for (size_t i = 0; i < points.size(); ++i) points[i] = {x[i], y[i], id[i]};
    return touchBridge.event(action, actionIndex, points.data(), points.size(), float(viewWidth), float(viewHeight),
                             menuKeys) ? JNI_TRUE : JNI_FALSE;
}

// Back released while the launcher menu runs (UI thread); applied on the game thread.
extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeBack(JNIEnv*, jclass) {
    if (menuMode.load()) backPending.store(true);
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
    if (levels <= 0 || level < kMenuLevel || level >= levels) {
        __android_log_print(ANDROID_LOG_ERROR, "wf_dream",
                            "level %d rejected: cd.iff holds %d levels (-1 shows the menu)", int(level), levels);
        return;
    }
    const bool menu = level == kMenuLevel;
    // The Aquarium app ships the playable menu as a second bundle; the Clocks app's chooser is inside cd.iff.
    // Only an APK that carries menu-cd.iff takes the second-bundle path.
    AAsset* menuAsset = menu ? AAssetManager_open(bundleAssets, kMenuBundleAsset, AASSET_MODE_UNKNOWN) : nullptr;
    const bool secondBundle = menuAsset != nullptr;
    if (menuAsset) AAsset_close(menuAsset);
    if (logPath) {
        const char* path = env->GetStringUTFChars(logPath, nullptr);
        if (path) {
            bridgeEngineLog(path);
            env->ReleaseStringUTFChars(logPath, path);
        }
    }
    if (menu) {
        std::fprintf(stderr, "\n=== wf_dream start the menu (%s) of %d ===\n", secondBundle ? kMenuBundleAsset : "cd.iff", levels);
        __android_log_print(ANDROID_LOG_INFO, "wf_dream", "start the menu (%s)", secondBundle ? kMenuBundleAsset : "cd.iff");
    } else {
        std::fprintf(stderr, "\n=== wf_dream start level %d of %d ===\n", int(level), levels);
        __android_log_print(ANDROID_LOG_INFO, "wf_dream", "start level %d", int(level));
    }
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    if (!window) return;
    assets = AAssetManager_fromJava(env, manager);
    // The HUD here is only the on-screen controller: on for the menu and its tanks on a phone, off for the Dream and the TV.
    WFAndroidSetHudEnabled(menu && touchBridge.enabled() ? 1 : 0);
    // Set before HALStart opens the bundle, and on every run: one process may hold both modes.
    WFAndroidSetBundleAsset(secondBundle ? kMenuBundleAsset : nullptr);
    // The menu starts with no key held or latched; the game thread is not running yet.
    menuKeys.clear();
    menuSelectorWasVisible = false;
    menuMode.store(menu);
    if (WFAndroidEglInit(window)) {
        activeWindow = window;
        surfaceWidth = ANativeWindow_getWidth(window);
        surfaceHeight = ANativeWindow_getHeight(window);
        windowReady.store(true);
        // The positional argument selects the same TOC index as the package's LevelCatalog;
        // The menu leaves it out (argv ends one early), so the bundle's shell-menu.fth asks the player.
        char arg0[] = "wf_dream";
        // Decimal, not one ASCII digit: index 10 (Sea Stars) as '0' + 10 is ':', which atoi()
        // reads as 0, so the Dream played the Clownfish tank. The engine parses it with atoi.
        char arg1[12];
        std::snprintf(arg1, sizeof arg1, "%d", int(level));
        char slotWidth[] = "--vram-slot-width=1024";
        char slotHeight[] = "--vram-slot-height=1024";
        char permWidth[] = "--vram-perm-width=1024";
        char permHeight[] = "--vram-perm-height=1024";
        // The same VRAM page as the aquarium app (wflevels/aquarium-wf_args.txt).
        // The reef tanks carry 1024-wide textures, which the 1024 default width rejects
        // (rmuv.hpi asserts w < VRAMWidth); tests/test_dream_host_vram.py keeps the two in step.
        char vramWidth[] = "--vram-width=2048";
        char vramHeight[] = "--vram-height=2048";
        char noFps[] = "--no-fps";
        char* argv[] = {arg0, slotWidth, slotHeight, permWidth, permHeight, vramWidth, vramHeight, noFps, arg1, nullptr};
        const int argc = menu ? 8 : 9;
        argv[argc] = nullptr;
        // The flavor's own VRAM sizes, if it ships a wf_args.txt (argv[1..6] are slot, perm and page width/height).
        char overrides[6][48];
        const char* const prefixes[6] = {"--vram-slot-width=", "--vram-slot-height=", "--vram-perm-width=",
                                         "--vram-perm-height=", "--vram-width=", "--vram-height="};
        for (int i = 0; i < 6; ++i) {
            if (vramOverride(prefixes[i], overrides[i], sizeof overrides[i])) {
                argv[1 + i] = overrides[i];
                __android_log_print(ANDROID_LOG_INFO, "wf_dream", "vram override: %s", overrides[i]);
            }
        }
        __argc = argc;
        __argv = argv;
        // Tank 0's overrides: the engine applies them when the level registry loads.
        plantedBridge.startFirstTank(launchOverrideSink);
        HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
        std::fprintf(stderr, "wf_dream: HALStart returned%s\n", leaveRequested.load() ? " (Back on the menu)" : "");
        windowReady.store(false);
        activeWindow = nullptr;
        WFAndroidEglTerm();
    }
    menuMode.store(false);
    menuKeys.clear();
    assets = nullptr;
    ANativeWindow_release(window);
}
