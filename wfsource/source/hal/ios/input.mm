//=============================================================================
// hal/ios/input.mm: iOS input — touch D-pad + A/B → joystick bitmask
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 3 of docs/plans/2026-04-21-ios-port-codemagic.md. Mirrors the Android
// shim (hal/android/input.cc for the HAL entry points; the touch hit test and
// gamepad|touch merge in hal/android/native_app_entry.cc; the HUD overlay in
// gfx/gl/android_window.cc, commit c20e56e).
//
//   UITouch (main thread) → WFTouchHudView → wf_touch::TouchTracker
//     → wf_touch::HitTest (touch_pad.cc) → _HALSetJoystickButtons
//     → _JoystickButtonsF (engine thread)
//
// Layout math, hit testing and per-finger bookkeeping live in touch_pad.cc,
// which is platform-independent and unit-tested on Linux
// (tests/test_ios_touch_pad.py). This file is only the UIKit glue.
//
// Differences from Android, and why:
//   - The HUD is a UIKit overlay view, not GL/Metal quads drawn before the
//     swap: the Metal encoder handoff (Phase 2C-B) is not wired, so a
//     Metal-drawn HUD would never reach the screen, and an overlay keeps the
//     HUD independent of renderer state entirely.
//   - The button state is atomic: on iOS the engine runs on its own thread
//     (native_app_entry.mm) while UIKit delivers touches on the main thread.
//     On Android both happen on the game thread (WFAndroidPumpEvents).
//   - Pressed buttons are drawn brighter, so a Simulator screenshot shows
//     that a tap registered.
//=============================================================================

#import <UIKit/UIKit.h>
#import <QuartzCore/QuartzCore.h>

#include <hal/hal.h>

#include <algorithm>
#include <atomic>
#include <cstdlib>

#include "touch_pad.hp"
#import "touch_hud.h"

static_assert(wf_touch::kBtnA     == EJ_BUTTONF_A,     "touch_pad.hp kBtnA drifted");
static_assert(wf_touch::kBtnB     == EJ_BUTTONF_B,     "touch_pad.hp kBtnB drifted");
static_assert(wf_touch::kBtnUp    == EJ_BUTTONF_UP,    "touch_pad.hp kBtnUp drifted");
static_assert(wf_touch::kBtnDown  == EJ_BUTTONF_DOWN,  "touch_pad.hp kBtnDown drifted");
static_assert(wf_touch::kBtnLeft  == EJ_BUTTONF_LEFT,  "touch_pad.hp kBtnLeft drifted");
static_assert(wf_touch::kBtnRight == EJ_BUTTONF_RIGHT, "touch_pad.hp kBtnRight drifted");

//=============================================================================
// HAL joystick entry points — same set as hal/android/input.cc.

// Written on the main thread, read on the engine thread.
static std::atomic<joystickButtonsF> _buttons{0};

extern "C" void
_HALSetJoystickButtons(joystickButtonsF joystickButtons)
{
    _buttons.store(joystickButtons, std::memory_order_release);
}

// Public host-injection wrapper — see hal/_input.h. Cross-platform parity:
// any host that wants to feed button state to the engine without going
// through the platform event loop calls this.
void
HALInjectJoystickButtons(joystickButtonsF joystickButtons)
{
    _HALSetJoystickButtons(joystickButtons);
}

void _InitJoystickInterface(void) {}
void _TermJoystickInterface(void) {}

int _JoystickUserAbort(void)
{
    return (_buttons.load(std::memory_order_acquire) & 0x8000000) ? 1 : 0;
}

joystickButtonsF
_JoystickButtonsF(IJoystick joystick)
{
    SJoystick* self = ITEMRETRIEVE(joystick, SJoystick);
    if (self->_stickNum == EJW_JOYSTICK1)
        return _buttons.load(std::memory_order_acquire);
    return 0;
}

//=============================================================================
// Touch state. Main thread only.

