//=============================================================================
// hal/android/input_probe.h: per-key latency bookkeeping for the input probe
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// docs/plans/2026-11-13-android-input-latency.md. Measures a remote key at the
// HAL, independent of any level's game logic, on the device's CLOCK_MONOTONIC
// (the clock AKeyEvent_getEventTime and Java's SystemClock.uptimeMillis use):
//
//   event   when Android generated the key   (AKeyEvent_getEventTime)
//   receive when HandleInputEvent saw it      (inside WFAndroidPumpEvents)
//   swap 1  the first eglSwapBuffers after it (the probe's flash is in it)
//   swap 2  the next one: the first frame whose game tick read the new state
//           (the tick runs before PageFlip, and the pump runs inside PageFlip)
//
// Plus, per second of frames, how long the longest frame was and how many
// input events and looper idents one pump drained: a backlog would show as a
// growing count per pump. Header-only and free of Android headers, so the
// desktop build tests it (tests/android_input_probe_test.cc); native_app_entry.cc
// and gfx/gl/android_window.cc drive it in WF_INPUT_PROBE builds only.
//=============================================================================
#pragma once

#include <cstdint>

namespace inputprobe {

constexpr int kMaxPending = 64;    // edges still waiting for their second swap
constexpr int kMaxHeld    = 16;    // distinct key codes held at once

struct Edge
{
    int      code = 0, action = 0;     // AKEY_EVENT_ACTION_DOWN = 0, _UP = 1
    int64_t  eventNs = 0, receiveNs = 0, swap1Ns = 0, swap2Ns = 0;
    uint64_t frame = 0;                // pump count when received
};

struct Stats
{
    uint64_t frames = 0;               // pumps in the window
    int64_t  maxFrameNs = 0;           // longest gap between two pumps
    uint32_t events = 0, maxEventsPerPump = 0;
    uint32_t idents = 0, maxIdentsPerPump = 0;
};

class Tracker
{
public:
    // One frame boundary: WFAndroidPumpEvents begins.
    void PumpBegin(int64_t nowNs)
    {
        if (pumped_ && nowNs - lastPumpNs_ > stats_.maxFrameNs)
            stats_.maxFrameNs = nowNs - lastPumpNs_;
        if (!pumped_) windowStartNs_ = nowNs;
        pumped_ = true;
        lastPumpNs_ = nowNs;
        ++frame_;
        ++stats_.frames;
        pumpEvents_ = pumpIdents_ = 0;
    }

    // One ALooper ident processed by the pump (a command or an input batch).
    void Ident() { ++pumpIdents_; ++stats_.idents; }

    // A key event reached HandleInputEvent. Every event counts toward the
    // per-pump backlog; only first edges (repeat 0) are timed, and they set
    // the held set the flash follows. Returns event-to-receive in ns.
    int64_t Key(int code, int action, int repeat, int64_t eventNs, int64_t nowNs)
    {
        ++pumpEvents_;
        ++stats_.events;
        if (repeat == 0 && (action == 0 || action == 1))
        {
            if (action == 0) Hold(code);
            else             Release(code);
            if (pending_ < kMaxPending)
            {
                Edge& e = edges_[pending_++];
                e = Edge();
                e.code = code; e.action = action;
                e.eventNs = eventNs; e.receiveNs = nowNs; e.frame = frame_;
            }
            else
                ++dropped_;
        }
        return nowNs - eventNs;
    }

    // WFAndroidPumpEvents is done: fold this pump into the per-pump maxima.
    void PumpEnd()
    {
        if (pumpEvents_ > stats_.maxEventsPerPump) stats_.maxEventsPerPump = pumpEvents_;
        if (pumpIdents_ > stats_.maxIdentsPerPump) stats_.maxIdentsPerPump = pumpIdents_;
    }

    // eglSwapBuffers returned at nowNs. An edge gets swap 1 from the first swap
    // after it arrived and swap 2 from the next; edges with both are copied to
    // done (up to max) and dropped from the tracker. Returns the count copied.
    int Swap(int64_t nowNs, Edge* done, int max)
    {
        int n = 0, keep = 0;
        for (int i = 0; i < pending_; ++i)
        {
            Edge e = edges_[i];
            if (e.swap1Ns == 0)      e.swap1Ns = nowNs;
            else if (e.swap2Ns == 0) e.swap2Ns = nowNs;
            if (e.swap2Ns != 0 && n < max) done[n++] = e;
            else if (e.swap2Ns != 0)       ++dropped_;
            else                           edges_[keep++] = e;
        }
        pending_ = keep;
        return n;
    }

    // True while any key whose first DOWN was seen has no UP yet.
    bool Held() const { return held_ > 0; }

    // Once at least a second of pumps has passed, copy and reset the stats.
    bool TakeStats(int64_t nowNs, Stats* out)
    {
        if (!pumped_ || nowNs - windowStartNs_ < 1000000000LL) return false;
        *out = stats_;
        stats_ = Stats();
        windowStartNs_ = nowNs;
        return true;
    }

    uint64_t Frame() const   { return frame_; }
    int      Pending() const { return pending_; }
    uint32_t Dropped() const { return dropped_; }

    // A focus change or pause: Android will not deliver the UPs.
    void ReleaseAll() { held_ = 0; }

private:
    void Hold(int code)
    {
        for (int i = 0; i < held_; ++i) if (heldCodes_[i] == code) return;
        if (held_ < kMaxHeld) heldCodes_[held_++] = code;
    }
    void Release(int code)
    {
        for (int i = 0; i < held_; ++i)
            if (heldCodes_[i] == code) { heldCodes_[i] = heldCodes_[--held_]; return; }
    }

    Edge     edges_[kMaxPending];
    int      pending_ = 0;
    int      heldCodes_[kMaxHeld] = {};
    int      held_ = 0;
    uint64_t frame_ = 0;
    uint32_t dropped_ = 0;
    uint32_t pumpEvents_ = 0, pumpIdents_ = 0;
    int64_t  lastPumpNs_ = 0, windowStartNs_ = 0;
    bool     pumped_ = false;
    Stats    stats_;
};

}  // namespace inputprobe
