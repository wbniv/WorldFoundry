// CTest args_file: the wf_args.txt parser shared by the Android and iOS apps
// (hal/args_file.hp). The Android section checks it against Android's old
// strtok loop on the shipped files and 20000 generated ones. The first case is the Finding Your Way v0.11
// APK's own assets/wf_args.txt, byte for byte; without these arguments the
// chapter aborts at level load with "LoadTexture: 2048x1024 texture does not
// fit its 256x256 VRAM slot" (the 2026-10-31 iOS attempts).
#include <hal/args_file.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static int checks = 0;

static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "args_file_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}

using Args = std::vector<std::string>;

// The file as hal/android/native_app_entry.cc reads it: at most 1023 bytes
// (AAsset_read into a 1024-byte buffer), NUL-terminated.
static void AndroidRead(const std::string& file, char (&buf)[1024])
{
    const std::size_t n = file.size() < sizeof(buf) - 1 ? file.size() : sizeof(buf) - 1;
    std::memcpy(buf, file.data(), n);
    buf[n] = '\0';
}

// Android's loop before it used hal/args_file.hp (2026-new-level 45915d33,
// native_app_entry.cc lines 788-812), verbatim but for the logging and the
// logo setting, which here records the qr_logo= token instead.
static void OldAndroidLoop(const std::string& file, Args& out, Args& qr)
{
    static char argBuf[1024];
    AndroidRead(file, argBuf);
    char arg0[] = "wf_game";
    char* argv[33] = { arg0 };
    int argc = 1;
    for (char* tok = strtok(argBuf, " \t\r\n"); tok && argc < 32; tok = strtok(nullptr, " \t\r\n"))
    {
        if (std::strncmp(tok, "qr_logo=", 8) == 0)
        {
            qr.push_back(tok);
            continue;
        }
        argv[argc++] = tok;
    }
    argv[argc] = nullptr;
    out.assign(argv, argv + argc);
}

// Android's code now: the same read, then the shared parser with the same cap.
static void NewAndroidPath(const std::string& file, Args& out, Args& settings)
{
    static char argBuf[1024];
    AndroidRead(file, argBuf);
    out.assign(1, "wf_game");
    wfargs::SplitArgsText(std::string(argBuf), out, &settings, 32);
}

