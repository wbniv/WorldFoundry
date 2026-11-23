// The combined apps' on-screen controller, pure logic (android/screensaver/src/main/cpp/touch_bridge.h;
// docs/plans/2026-11-22-aquarium-clocks-touch-controls.md). Built and run by `task test-touch-bridge` in
// wf-linux-test:local with plain g++: no Android, no engine.
#undef NDEBUG  // the checks below carry side effects
#include "touch_bridge.h"
#include <cassert>
#include <cstdio>

namespace {
int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)

constexpr int W = 1600, H = 720;
constexpr float kDensity = 2.5f;

using TB = TouchBridge;

wftouch::Layout geometry() { return wftouch::layout(float(W), float(H), kDensity, 0.0f); }

wftouch::Point centre(const wftouch::Rect& r, int id = 0) { return {(r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, id}; }

wftouch::Point control(uint32_t bit, int id = 0) {
    const auto l = geometry();
    for (int i = 4; i < 8; ++i) if (l.controls[i].bit == bit) return centre(l.controls[i].rect, id);
    assert(false);
    return {};
}

// A point in the stick, `fraction` of its radius to the right of its centre.
wftouch::Point stickRight(float fraction, int id = 0) {
    const auto l = geometry();
    auto p = centre(l.pad, id);
    p.x += fraction * wftouch::stickRadius(l);
    return p;
}

// The game thread draws one frame: the surface size reaches the bridge.
void frame(TB& t) {
    wftouch::Layout l;
    uint32_t held;
    float x, y;
    t.layout(W, H, &l, &held, &x, &y);
}

}  // namespace

int main() {
    // Off (a TV, or no touchscreen): events are not taken and nothing is drawn.
    {
        TB t;
        MenuKeyLatch keys;
        t.configure(false, kDensity);
        wftouch::Layout l;
        uint32_t held = 99;
        float x = 9, y = 9;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(!l.valid && held == 0 && x == 0 && y == 0);
        const auto a = control(wftouch::A);
        CHECK(!t.event(TB::kActionDown, 0, &a, 1, W, H, keys));
        CHECK(keys.takeFrame() == 0);
    }
    // On: the controller is drawn and a tap on A, down and up inside one frame, reads once, then not again.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(l.valid && l.stick);
        const auto a = control(wftouch::A);
        CHECK(t.event(TB::kActionDown, 0, &a, 1, W, H, keys));
        CHECK(t.event(TB::kActionUp, 0, &a, 1, W, H, keys));
        CHECK(keys.takeFrame() == wftouch::A);
        CHECK(keys.takeFrame() == 0);
    }
    // A hold on A (the Clocks settings form takes one second of OK) reads every frame until the finger lifts.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        const auto a = control(wftouch::A);
        t.event(TB::kActionDown, 0, &a, 1, W, H, keys);
        for (int i = 0; i < 5; ++i) CHECK(keys.takeFrame() == wftouch::A);
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(held == wftouch::A);
        t.event(TB::kActionUp, 0, &a, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
    }
    // The stick: right of centre reads Right, follows the thumb, leaves nothing behind.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        auto p = stickRight(0.9f);
        t.event(TB::kActionDown, 0, &p, 1, W, H, keys);
        CHECK(keys.takeFrame() == wftouch::Right);
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(held == wftouch::Right && x > 0.5f);
        p = stickRight(0.1f);                                   // back near the middle: no direction
        t.event(TB::kActionMove, 0, &p, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
        t.event(TB::kActionUp, 0, &p, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
    }
    // Two thumbs: the stick and A together, then A lets go and the stick stays.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        wftouch::Point both[2] = {stickRight(0.9f, 0), control(wftouch::A, 1)};
        t.event(TB::kActionDown, 0, both, 1, W, H, keys);
        t.event(TB::kActionPointerDown, 1, both, 2, W, H, keys);
        CHECK(keys.takeFrame() == (wftouch::Right | wftouch::A));
        t.event(TB::kActionPointerUp, 1, both, 2, W, H, keys);
        CHECK(keys.takeFrame() == wftouch::Right);
    }
    // A cancelled gesture lets everything go.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        const auto a = control(wftouch::B);
        t.event(TB::kActionDown, 0, &a, 1, W, H, keys);
        CHECK(keys.takeFrame() == wftouch::B);
        t.event(TB::kActionCancel, 0, &a, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
    }
    // The view and the surface can differ in size: a point in view pixels is scaled to the surface.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        auto a = control(wftouch::C);
        a.x /= 2;                                               // the same spot on a view half as wide
        a.y /= 2;                                               // and half as tall
        t.event(TB::kActionDown, 0, &a, 1, W / 2.0f, H / 2.0f, keys);
        CHECK(keys.takeFrame() == wftouch::C);
    }
    // Before the first frame there is no layout to hit: the event is taken, nothing is pressed.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        const auto a = control(wftouch::A);
        CHECK(t.event(TB::kActionDown, 0, &a, 1, W, H, keys));
        CHECK(keys.takeFrame() == 0);
    }
    // A touch that misses every control presses nothing.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        wftouch::Point miss{W / 2.0f, 40.0f, 0};
        t.event(TB::kActionDown, 0, &miss, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
    }
    // reset() drops the fingers' state (a run starts or ends).
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        const auto a = control(wftouch::A);
        t.event(TB::kActionDown, 0, &a, 1, W, H, keys);
        t.reset();
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(held == 0);
    }
    // release(): the settings form took the gesture, so a held button lets go at once.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        frame(t);
        const auto a = control(wftouch::A);
        t.event(TB::kActionDown, 0, &a, 1, W, H, keys);
        CHECK(keys.takeFrame() == wftouch::A);
        t.release(keys);
        CHECK(keys.takeFrame() == 0);
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(held == 0);
        CHECK(t.density() == kDensity);
    }
    // A story card narrows the controller to A and C: the stick is gone, A still works.
    {
        TB t; MenuKeyLatch keys;
        t.configure(true, kDensity);
        t.setReading(true);
        frame(t);
        wftouch::Layout l; uint32_t held; float x, y;
        t.layout(W, H, &l, &held, &x, &y);
        CHECK(!l.stick && l.shown == (wftouch::A | wftouch::C));
        auto p = stickRight(0.9f);
        t.event(TB::kActionDown, 0, &p, 1, W, H, keys);
        CHECK(keys.takeFrame() == 0);
        t.event(TB::kActionUp, 0, &p, 1, W, H, keys);
        const auto a = control(wftouch::A);
        t.event(TB::kActionDown, 0, &a, 1, W, H, keys);
        CHECK(keys.takeFrame() == wftouch::A);
    }
    // A gamepad's stick: past half deflection a direction, the hat wins, back to centre lets go.
    {
        CHECK(GamepadStick::axes(0.4f, 0, 0, 0) == 0);
        CHECK(GamepadStick::axes(0.6f, 0, 0, 0) == wftouch::Right);
        CHECK(GamepadStick::axes(-0.6f, -0.9f, 0, 0) == (wftouch::Left | wftouch::Up));
        CHECK(GamepadStick::axes(0.9f, 0, -1, 0) == wftouch::Left);   // the hat wins
        GamepadStick g; MenuKeyLatch keys;
        g.update(0.9f, 0, 0, 0, keys);
        CHECK(keys.takeFrame() == wftouch::Right);
        CHECK(keys.takeFrame() == wftouch::Right);                    // held
        g.update(0, 0, 0, 0, keys);
        CHECK(keys.takeFrame() == 0);
    }
    std::printf("touch_bridge: %d checks passed\n", checks);
    return 0;
}
