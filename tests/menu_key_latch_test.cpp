// The launcher menu's key latch, pure logic (android/screensaver/src/main/cpp/menu_key_latch.h;
// docs/plans/2026-11-21-menu-key-latch.md). Built and run by `task test-menu-key-latch` in
// wf-linux-test:local with plain g++: no Android, no engine.
#undef NDEBUG  // the checks below carry side effects
#include "menu_key_latch.h"
#include <cassert>
#include <cstdio>

namespace {
constexpr uint32_t kDown = 1u << 1;
constexpr uint32_t kSelect = 1u << 4;
int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)
}

int main() {
    // A tap inside one frame (down and up before the game thread reads) reads exactly once.
    {
        MenuKeyLatch k;
        k.keyDown(kDown);
        k.keyUp(kDown);
        CHECK(k.takeFrame() == kDown);
        CHECK(k.takeFrame() == 0);
        CHECK(k.takeFrame() == 0);
    }
    // A held key reads every frame until released; key repeat queues no extra frame after it.
    {
        MenuKeyLatch k;
        k.keyDown(kDown);
        CHECK(k.takeFrame() == kDown);
        k.keyDown(kDown);  // key repeat
        CHECK(k.takeFrame() == kDown);
        k.keyDown(kDown);  // key repeat
        CHECK(k.takeFrame() == kDown);
        k.keyDown(kDown);  // key repeat just before the release, inside one frame
        k.keyUp(kDown);
        CHECK(k.takeFrame() == 0);
    }
    // Releasing clears the held bit, but a latched press not yet read still reads once.
    {
        MenuKeyLatch k;
        k.keyDown(kSelect);
        k.keyUp(kSelect);
        k.keyDown(kDown);
        CHECK(k.takeFrame() == (kSelect | kDown));
        CHECK(k.takeFrame() == kDown);  // Down still held, Select gone
        k.keyUp(kDown);
        CHECK(k.takeFrame() == 0);
    }
    // Two different keys tapped in one frame both read in that frame.
    {
        MenuKeyLatch k;
        k.keyDown(kDown);
        k.keyUp(kDown);
        k.keyDown(kSelect);
        k.keyUp(kSelect);
        CHECK(k.takeFrame() == (kDown | kSelect));
        CHECK(k.takeFrame() == 0);
    }
    // The clear when the menu starts drops held keys and unread presses.
    {
        MenuKeyLatch k;
        k.keyDown(kDown);
        k.keyDown(kSelect);
        k.keyUp(kSelect);
        k.clear();
        CHECK(k.takeFrame() == 0);
        k.keyDown(kDown);  // a fresh press after the clear latches again
        k.keyUp(kDown);
        CHECK(k.takeFrame() == kDown);
    }
    // A tank starts or the menu comes back: unread presses go, a held key stays held.
    {
        MenuKeyLatch k;
        k.keyDown(kDown);
        k.keyDown(kSelect);
        k.keyUp(kSelect);
        k.clearLatch();
        CHECK(k.takeFrame() == kDown);
        k.keyUp(kDown);
        CHECK(k.takeFrame() == 0);
    }
    // A press that arrives after a frame read lands in the next frame.
    {
        MenuKeyLatch k;
        CHECK(k.takeFrame() == 0);
        k.keyDown(kDown);
        k.keyUp(kDown);
        CHECK(k.takeFrame() == kDown);
    }
    std::printf("menu_key_latch: %d checks passed\n", checks);
    return 0;
}
