#include <renderassets/box_color.h>
#include <cstdio>
#include <cstdlib>

int main()
{
    // Oracle captured from the Linux reference, including GCC's B,G,R order.
    const wf_render::BoxRGB expected[] = {
        {193,72,129}, {141,239,51}, {175,188,132}, {203,158,27}
    };
    wf_render::BoxColorSequence colors;
    wf_render::BoxColorSequence independent;
    uint32_t checksum = 2166136261u;
    for (unsigned i = 0; i < 10000; ++i) {
        const auto c = colors.NextColor();
        std::srand(i + 7);
        (void)std::rand(); // libc state must have no effect on visual colors.
        const auto other = independent.NextColor();
        if (c.red != other.red || c.green != other.green || c.blue != other.blue)
            return 1;
        if (i < 4 && (c.red != expected[i].red || c.green != expected[i].green
                                              || c.blue != expected[i].blue))
            return 2;
        for (uint8_t v : {c.red, c.green, c.blue})
            checksum = (checksum ^ v) * 16777619u;
    }
    if (checksum != 0x71e4fa59u) {
        std::fprintf(stderr, "FAIL: box color checksum %08x\n", checksum);
        return 3;
    }
    std::puts("PASS: 10000 box colors match Linux reference; independent of libc RNG");
}
