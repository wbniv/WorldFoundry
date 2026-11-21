// tests/test_ios_launch_args.py: which iOS launch arguments reach the engine
// (hal/ios/launch_args.hp). The regression case is Codemagic build 6af131a7:
// the XCUITest tour launched the Finding Your Way chapter with
// "-WFTouchDiagnostics 1 -WFOrientation landscape", the engine read "1" as the
// starting level and aborted in Level::Level.
#include <hal/args_file.hp>
#include <hal/ios/launch_args.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using Args = std::vector<std::string>;

static int checks = 0;

static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "ios_launch_args_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}

// game/main.cc: ParseCommandLine stops at the first argument that does not
// start with '-' or '/'; PIGSMain then takes atoi() of it as the starting
// level, or -1 (the level the game picks) when every argument is a switch.
static int StartingLevel(const Args& argv)
{
    std::size_t i = 1;
    while (i < argv.size() && (argv[i][0] == '-' || argv[i][0] == '/'))
        ++i;
    return i < argv.size() ? std::atoi(argv[i].c_str()) : -1;
}

// The chapter's bundled wf_args.txt (Finding Your Way v0.11), as in args_file_test.cc.
static const char kChapterArgs[] =
    "--vram-width=5120 --vram-height=2048 --vram-slot-width=1024 --vram-slot-height=512\n"
    "--vram-perm-width=2048 --vram-perm-height=1024 --static-mesh=1 --static-mesh-shared-index=1\n";

static Args Engine(const Args& launch)
{
    return wfargs::ComposeArgs("wf_game", kChapterArgs, wfios::EngineLaunchArgs(launch));
}

int main()
{
    // Build 6af131a7's XCUITest launch: before, "1" became the starting level.
    const Args uitest = { "--authored-aspect=1.778", "--maximum-aspect=2.25",
                          "-WFTouchDiagnostics", "1", "-WFOrientation", "landscape" };
    Check(StartingLevel(wfargs::ComposeArgs("wf_game", kChapterArgs, uitest)) == 1,
          "the unfiltered XCUITest arguments select level 1 (the bug this guards)");
    const Args e = Engine(uitest);
    Check(StartingLevel(e) == -1, "filtered: no starting level from the defaults pairs");
    Check(e.size() == 1 + 8 + 2, "argv0, 8 file arguments, the two aspect switches");
    Check(e[9] == "--authored-aspect=1.778" && e[10] == "--maximum-aspect=2.25",
          "engine switches keep their order after the file's");

    // The chapter run's simctl launch and the portrait HUD tour.
    Check(Engine({ "--authored-aspect=1.778", "-WFOrientation", "portrait" }).size() == 10,
          "-WFOrientation portrait dropped");
    Check(Engine({ "-WFTouchScript", "a@22+0.5,up@27+2" }).size() == 9, "-WFTouchScript dropped");

    // UIKit / XCTest defaults pairs.
    Check(Engine({ "-NSTreatUnknownArgumentsAsOpen", "NO", "-ApplePersistenceIgnoreState", "YES" }).size() == 9,
          "-NS... and -Apple... pairs dropped");
    Check(Engine({ "-AppleLanguages", "(en)", "--static-mesh=0" }).back() == "--static-mesh=0",
          "a switch after a pair survives");

    // Engine switches that look close but are not defaults keys.
    const Args keep = { "-Lcd.iff", "-rate30", "-W", "-WF", "-NSlower", "--no-fps", "-Applesauce" };
    const Args k = wfios::EngineLaunchArgs(keep);
    Check(k == keep, "-L<path>, -rateN, bare prefixes and lower case after a prefix pass through");

    // A key with no value at the end is dropped alone.
    Check(wfios::EngineLaunchArgs({ "--no-fps", "-WFOrientation" }) == Args{ "--no-fps" },
          "a trailing key without a value");
    Check(wfios::EngineLaunchArgs({}).empty(), "no launch arguments");

    std::printf("ios_launch_args_test: PASS (%d checks)\n", checks);
    return 0;
}
