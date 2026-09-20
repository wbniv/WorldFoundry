// Deterministic colors for procedural MODEL_TYPE_BOX meshes.
#ifndef WF_RENDERASSETS_BOX_COLOR_H
#define WF_RENDERASSETS_BOX_COLOR_H

#include <array>
#include <cstdint>

namespace wf_render {

struct BoxRGB {
    uint8_t red, green, blue;
};

// Preserve the Linux/glibc seed-1 color sequence without depending on libc's
// rand() algorithm or the compiler's argument evaluation order. This private
// visual stream also cannot be perturbed by gameplay's random draws.
// Algorithm: degree-31 additive feedback, separation 3, modulo 2^32; discard
// the low bit. Seed with Park-Miller and warm up for 10 * 31 draws.
class BoxColorSequence {
public:
    BoxColorSequence()
    {
        state_[0] = 1;
        for (unsigned i = 1; i < state_.size(); ++i)
            state_[i] = uint32_t(uint64_t(state_[i-1]) * 16807 % 2147483647);
        for (unsigned i = 0; i < 310; ++i)
            Next();
    }

    BoxRGB NextColor()
    {
        // GCC evaluated the old Color(rand(), rand(), rand()) blue first.
        // Sequence these calls explicitly so Clang produces the same RGB.
        const auto blue  = uint8_t(Next() % 230 + 26);
        const auto green = uint8_t(Next() % 230 + 26);
        const auto red   = uint8_t(Next() % 230 + 26);
        return {red, green, blue};
    }

private:
    uint32_t Next()
    {
        state_[front_] += state_[rear_];
        const uint32_t value = state_[front_] >> 1;
        front_ = (front_ + 1) % state_.size();
        rear_  = (rear_ + 1) % state_.size();
        return value;
    }

    std::array<uint32_t, 31> state_{};
    unsigned front_ = 3;
    unsigned rear_ = 0;
};

} // namespace wf_render
#endif
