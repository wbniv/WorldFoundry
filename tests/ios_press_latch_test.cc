// tests/test_ios_press_latch.py: a touch press lasts until the engine has read
// it (hal/ios/press_latch.hp). The regression case is Codemagic build 6b01461c:
// a 51 ms XCUITest tap on C, iPad landscape, began and ended between two
// engine samples, and the card stayed open.
#include <hal/ios/press_latch.hp>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>

static int checks = 0;

static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "ios_press_latch_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}

enum : uint32_t { A = 0x1, B = 0x2, C = 0x4, D = 0x8, UP = 0x800, RIGHT = 0x2000 };

int main()
{
    {   // 6b01461c: press and release before the engine's next read.
        wfios::PressLatch l;
        l.Set(C); l.Set(0);
        Check(l.Held() == 0, "current state alone loses the tap (the bug)");
        Check(l.Read() == C, "the tap is read");
        Check(l.Read() == C, "and stays for every read of that frame");
        l.FrameEnd();
        Check(l.Read() == 0, "released after the frame that read it");
    }
    {   // No frame read it yet: it waits, however many frames pass unread.
        wfios::PressLatch l;
        l.Set(A); l.Set(0);
        l.FrameEnd(); l.FrameEnd();
        Check(l.Read() == A, "an unread press survives frames with no read");
        l.FrameEnd();
        Check(l.Read() == 0, "then goes");
    }
    {   // A press after the frame's reads belongs to the next frame.
        wfios::PressLatch l;
        Check(l.Read() == 0, "nothing pressed");
        l.Set(B); l.Set(0);
        l.FrameEnd();
        Check(l.Read() == B, "pressed after the read, seen next frame");
    }
    {   // A held button is held; its release is not delayed past a read frame.
        wfios::PressLatch l;
        l.Set(UP);
        Check(l.Read() == UP, "held");
        l.FrameEnd();
        Check(l.Read() == UP, "still held next frame");
        l.FrameEnd();
        l.Set(0);
        Check(l.Read() == 0, "release of a long hold is immediate");
    }
    {   // A held button and a short tap on another: both seen, the tap once.
        wfios::PressLatch l;
        l.Set(RIGHT);
        l.Set(RIGHT | D); l.Set(RIGHT);
        Check(l.Read() == (RIGHT | D), "chord with a short tap");
        l.FrameEnd();
        Check(l.Read() == RIGHT, "the tap goes, the hold stays");
    }
    {   // Suspend drops everything.
        wfios::PressLatch l;
        l.Set(A | B); l.Set(0);
        l.Clear();
        Check(l.Read() == 0 && l.Held() == 0, "Clear drops held and latched");
    }
    {   // Two threads, as on iOS: 20000 taps of 0.0 s, each must be read.
        wfios::PressLatch l;
        std::atomic<uint32_t> engineSaw{0};
        std::atomic<bool> stop{false};
        std::thread engine([&] {
            while (!stop.load()) {
                engineSaw.fetch_or(l.Read());
                l.FrameEnd();
            }
        });
        const uint32_t bits[] = { A, B, C, D, UP, RIGHT };
        bool all = true;
        for (int i = 0; i < 20000 && all; ++i) {
            const uint32_t bit = bits[i % 6];
            engineSaw.fetch_and(~bit);
            l.Set(bit); l.Set(0);
            long spins = 0;
            while (!(engineSaw.load() & bit) && ++spins < 2000000000L) std::this_thread::yield();
            all = (engineSaw.load() & bit) != 0;
        }
        stop.store(true);
        engine.join();
        Check(all, "every tap reached the engine thread");
    }
    std::printf("ios_press_latch_test: PASS (%d checks)\n", checks);
    return 0;
}
