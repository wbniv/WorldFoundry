#include <android/asset_manager_jni.h>
#include <android/native_window_jni.h>
#include <jni.h>
#include <android/log.h>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <fcntl.h>
#include <mutex>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>

#include <hal/hal.h>
#include <hal/_input.h>
#include <hal/android/key_map.h>
#include <hal/android/touch_controls.h>
#include <game/level_menu.h>
#include <game/bitmap_presenter.hp>   // ReaderOpen: a story card narrows the controller
#include <game/runtime_property_touch.h>
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
GamepadStick gamepadStick; // a hardware gamepad's analog stick and hat, through menuKeys

// Touch events from the UI thread, handled on the game thread: the engine's settings form and the controller both
// change game state, and the engine is single-threaded. One record is one MotionEvent.
struct TouchRecord {
    int action = 0, actionIndex = 0;
    float viewWidth = 0, viewHeight = 0;
    std::vector<androidtouch::Point> points;
};
std::mutex touchQueueMutex;
std::vector<TouchRecord> touchQueue;
constexpr size_t kTouchQueueMax = 256;
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

// Tapping a row of the tank menu (the standalone host's gMenuTouchPointer logic): a down on a row remembers the finger,
// the matching up within 24 pixels chooses the row. Game thread only. Returns true when the event is the menu's.
static bool menuRowTouch(const TouchRecord& e, float fx, float fy) {
    static int pointer = -1;
    static float downX = 0, downY = 0;
    if (!levelmenu::SelectorVisible() || wfprops::host().modal) {
        pointer = -1;
        return false;
    }
    const int w = int(e.viewWidth * fx + .5f), h = int(e.viewHeight * fy + .5f);
    if (e.action == TouchBridge::kActionCancel) {
        const bool mine = pointer >= 0;
        pointer = -1;
        return mine;
    }
    if (e.action == TouchBridge::kActionMove) return pointer >= 0;
    if (e.actionIndex < 0 || size_t(e.actionIndex) >= e.points.size()) return false;
    const auto& p = e.points[size_t(e.actionIndex)];
    const float x = p.x * fx, y = p.y * fy;
    if (e.action == TouchBridge::kActionDown || e.action == TouchBridge::kActionPointerDown) {
        if (pointer < 0 && levelmenu::TouchRowAt(x, y, w, h) >= 0) {
            pointer = p.id;
            downX = x;
            downY = y;
            return true;
        }
        return false;
    }
    if (p.id != pointer) return false;
    pointer = -1;
    if (std::fabs(x - downX) < 24 && std::fabs(y - downY) < 24) {
        const int row = levelmenu::TouchRowAt(x, y, w, h);
        if (row >= 0) levelmenu::QueueTouchRow(row);
    }
    return true;
}

// The settings form first (its entry button at the top right, and the form itself), then the controller, exactly
// as the NativeActivity host orders them (hal/android/native_app_entry.cc); a touch the form takes lets go of every
// controller button. Game thread only.
static void pumpTouch(int surfaceW, int surfaceH) {
    touchBridge.setReading(bitmaptext::ReaderOpen());
    std::vector<TouchRecord> events;
    {
        std::lock_guard<std::mutex> lock(touchQueueMutex);
        events.swap(touchQueue);
    }
    for (const TouchRecord& e : events) {
        if (e.viewWidth <= 0 || e.viewHeight <= 0 || surfaceW <= 0 || surfaceH <= 0) continue;
        const float fx = float(surfaceW) / e.viewWidth, fy = float(surfaceH) / e.viewHeight;
        bool settingsTouch = false;
        using Phase = propertyui::TouchPhase;
        if (e.action == TouchBridge::kActionCancel) {
            settingsTouch = propertyui::touchEvent(Phase::Cancel, -1, 0, 0, surfaceW, surfaceH);
        } else if (e.action == TouchBridge::kActionMove) {
            for (const auto& p : e.points)
                settingsTouch = propertyui::touchEvent(Phase::Move, p.id, p.x * fx, p.y * fy, surfaceW, surfaceH) || settingsTouch;
        } else if (e.actionIndex >= 0 && size_t(e.actionIndex) < e.points.size()) {
            const auto& p = e.points[size_t(e.actionIndex)];
            const bool down = e.action == TouchBridge::kActionDown || e.action == TouchBridge::kActionPointerDown;
            settingsTouch = propertyui::touchEvent(down ? Phase::Down : Phase::Up, p.id, p.x * fx, p.y * fy, surfaceW, surfaceH);
        }
        if (!settingsTouch && menuRowTouch(e, fx, fy)) {
            touchBridge.release(menuKeys);
            continue;
        }
        if (settingsTouch) touchBridge.release(menuKeys);
        else touchBridge.event(e.action, e.actionIndex, e.points.data(), e.points.size(), e.viewWidth, e.viewHeight, menuKeys);
    }
}

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
        pumpTouch(surfaceWidth, surfaceHeight);
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
    gamepadStick.reset();
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

// A hardware gamepad's stick and hat (UI thread): past half deflection a direction, through the key latch.
extern "C" JNIEXPORT jboolean JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeStick(JNIEnv*, jclass, jfloat x, jfloat y, jfloat hatX, jfloat hatY) {
    if (!menuMode.load()) return JNI_FALSE;
    gamepadStick.update(x, y, hatX, hatY, menuKeys);
    return JNI_TRUE;
}

// Whether this device draws the on-screen controller (a touchscreen and no TV) and its density scale; once per player.
extern "C" JNIEXPORT void JNICALL
Java_org_worldfoundry_screensaver_TankPlayer_nativeTouchConfigure(JNIEnv*, jclass, jboolean enabled, jfloat density) {
    touchBridge.configure(enabled == JNI_TRUE, density);
}

// One touch event on the surface view (UI thread): queued for the game thread, which gives it to the settings form
// and the controller. Returns true when this device takes touches here (the controller is drawn).
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
    TouchRecord record;
    record.action = action;
    record.actionIndex = actionIndex;
    record.viewWidth = float(viewWidth);
    record.viewHeight = float(viewHeight);
    record.points.resize(n);
    for (size_t i = 0; i < n; ++i) record.points[i] = {x[i], y[i], id[i]};
    std::lock_guard<std::mutex> lock(touchQueueMutex);
    if (touchQueue.size() >= kTouchQueueMax) touchQueue.erase(touchQueue.begin());
    touchQueue.push_back(std::move(record));
    return JNI_TRUE;
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
    // The engine's own touch settings form (an entry button at the top right, then the form) goes with the controller.
    propertyui::touchConfigure(menu && touchBridge.enabled(), touchBridge.density());
    propertyui::touchReset();
    { std::lock_guard<std::mutex> lock(touchQueueMutex); touchQueue.clear(); }
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
