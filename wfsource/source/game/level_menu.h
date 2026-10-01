//=============================================================================
// game/level_menu.h: the level menu of multi-level bundles (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// A bundle built with `cdpack --manifest` (task build-cd-iff-smb-menu) carries a
// MENU chunk as its last TOC entry: a title, a prompt and one name per level.
// Its shell (shell-menu.fth) writes -1 to LEVEL_TO_RUN on the first pass, and
// WFGame::RunGameScript then runs this menu instead of a level: up/down move,
// A (the remote's OK) starts. The chosen index goes to LEVEL_TO_RUN.
//
// Everything here is pure logic plus geometry, like hal/phonepad/phonepad_overlay:
// the menu is a list of solid rectangles (text from stb_easy_font) that each
// platform draws (desktop: gfx/gl/display.cc). The tests compile this file with
// level_menu_host.cc on Linux and drive it with a fake clock (tests/test_level_menu.py).
// Plan: docs/plans/2026-10-01-level-menu-selector.md
//=============================================================================

#ifndef GAME_LEVEL_MENU_H
#define GAME_LEVEL_MENU_H

#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

#include "../hal/phonepad/phonepad_overlay.h"   // PhonepadRect: the rectangle type Android already draws

namespace levelmenu
{

// LEVEL_TO_RUN value meaning "ask the player" (written by shell-menu.fth). The engine
// treats any negative value so: Forth's -1 reaches WFGame as -2 (float WholePart floors).
constexpr int kAskPlayer = -1;

// The joystick bits the menu reads (EJ_BUTTONF_* in hal/sjoystic.h; kept as numbers
// so this file needs no engine header; level_menu_host.cc checks they agree).
constexpr uint32_t kButtonA    = 1u << 0;
constexpr uint32_t kButtonUp   = 1u << 11;
constexpr uint32_t kButtonDown = 1u << 12;

constexpr int     kVisibleRows    = 6;
constexpr int64_t kRepeatDelayMs  = 400;    // a held up/down repeats after this...
constexpr int64_t kRepeatEveryMs  = 120;    // ...every this
constexpr int64_t kReleaseWaitMs  = 1500;   // start anyway if a button stays down this long
constexpr size_t  kMaxText        = 60;     // cdpack refuses longer names

// ---- the MENU chunk -------------------------------------------------------

struct TocEntry
{
    uint32_t tag, offset, size;
};

struct Entry
{
    int         level;   // TOC level index (LEVEL_TO_RUN value)
    std::string name;
};

struct Bundle
{
    std::string        title, prompt;
    std::vector<Entry> entries;
};

uint32_t Tag(const char (&s)[5]);

// Sector 0 of a cd.iff: GAME header, TOC chunk. False if it is not one.
bool ParseToc(const uint8_t* sector0, size_t n, std::vector<TocEntry>* out);
// The MENU entry, which must be the last TOC entry; *levelCount = entries - SHEL - MENU.
bool FindMenu(const std::vector<TocEntry>& toc, TocEntry* menu, int* levelCount);
// The MENU chunk (starting at its 'MENU' tag, `n` = TOC size). False with *err on any
// malformation, an index >= levelCount, or text the font cannot draw.
bool ParseMenu(const uint8_t* chunk, size_t n, int levelCount, Bundle* out, std::string* err);

// ---- the menu --------------------------------------------------------------

class Menu
{
public:
    Menu(Bundle bundle, int cursor, std::string hint);

    // One frame: the joystick bits held now, and the time. Buttons already held on the
    // first call are ignored until released (so a held key cannot pick a level).
    void Update(uint32_t buttons, int64_t nowMs);

    bool Chosen() const { return phase_ != Phase::Choosing; }   // A pressed
    bool Done() const   { return phase_ == Phase::Done; }       // ...and released: start the level
    int  Cursor() const { return cursor_; }
    int  First() const  { return first_; }                      // the top visible row
    int  ChosenLevel() const { return bundle_.entries[size_t(cursor_)].level; }
    const Bundle& GetBundle() const { return bundle_; }

    // The rectangles for a w x h surface (pixels, origin top-left). Returns true when
    // the list differs from the previous call's (a GPU-side caller re-uploads only then).
    bool Build(int w, int h, std::vector<PhonepadRect>* out);

    // The text actually drawn for entry i at the row width (cut with "..." if too wide).
    std::string RowText(int i) const;

private:
    enum class Phase { Choosing, WaitRelease, Done };
    void Move(int delta);

    Bundle      bundle_;
    std::string hint_;
    int         cursor_ = 0, first_ = 0;
    Phase       phase_ = Phase::Choosing;
    bool        primed_ = false;
    uint32_t    prev_ = 0;
    int         heldDir_ = 0;
    int64_t     repeatAt_ = 0, chosenAt_ = 0;
    std::string lastKey_;
};

// How the engine should treat a bundle: -1 = show the menu, otherwise the level to start
// without one (one entry: that level; no entries: level 0).
int AutoPick(const Bundle& bundle);

// ---- scripted input (wf_game --menu-input=...) -----------------------------
// Tokens, comma-separated: up, down, a (a press frame then a release frame), wait:N
// (N empty frames), back (ask to return to the menu), quit (close the game).

struct ScriptFrame
{
    uint32_t buttons = 0;
    bool     back = false, quit = false;
};

class InputScript
{
public:
    bool Parse(const std::string& text, std::string* err);
    bool Active() const { return active_; }
    // The next frame; false once the script has run out (then real input applies).
    bool Next(ScriptFrame* out);
    size_t Left() const { return frames_.size(); }
private:
    std::deque<ScriptFrame> frames_;
    bool active_ = false;
};

// The engine's script (set by main.cc from --menu-input=; inactive otherwise).
InputScript& Script();

// ---- the platform side -----------------------------------------------------

// Draws the menu's rectangles over a cleared frame. Platforms that can register one
// (gfx/gl/display.cc on the Linux desktop); without one the engine starts entry 0.
using DrawFn = void (*)(const PhonepadRect* rects, int count, int w, int h);
void   SetDrawer(DrawFn fn);
DrawFn Drawer();

// The hint line for this platform (TV remote or desktop keyboard).
const char* PlatformHint();

// Return-to-menu requests (desktop: Backspace; mesa.cc calls RequestReturn). The engine
// consumes them only while a menu bundle's level runs.
void RequestReturn();
bool ConsumeReturnRequest();

}  // namespace levelmenu

#endif  // GAME_LEVEL_MENU_H
