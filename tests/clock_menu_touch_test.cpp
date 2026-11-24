#include "clock_menu_touch.h"
#include <cassert>

int main() {
    ClockMenuTouch touch;
    MenuKeyLatch keys;
    touch.down(1, 100, 200, 2);
    assert(touch.up(1, 101, 201, 2, keys) == 2);
    assert(keys.takeFrame() == 0);

    touch.down(1, 100, 300, 3);
    touch.move(1, 200, keys);
    assert(keys.takeFrame() == wftouch::Down);
    assert(keys.takeFrame() == wftouch::Down); // Hold supports menu repeat.
    assert(touch.up(1, 100, 200, 1, keys) == -1);
    assert(keys.takeFrame() == 0);

    touch.down(2, 100, 200, 1);
    touch.move(2, 300, keys);
    touch.up(2, 100, 300, 3, keys);
    assert(keys.takeFrame() == wftouch::Up); // A quick swipe survives one frame.
    assert(keys.takeFrame() == 0);

    touch.down(3, 100, 200, 1);
    touch.move(3, 150, keys);
    keys.takeFrame();
    touch.cancel(keys);
    assert(keys.takeFrame() == 0);
    assert(touch.up(3, 100, 150, 1, keys) == -1);
    return 0;
}
