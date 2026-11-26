// The `fmaf-probe` test of WF Native Tests: why the device's fmaf can differ from glibc's.
// Plan: docs/plans/2026-11-26-device-native-test-route.md ("Findings"). Found by the first device run of
// tests/forth_math_agreement.py: on both Chromecasts (armeabi-v7a, VFPv3 code, so no vfma and fmaf is
// bionic's software routine) fma(1.000244140625, 1.000244140625, -1e-24) came back 0x3f801001, one ulp
// above the correctly rounded 0x3f801000 that glibc and the vector oracle give.
//
// FreeBSD msun's s_fmaf.c, which bionic carries, computes x*y exactly in double, adds z, and in the one
// case where that double sits exactly halfway between two floats it recomputes the sum rounding toward
// zero and nudges the low word up when the two sums are equal. The probe prints what this process sees:
// the library's fmaf, whether fesetround(FE_TOWARDZERO) changes a double addition here, and the same
// algorithm written out with volatile operands so the compiler cannot merge the two additions.
#include <dlfcn.h>
#include <fenv.h>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

uint32_t fbits(float f) { uint32_t u; std::memcpy(&u, &f, sizeof u); return u; }
uint64_t dbits(double d) { uint64_t u; std::memcpy(&u, &d, sizeof u); return u; }

// msun s_fmaf.c, with every intermediate forced through memory.
float msun_fmaf(float x, float y, float z)
{
    volatile double xy = static_cast<double>(x) * y;
    volatile double result = xy + z;
    const uint64_t r = dbits(result);
    const uint32_t lr = static_cast<uint32_t>(r), hr = static_cast<uint32_t>(r >> 32);
    if ((lr & 0x1fffffff) != 0x10000000 || (hr & 0x7ff00000) == 0x7ff00000 || result - xy == z ||
        fegetround() != FE_TONEAREST)
        return static_cast<float>(result);
    fesetround(FE_TOWARDZERO);
    volatile double adjusted = xy + z;
    fesetround(FE_TONEAREST);
    double out = adjusted;
    if (result == adjusted) {
        uint64_t a = dbits(out);
        a = (a & 0xffffffff00000000ull) | static_cast<uint32_t>(lr + 1);
        std::memcpy(&out, &a, sizeof out);
    }
    return static_cast<float>(out);
}

}  // namespace

int wf_nt_fmaf_probe()
{
    volatile float a = 1.000244140625f, b = 1.000244140625f, c = -1.0000000195414814e-24f, cp = 1.0000000195414814e-24f;
    Dl_info info{};
    const bool found = dladdr(reinterpret_cast<void*>(static_cast<float (*)(float, float, float)>(&::fmaf)), &info);
    std::printf("fmaf from %s\n", found && info.dli_fname ? info.dli_fname : "(unknown)");
    std::printf("library fmaf(a, a, -1e-24) %08x   (correctly rounded: 3f801000)\n", (unsigned)fbits(::fmaf(a, b, c)));
    std::printf("library fmaf(a, a, +1e-24) %08x   (correctly rounded: 3f801001)\n", (unsigned)fbits(::fmaf(a, b, cp)));
    std::printf("written-out msun fmaf(a, a, -1e-24) %08x\n", (unsigned)fbits(msun_fmaf(a, b, c)));
    std::printf("written-out msun fmaf(a, a, +1e-24) %08x\n", (unsigned)fbits(msun_fmaf(a, b, cp)));

    volatile double one = 1.0, tiny = -1e-30;
    std::printf("fegetround() at start %d (FE_TONEAREST %d)\n", fegetround(), FE_TONEAREST);
    const int set = fesetround(FE_TOWARDZERO);
    const int now = fegetround();
    volatile double tz = one + tiny;
    fesetround(FE_TONEAREST);
    volatile double tn = one + tiny;
    std::printf("fesetround(FE_TOWARDZERO) returned %d, fegetround() then %d (FE_TOWARDZERO %d)\n", set, now, FE_TOWARDZERO);
    std::printf("1 + -1e-30 toward zero %016llx, to nearest %016llx  (a working mode change gives 3fefffffffffffff, 3ff0000000000000)\n",
                (unsigned long long)dbits(tz), (unsigned long long)dbits(tn));
    return 0;
}
