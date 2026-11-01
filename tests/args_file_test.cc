// CTest args_file: the wf_args.txt parser shared by Android's format and the
// iOS app (hal/args_file.hp). The first case is the Finding Your Way v0.11
// APK's own assets/wf_args.txt, byte for byte; without these arguments the
// chapter aborts at level load with "LoadTexture: 2048x1024 texture does not
// fit its 256x256 VRAM slot" (the 2026-10-31 iOS attempts).
#include <hal/args_file.hp>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static int checks = 0;

static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "args_file_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}

using Args = std::vector<std::string>;

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

    std::printf("args_file_test: PASS (%d checks)\n", checks);
    return 0;
}
