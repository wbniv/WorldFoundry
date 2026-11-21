// The launcher menu's remote keys, from the UI thread to the game thread, without losing a press
// (docs/plans/2026-11-21-menu-key-latch.md). Pure C++: no Android or engine types, so
// tests/menu_key_latch_test.cpp builds it on the host (`task test-menu-key-latch`).
//
// The game thread samples the menu input once per frame, and a Chromecast HD frame can be 200 ms,
// so a held mask alone loses a key that goes down and up between two samples. The latch keeps
// every new press until the game thread has read it once; the held mask keeps holds and the
// level menu's own auto-repeat working. Key repeat (more key-downs while held) latches nothing.
#pragma once

#include <atomic>
#include <cstdint>

class MenuKeyLatch {
public:
    // UI thread: a key went down. Only bits not already held are latched, so key repeat adds
    // no extra frame of press after the release.
    void keyDown(uint32_t mask) {
        const uint32_t before = held_.fetch_or(mask);
        if (const uint32_t fresh = mask & ~before) pressed_.fetch_or(fresh);
    }

    // UI thread: a key went up. A press latched but not yet read still reads once.
    void keyUp(uint32_t mask) { held_.fetch_and(~mask); }

    // Game thread, once per frame: the buttons for this frame, held or pressed since the last
    // read. Consumes the latch.
    uint32_t takeFrame() { return held_.load() | pressed_.exchange(0); }

    // Drop presses not yet read (a tank starts, the menu comes back); held keys stay held.
    void clearLatch() { pressed_.store(0); }

    // Drop everything (a run starts or ends).
    void clear() {
        held_.store(0);
        pressed_.store(0);
    }

private:
    std::atomic<uint32_t> held_{0};     // keys down now
    std::atomic<uint32_t> pressed_{0};  // keys gone down since the game thread last read
};
