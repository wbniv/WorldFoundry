#include <game/doom_fire.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static void Check(bool ok, const char* message)
{
    if (!ok) { std::fprintf(stderr, "doom_fire_test: %s\n", message); std::exit(1); }
}

int main()
{
    DoomFireField a(24, 27, 0x12345678), b(24, 27, 0x12345678), c(24, 27, 0x87654321);
    Check(a.Width() == 24 && a.Height() == 27, "field dimensions");
    Check(std::memcmp(a.Pixels(), b.Pixels(), 24 * 27 * 4) == 0, "same seed must be repeatable");
    Check(std::memcmp(a.Pixels(), c.Pixels(), 24 * 27 * 4) != 0, "different seeds must differ");
    for (int i = 0; i < 24 * 27; ++i) {
        Check(a.Pixels()[i * 4 + 3] == 255, "palette alpha stays opaque");
        Check(a.Pixels()[i * 4] >= 220 && a.Pixels()[i * 4 + 1] >= 65,
              "cold cells must stay luminous orange, never near-black");
    }
    int warm = 0;
    for (int y = 3; y < 24; ++y)
        for (int x = 6; x < 18; ++x)
            if (a.Pixels()[(y * 24 + x) * 4 + 1] > 90) ++warm;
    Check(warm > 180, "heat must fill the flame body instead of dying in scatter holes");

    const std::vector<unsigned char> still(a.Pixels(), a.Pixels() + 24 * 27 * 4);
    Check(a.Advance(10.0, true, false), "initial image is pending upload");
    Check(std::memcmp(a.Pixels(), still.data(), 24 * 27 * 4) == 0, "reduced motion image is stable");
    Check(!a.Advance(10.05, true, false), "unchanged reduced image is not re-uploaded");
    Check(!a.Advance(100.0, false, true), "modal pauses updates");
    Check(!a.Advance(100.0, false, false), "modal time does not cause catch-up");
    Check(a.Advance(100.05, false, false), "fixed step advances the field");
    Check(std::memcmp(a.Pixels(), still.data(), 24 * 27 * 4) != 0, "normal motion changes the heat field");
}