namespace
{

// Merged and flushed to _HALSetJoystickButtons, as on Android. The gamepad
// half stays 0 until Phase 5 wires GCController (MFi).
joystickButtonsF      gGamepadButtons = 0;
joystickButtonsF      gTouchButtons   = 0;

wf_touch::Layout       gLayout;
wf_touch::TouchTracker gTracker;
bool                   gInputSuspended = false;
bool                   gHudEnabled     = true;
WFTouchHudView*        gHud            = nil;   // owned by the view hierarchy

void Emit()
{
    _HALSetJoystickButtons(gGamepadButtons | gTouchButtons);
}

// Recompute the touch bits from every tracked finger; log and redraw on a
// change (the log line is what the Simulator CI run greps for).
void RecomputeTouch()
{
    const joystickButtonsF now =
        (gInputSuspended || !gHudEnabled) ? 0 : gTracker.Buttons(gLayout);
    if (now != gTouchButtons)
    {
        NSLog(@"wf_game: touch buttons 0x%04x", (unsigned)now);
        gTouchButtons = now;
        [gHud setNeedsDisplay];
    }
    Emit();
}

inline uintptr_t TouchId(UITouch* t)
{
    // UIKit reuses the same UITouch object for a finger's whole sequence.
    return (uintptr_t)(__bridge void*)t;
}

}  // namespace

//=============================================================================

@implementation WFTouchHudView

- (instancetype)initWithFrame:(CGRect)frame
{
    self = [super initWithFrame:frame];
    if (!self) return nil;
    self.opaque                 = NO;
    self.backgroundColor        = [UIColor clearColor];
    self.multipleTouchEnabled   = YES;
    self.userInteractionEnabled = YES;
    self.contentMode            = UIViewContentModeRedraw;
    self.autoresizingMask       = UIViewAutoresizingFlexibleWidth
                                | UIViewAutoresizingFlexibleHeight;
    gHud = self;
    return self;
}

- (void)dealloc
{
    if (gHud == self) gHud = nil;
#if !__has_feature(objc_arc)
    [super dealloc];
#endif
}

- (void)layoutSubviews
{
    [super layoutSubviews];
    const CGSize       sz = self.bounds.size;
    const UIEdgeInsets in = self.safeAreaInsets;
    wf_touch::Insets insets;
    insets.top    = (float)in.top;
    insets.left   = (float)in.left;
    insets.bottom = (float)in.bottom;
    insets.right  = (float)in.right;
    gLayout = wf_touch::ComputeLayout((float)sz.width, (float)sz.height, insets);
    NSLog(@"wf_game: touch layout %gx%g pt, safe {%g,%g,%g,%g}, cell %.1f pt",
          sz.width, sz.height, in.top, in.left, in.bottom, in.right, gLayout.cell);
    [self setNeedsDisplay];
    RecomputeTouch();   // held fingers are re-hit-tested against the new layout
}

- (void)safeAreaInsetsDidChange
{
    [super safeAreaInsetsDidChange];
    [self setNeedsLayout];
}

- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    if (gInputSuspended) return;
    for (UITouch* t in touches)
    {
        const CGPoint p = [t locationInView:self];
        gTracker.Began(TouchId(t), (float)p.x, (float)p.y);
    }
    RecomputeTouch();
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    if (gInputSuspended) return;
    for (UITouch* t in touches)
    {
        const CGPoint p = [t locationInView:self];
        gTracker.Moved(TouchId(t), (float)p.x, (float)p.y);
    }
    RecomputeTouch();
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    for (UITouch* t in touches)
        gTracker.Ended(TouchId(t));
    RecomputeTouch();
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    for (UITouch* t in touches)
        gTracker.Ended(TouchId(t));
    RecomputeTouch();
}

// Same rectangles the hit test uses, same colours as Android's HUD: gray
// cross arms, red A, blue B; brighter while held.
static void
FillRect(const wf_touch::Rect& r, CGFloat red, CGFloat green, CGFloat blue,
         CGFloat alpha, bool held)
{
    [[UIColor colorWithRed:red green:green blue:blue
                     alpha:(held ? 0.85 : alpha)] setFill];
    UIRectFillUsingBlendMode(CGRectMake(r.x0, r.y0, r.Width(), r.Height()),
                             kCGBlendModeNormal);
}

