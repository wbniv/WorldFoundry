// The on-screen controller of the combined apps (Aquarium and Clocks) on a touchscreen phone: touches from the
// UI thread become the same joystick bits as the TV remote's keys, through the menu key latch, and the game
// thread reads the layout and the held buttons to draw the controller. Pure C++ (no Android or engine types
// beyond the shared hal/touch_controls.h), so tests/touch_bridge_test.cpp builds it on the host
// (`task test-touch-bridge`). docs/plans/2026-11-22-aquarium-clocks-touch-controls.md.
//
// Will, 2026-11-22: the combined app had no way to be driven on a phone once the standalone Aquarium app (which had
// this controller) was retired; the Clocks chooser and its hold-A settings form need it too.
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <vector>

#include <hal/touch_controls.h>

#include "menu_key_latch.h"

class TouchBridge {
public:
    // android.view.MotionEvent action codes.
    static constexpr int kActionDown = 0, kActionUp = 1, kActionMove = 2, kActionCancel = 3,
                         kActionPointerDown = 5, kActionPointerUp = 6;

    // Before a run: a touchscreen and no TV (the TV has the remote), and the display's density scale.
    void configure(bool enabled, float density) {
        enabled_.store(enabled);
        density_.store(density > 0 ? density : 1.0f);
    }
    bool enabled() const { return enabled_.load(); }

    // UI thread: one touch event. `points` are in the view's pixels; the surface may be another size, so they are
    // scaled to it. `action` is getActionMasked(), `actionIndex` getActionIndex(). Returns true when the controller
    // took the event, so the view keeps receiving the rest of the gesture. A tap that is down and up inside one
    // frame still reads once, because the buttons go through the latch.
    bool event(int action, int actionIndex, const wftouch::Point* points, size_t count, float viewWidth,
               float viewHeight, MenuKeyLatch& keys) {
        if (!enabled_.load()) return false;
        const int w = surfaceWidth_.load();
        const int h = surfaceHeight_.load();
        if (w <= 0 || h <= 0 || viewWidth <= 0 || viewHeight <= 0) return true;   // nothing drawn yet to hit
        std::vector<wftouch::Point> scaled(points, points + count);
        for (auto& p : scaled) {
            p.x *= float(w) / viewWidth;
            p.y *= float(h) / viewHeight;
        }
        std::lock_guard<std::mutex> lock(mutex_);
        uint32_t mask = 0;
        if (action == kActionUp || action == kActionCancel) {
            state_.clear();
        } else {
            const auto phase = (action == kActionDown || action == kActionPointerDown) ? wftouch::Action::Down
                               : action == kActionPointerUp                              ? wftouch::Action::Up
                                                                                         : wftouch::Action::Move;
            mask = state_.update(layoutLocked(w, h), scaled.data(), scaled.size(), phase, actionIndex);
        }
        publishLocked(mask, keys);
        return true;
    }

    // Game thread, every frame the engine draws the controller (WFAndroidTouchLayout): the geometry, the buttons
    // the fingers hold, and the stick position for the knob. An empty layout draws nothing.
    void layout(int w, int h, wftouch::Layout* layout, uint32_t* held, float* stickX, float* stickY) {
        surfaceWidth_.store(w);
        surfaceHeight_.store(h);
        if (!enabled_.load()) {
            *layout = wftouch::Layout{};
            *held = 0;
            *stickX = *stickY = 0;
            return;
        }
        std::lock_guard<std::mutex> lock(mutex_);
        *layout = layoutLocked(w, h);
        *held = mask_;
        *stickX = state_.position.x;
        *stickY = state_.position.y;
    }

    // A run starts or ends: no finger is down any more.
    void reset() {
        std::lock_guard<std::mutex> lock(mutex_);
        state_.clear();
        mask_ = 0;
    }

private:
    wftouch::Layout layoutLocked(int w, int h) const {
        return wftouch::layout(float(w), float(h), density_.load(), 0.0f);
    }

    void publishLocked(uint32_t mask, MenuKeyLatch& keys) {
        if (const uint32_t pressed = mask & ~mask_) keys.keyDown(pressed);
        if (const uint32_t released = mask_ & ~mask) keys.keyUp(released);
        mask_ = mask;
    }

    std::atomic<bool> enabled_{false};
    std::atomic<float> density_{1.0f};
    std::atomic<int> surfaceWidth_{0};
    std::atomic<int> surfaceHeight_{0};
    std::mutex mutex_;
    wftouch::State state_;     // guarded by mutex_
    uint32_t mask_ = 0;        // guarded by mutex_
};
