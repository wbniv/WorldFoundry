// Touch navigation for the Aquarium and Clocks phone choosers, without an on-screen gamepad.
#pragma once

#include <cmath>
#include <cstdint>
#include <hal/touch_controls.h>
#include "menu_key_latch.h"

class ClockMenuTouch {
public:
    void down(int pointer, float x, float y, int row) {
        if (pointer_ >= 0) return;
        pointer_ = pointer;
        x_ = x;
        y_ = y;
        row_ = row;
        dragged_ = false;
    }

    void move(int pointer, float y, MenuKeyLatch& keys) {
        if (pointer != pointer_) return;
        const float dy = y - y_;
        if (!dragged_ && std::fabs(dy) < 32.f) return;
        dragged_ = true;
        const uint32_t next = dy < 0 ? wftouch::Down : wftouch::Up;
        if (next != held_) {
            if (held_) keys.keyUp(held_);
            keys.keyDown(next);
            held_ = next;
        }
    }

    int up(int pointer, float x, float y, int row, MenuKeyLatch& keys) {
        if (pointer != pointer_) return -1;
        const int chosen = !dragged_ && row_ >= 0 && row == row_ &&
                           std::fabs(x - x_) < 24.f && std::fabs(y - y_) < 24.f ? row : -1;
        cancel(keys);
        return chosen;
    }

    void cancel(MenuKeyLatch& keys) {
        if (held_) keys.keyUp(held_);
        held_ = 0;
        pointer_ = -1;
        row_ = -1;
        dragged_ = false;
    }

private:
    int pointer_ = -1;
    int row_ = -1;
    float x_ = 0;
    float y_ = 0;
    bool dragged_ = false;
    uint32_t held_ = 0;
};