int main()
{
    const std::string chapter =
        "--vram-width=5120\n--vram-height=2048\n--vram-slot-width=1024\n"
        "--vram-slot-height=512\n--vram-perm-width=2048\n--vram-perm-height=1024\n"
        "--static-mesh=1\n--static-mesh-shared-index=1\n";
    const Args chapterArgs = {
        "--vram-width=5120", "--vram-height=2048", "--vram-slot-width=1024",
        "--vram-slot-height=512", "--vram-perm-width=2048", "--vram-perm-height=1024",
        "--static-mesh=1", "--static-mesh-shared-index=1"};

    Args a = wfargs::ComposeArgs("wf_game", chapter, {});
    Args want = {"wf_game"};
    want.insert(want.end(), chapterArgs.begin(), chapterArgs.end());
    Check(a == want, "v0.11 APK wf_args.txt gives argv0 plus its eight arguments");

    // No file (or an empty one): argv0 only, the behaviour before wf_args.txt.
    Check(wfargs::ComposeArgs("wf_game", "", {}) == Args{"wf_game"}, "empty file");
    Check(wfargs::ComposeArgs("wf_game", " \t\r\n\n", {}) == Args{"wf_game"}, "whitespace-only file");
    Check(wfargs::ComposeArgs(nullptr, "", {}) == Args{"wf_game"}, "null argv0 defaults to wf_game");

    // Separators: space, tab, CR, LF, runs of them; no trailing newline.
    Args b;
    wfargs::SplitArgsText("  --a=1\t--b=2\r\n--c=3   --d=4", b);
    Check(b == (Args{"--a=1", "--b=2", "--c=3", "--d=4"}), "mixed separators, no trailing newline");

    // qr_logo= is an app setting: never an engine argument.
    Args settings;
    Args c = wfargs::ComposeArgs("wf_game", "--x=1 qr_logo=none\n--y=2\n", {}, &settings);
    Check(c == (Args{"wf_game", "--x=1", "--y=2"}), "qr_logo= is not passed to the engine");
    Check(settings == Args{"qr_logo=none"}, "qr_logo= is returned as a setting");
    Args d = wfargs::ComposeArgs("wf_game", "qr_logo=full", {});
    Check(d == Args{"wf_game"}, "qr_logo= is dropped when settings is null");

    // Launch arguments (simctl launch ... --flag) come after the file's, so a
    // CI run can override a bundled value with the engine's last-one-wins rule.
    Args e = wfargs::ComposeArgs("wf_game", "--vram-slot-height=512\n",
                                 {"--vram-slot-height=2048", "--no-fps"});
    Check(e == (Args{"wf_game", "--vram-slot-height=512", "--vram-slot-height=2048", "--no-fps"}),
          "launch arguments follow the file's arguments");

    // ---- Android: the shared parser gives what the old strtok loop gave ----
    // The v0.11 APK's file is the `chapter` text above, all 175 bytes of it.
    Check(chapter.size() == 175, "the chapter text is the APK's 175-byte file");
    // Byte for byte: android/app/src/{aquarium,condo}/assets/wf_args.txt.
    const std::string aquarium =
        "--vram-width=2048\n--vram-height=1024\n--vram-slot-width=512\n"
        "--vram-slot-height=512\n--vram-perm-width=1024\n--vram-perm-height=1024\n";
    const std::string condo =
        "--vram-width=4096\n--vram-height=2048\n--vram-slot-width=1024\n"
        "--vram-slot-height=1024\n--vram-perm-width=1024\n--vram-perm-height=1024\n";
    Check(aquarium.size() == 129 && condo.size() == 131, "aquarium and condo texts are their files' sizes");

    std::vector<std::string> inputs = {
        chapter, aquarium, condo,
        aquarium + "--frame-profile\n",                    // scripts/build-aquarium-variant.py --profile
        chapter + "\n--frame-profile\n",                   // scripts/build-seahorse-close-variants.py
        "--frame-profile\n",
        "", " ", "\n\n\r\n\t",
        "qr_logo=planet\n", "qr_logo=full --x=1", "--x=1 qr_logo=none\n--y=2", "qr_logo=bogus",
        "qr_logo=", "qr_log", "qr_logo", "xqr_logo=full", "QR_LOGO=full",
        std::string("--a=1\0--hidden=2", 16),              // strtok stops at a NUL byte
        std::string(1100, 'x'),                            // longer than the 1023 bytes read
        std::string(1020, ' ') + "--cut-off-here",         // a token across the 1023-byte limit
    };
    {
        // Past the argv cap: 40 arguments, then settings before, at and after the 31st.
        std::string many, qrAt31;
        for (int i = 0; i < 40; ++i) many += "--a" + std::to_string(i) + " ";
        inputs.push_back(many);
        for (int i = 0; i < 31; ++i) qrAt31 += "--a" + std::to_string(i) + " ";
        inputs.push_back("qr_logo=full " + qrAt31 + "qr_logo=none --late");
        inputs.push_back(qrAt31.substr(0, qrAt31.size() - 5) + " qr_logo=none " + "--b1 --b2 --b3");
    }
    {
        // Deterministic random files over the characters that matter to either parser.
        static const char* const kPieces[] = {"-", "-", "a", "=", "1", " ", "\t", "\r", "\n", "  ",
                                              "qr_logo=", "qr_logo=full", "--vram-width=5120", "\0"};
        unsigned seed = 20261101u;
        for (int c = 0; c < 20000; ++c)
        {
            std::string s;
            seed = seed * 1664525u + 1013904223u;
            const int len = static_cast<int>(seed >> 22);                  // 0..1023 pieces
            for (int k = 0; k < len; ++k)
            {
                seed = seed * 1664525u + 1013904223u;
                const char* p = kPieces[(seed >> 16) % 14];
                s.append(p, *p ? std::strlen(p) : 1);
            }
            inputs.push_back(s);
        }
    }
    int same = 0;
    for (const std::string& in : inputs)
    {
        Args oldArgs, oldSettings, newArgs, newSettings;
        OldAndroidLoop(in, oldArgs, oldSettings);
        NewAndroidPath(in, newArgs, newSettings);
        if (oldArgs != newArgs || oldSettings != newSettings)
        {
            std::fprintf(stderr, "args_file_test: Android old/new differ on %zu-byte input\n", in.size());
            Check(false, "Android old loop and shared parser agree");
        }
        ++same;
    }
    Check(same == static_cast<int>(inputs.size()), "every input compared");
    Args apkOld, apkSet;
    OldAndroidLoop(chapter, apkOld, apkSet);
    Check(apkOld == want && apkSet.empty(), "old Android loop also gives argv0 plus the APK's eight arguments");
    {
        // The limit cases are reached, not just agreed on.
        Args capped, cappedSettings;
        NewAndroidPath(inputs[inputs.size() - 20003], capped, cappedSettings);   // the 40-argument file
        Check(capped.size() == 32 && capped.back() == "--a30", "the cap keeps argv0 plus 31 arguments");
        Args late, lateSettings;
        NewAndroidPath(inputs[inputs.size() - 20002], late, lateSettings);
        Check(late.size() == 32 && lateSettings == Args{"qr_logo=full"}, "nothing after the 31st argument is read");
        Args nul, nulSettings;
        NewAndroidPath(std::string("--a=1\0--hidden=2", 16), nul, nulSettings);
        Check(nul == (Args{"wf_game", "--a=1"}), "text after a NUL byte is ignored");
    }
    std::printf("args_file_test: Android old loop == shared parser on %d inputs\n", same);

    std::printf("args_file_test: PASS (%d checks)\n", checks);
    return 0;
}