- (void)drawRect:(CGRect)dirty
{
    if (!gLayout.valid) return;
    const joystickButtonsF held = gTouchButtons;
    const CGFloat g = 0.6, ga = 0.5;
    FillRect(gLayout.Left(),  g, g, g, ga, held & wf_touch::kBtnLeft);
    FillRect(gLayout.Right(), g, g, g, ga, held & wf_touch::kBtnRight);
    FillRect(gLayout.Up(),    g, g, g, ga, held & wf_touch::kBtnUp);
    FillRect(gLayout.Down(),  g, g, g, ga, held & wf_touch::kBtnDown);
    FillRect(gLayout.a, 0.80, 0.25, 0.25, 0.55, held & wf_touch::kBtnA);
    FillRect(gLayout.b, 0.25, 0.35, 0.85, 0.55, held & wf_touch::kBtnB);
}

@end

//=============================================================================

extern "C" void
WFIosSetHudEnabled(int enabled)
{
    gHudEnabled = (enabled != 0);
    gHud.hidden = !gHudEnabled;       // hidden views receive no touches
    if (!gHudEnabled)
        gTracker.ReleaseAll();
    RecomputeTouch();
    NSLog(@"wf_game: touch HUD %s", gHudEnabled ? "enabled" : "disabled");
}

extern "C" void
WFIosInputSuspend(void)
{
    gInputSuspended = true;
    gTracker.ReleaseAll();
    RecomputeTouch();
}

extern "C" void
WFIosInputResume(void)
{
    gInputSuspended = false;
    RecomputeTouch();
}

//=============================================================================
// Simulator CI touch script. Presses each scripted button at its on-screen
// centre through the same tracker + hit test + HAL path a finger uses; only
// UIKit's touch delivery is skipped. Synthetic ids cannot collide with
// UITouch pointers (those are heap addresses, never this small).

namespace
{

constexpr uintptr_t    kScriptIdBase = 0x10;
wf_touch::ScriptEntry  gScript[wf_touch::kMaxScriptEntries];
bool                   gScriptHeld[wf_touch::kMaxScriptEntries] = {};
int                    gScriptCount = 0;

NSString* ScriptText()
{
    // `-WFTouchScript <s>` launch arguments land in NSUserDefaults'
    // argument domain; SIMCTL_CHILD_WF_TOUCH_SCRIPT reaches getenv.
    NSString* s = [[NSUserDefaults standardUserDefaults] stringForKey:@"WFTouchScript"];
    if (s.length) return s;
    const char* env = std::getenv("WF_TOUCH_SCRIPT");
    return (env && *env) ? [NSString stringWithUTF8String:env] : nil;
}

}  // namespace

extern "C" void
WFIosStartTouchScript(void)
{
    NSString* text = ScriptText();
    if (!text) return;
    gScriptCount = wf_touch::ParseScript(text.UTF8String, gScript,
                                         wf_touch::kMaxScriptEntries);
    if (gScriptCount <= 0)
    {
        NSLog(@"wf_game: touch script rejected: \"%@\"", text);
        return;
    }
    float endTime = 0;
    for (int i = 0; i < gScriptCount; ++i)
        endTime = std::max(endTime, gScript[i].start + gScript[i].duration);
    NSLog(@"wf_game: touch script: %d entries, %.1f s", gScriptCount, endTime);

    const CFTimeInterval t0 = CACurrentMediaTime();
    [NSTimer scheduledTimerWithTimeInterval:1.0 / 60.0 repeats:YES block:^(NSTimer* timer) {
        const float t = (float)(CACurrentMediaTime() - t0);
        for (int i = 0; i < gScriptCount; ++i)
        {
            const wf_touch::ScriptEntry& e = gScript[i];
            const bool want = t >= e.start && t < e.start + e.duration;
            if (want == gScriptHeld[i]) continue;
            if (want)
            {
                float x, y;
                // Not laid out yet, or suspended: retry on the next tick.
                if (gInputSuspended || !wf_touch::ButtonCenter(gLayout, e.button, &x, &y))
                    continue;
                gTracker.Began(kScriptIdBase + i, x, y);
            }
            else
            {
                gTracker.Ended(kScriptIdBase + i);
            }
            gScriptHeld[i] = want;
        }
        RecomputeTouch();
        if (t >= endTime)
        {
            NSLog(@"wf_game: touch script done");
            [timer invalidate];
        }
    }];
}
