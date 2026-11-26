// The `cpuinfo` test of WF Native Tests: what the CPU and the kernel tell a process of this ABI.
// Plan: docs/plans/2026-11-26-device-native-test-route.md. Prints to stdout, which the runner has
// pointed at wf.log. A 32-bit process on an ARMv8 kernel sees the compat /proc/cpuinfo, whose
// Features line is what our armeabi-v7a code can use.
#include <sys/auxv.h>
#include <sys/system_properties.h>
#include <sys/utsname.h>

#include <cerrno>
#include <cstdio>
#include <cstring>

namespace {

void cat(const char* path)
{
    FILE* f = std::fopen(path, "r");
    if (!f) {
        std::printf("(unreadable: %s)\n", std::strerror(errno));
        return;
    }
    char buf[4096];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) std::fwrite(buf, 1, n, stdout);
    std::fclose(f);
}

void line_of(const char* label, const char* path)
{
    char buf[256] = {0};
    FILE* f = std::fopen(path, "r");
    if (!f) return;                                  // absent cores and unreadable nodes are skipped
    if (std::fgets(buf, sizeof buf, f)) {
        buf[std::strcspn(buf, "\n")] = 0;
        std::printf("%s %s\n", label, buf);
    }
    std::fclose(f);
}

}  // namespace

int wf_nt_cpuinfo()
{
    std::printf("--- /proc/cpuinfo\n");
    cat("/proc/cpuinfo");

    std::printf("--- uname\n");
    utsname u{};
    if (uname(&u) == 0) std::printf("%s %s %s %s\n", u.sysname, u.release, u.version, u.machine);

    std::printf("--- auxv\n");
    std::printf("AT_HWCAP 0x%lx\n", getauxval(AT_HWCAP));
    std::printf("AT_HWCAP2 0x%lx\n", getauxval(AT_HWCAP2));
    const char* platform = reinterpret_cast<const char*>(getauxval(AT_PLATFORM));
    std::printf("AT_PLATFORM %s\n", platform ? platform : "(none)");

    std::printf("--- properties\n");
    const char* props[] = {"ro.product.cpu.abi", "ro.product.cpu.abilist", "ro.soc.manufacturer", "ro.soc.model",
                           "ro.hardware", "ro.board.platform", "ro.product.device", "ro.product.model",
                           "ro.build.fingerprint"};
    for (const char* p : props) {
        char value[PROP_VALUE_MAX] = {0};
        __system_property_get(p, value);
        std::printf("%s=%s\n", p, value);
    }

    std::printf("--- cpufreq\n");
    line_of("possible", "/sys/devices/system/cpu/possible");
    for (int cpu = 0; cpu < 16; ++cpu) {
        char path[96], label[32];
        std::snprintf(path, sizeof path, "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", cpu);
        std::snprintf(label, sizeof label, "cpu%d max_khz", cpu);
        line_of(label, path);
    }

    std::printf("--- compiled for\n");
#if defined(__aarch64__)
    std::printf("aarch64");
#elif defined(__arm__)
    std::printf("arm __ARM_ARCH=%d", __ARM_ARCH);
#endif
#if defined(__ARM_NEON)
    std::printf(" neon");
#endif
#if defined(__ARM_FP)
    std::printf(" __ARM_FP=0x%x", __ARM_FP);
#endif
#if defined(__ARM_FEATURE_FMA)
    std::printf(" fma");
#endif
#if defined(__ARM_FEATURE_DIRECTED_ROUNDING)
    std::printf(" directed-rounding");
#endif
    std::printf("\n");
    return 0;
}
