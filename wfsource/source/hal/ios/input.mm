//=============================================================================
// hal/ios/input.mm: iOS input — Android's touch controls → joystick bitmask
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// The touch controls are Android's: a joystick bottom-left and A, B, C, D
// bottom-right, and while a story card is open only A and C. Layout, hit
// testing and finger ownership are hal/touch_controls.h, the code Android
// runs; hal/ios/touch_pad.cc adapts UIKit's touches to it. Both are
// platform-free and unit-tested on Linux (tests/test_ios_touch_pad.py). This
// file is only the UIKit glue. Plan: finding-your-way
// docs/plans/2026-11-08-ios-touch-parity.md.
//
//   UITouch (main thread) → WFTouchHudView → wf_touch::Pad
//     → wftouch::State::update (shared) → _HALSetJoystickButtons
//     → _JoystickButtonsF (engine thread)
//   bitmaptext::ReaderOpen() (engine thread, Display::RenderEnd)
//     → WFIosTouchFrame → main queue → Pad::SetReading
//
// Differences from Android, and why:
//   - The HUD is a UIKit overlay view drawn with UIKit, not GL quads drawn
//     before the swap: Android's WFAndroidDrawHUD (gfx/gl/android_window.cc)
//     is raw GL, and an overlay keeps the HUD independent of renderer state.
//     Colours, alphas and proportions are copied from it; the labels use the
//     system semibold font (Android's UI font atlas is engine-rendered).
//   - Sizes are points, inside the safe area on every side.
//   - The button state is atomic: on iOS the engine runs on its own thread
//     (native_app_entry.mm) while UIKit delivers touches on the main thread.
//   - The card flag is read on the engine thread and handed to the main
//     thread, and a finger on a control a card hides lets go at once.
//   - Each visible control is an accessibility element (wf.touch.stick,
//     wf.touch.A ... wf.touch.D), so a UI test can tap it through UIKit.
//     -WFTouchDiagnostics 1 adds wf.touch.state, whose value is
//     "held=0x.... seen=0x.... reading=0|1" (seen: every bit since launch).
//=============================================================================

#import <UIKit/UIKit.h>
#import <QuartzCore/QuartzCore.h>

#include <hal/hal.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdlib>

#include "touch_pad.hp"
#import "touch_hud.h"

static_assert(wf_touch::kBtnA     == EJ_BUTTONF_A,     "touch_controls.h A drifted");
static_assert(wf_touch::kBtnB     == EJ_BUTTONF_B,     "touch_controls.h B drifted");
static_assert(wf_touch::kBtnC     == EJ_BUTTONF_C,     "touch_controls.h C drifted");
static_assert(wf_touch::kBtnD     == EJ_BUTTONF_D,     "touch_controls.h D drifted");
static_assert(wf_touch::kBtnUp    == EJ_BUTTONF_UP,    "touch_controls.h Up drifted");
static_assert(wf_touch::kBtnDown  == EJ_BUTTONF_DOWN,  "touch_controls.h Down drifted");
static_assert(wf_touch::kBtnLeft  == EJ_BUTTONF_LEFT,  "touch_controls.h Left drifted");
static_assert(wf_touch::kBtnRight == EJ_BUTTONF_RIGHT, "touch_controls.h Right drifted");

// game/bitmap_presenter.hp; declared here so this Objective-C++ file does not
// pull in the renderer headers that one includes.
namespace bitmaptext { bool ReaderOpen(); }

// The iOS target builds without ARC (see dealloc below); the per-query
// accessibility elements must not leak either way.
#if __has_feature(objc_arc)
#define WF_AUTORELEASE(x) (x)
#else
#define WF_AUTORELEASE(x) [(x) autorelease]
#endif

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
joystickButtonsF      gSeenButtons    = 0;   // diagnostics: every bit since launch

wf_touch::Pad          gPad;
wftouch::Stick         gDrawnStick;
bool                   gInputSuspended = false;
bool                   gHudEnabled     = true;
bool                   gDiagnostics    = false;
WFTouchHudView*        gHud            = nil;   // owned by the view hierarchy

void Emit()
{
    _HALSetJoystickButtons(gGamepadButtons | gTouchButtons);
}

// Read the touch bits from the pad; log and redraw on a change (the log line
// is what the Simulator CI run greps for), and redraw when the knob moves.
void RecomputeTouch()
{
    const joystickButtonsF now =
        (gInputSuspended || !gHudEnabled) ? 0 : gPad.Buttons();
    if (now != gTouchButtons)
    {
        NSLog(@"wf_game: touch buttons 0x%04x", (unsigned)now);
        gTouchButtons = now;
        gSeenButtons |= now;
        [gHud setNeedsDisplay];
    }
    const wftouch::Stick s = gPad.StickPosition();
    if (s.x != gDrawnStick.x || s.y != gDrawnStick.y)
    {
        gDrawnStick = s;
        [gHud setNeedsDisplay];
    }
    Emit();
}

inline uintptr_t TouchId(UITouch* t)
{
    // UIKit reuses the same UITouch object for a finger's whole sequence.
    return (uintptr_t)(__bridge void*)t;
}

void ApplyReading(bool reading)
{
    if (reading == gPad.Reading()) return;
    gPad.SetReading(reading);
    NSLog(@"wf_game: touch reading %s", reading ? "on" : "off");
    [gHud setNeedsDisplay];
    UIAccessibilityPostNotification(UIAccessibilityLayoutChangedNotification, nil);
    RecomputeTouch();
}

UIAccessibilityElement* ControlElement(id container, const wftouch::Rect& r,
                                       NSString* ident, NSString* label)
{
    UIAccessibilityElement* e = WF_AUTORELEASE([[UIAccessibilityElement alloc] initWithAccessibilityContainer:container]);
    e.accessibilityFrameInContainerSpace = CGRectMake(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
    e.accessibilityIdentifier = ident;
    e.accessibilityLabel      = label;
    e.accessibilityTraits     = UIAccessibilityTraitButton;
    return e;
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
    self.isAccessibilityElement = NO;   // a container of one element per control
    gDiagnostics = [[NSUserDefaults standardUserDefaults] boolForKey:@"WFTouchDiagnostics"];
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
    wftouch::Insets insets;
    insets.top    = (float)in.top;
    insets.left   = (float)in.left;
    insets.bottom = (float)in.bottom;
    insets.right  = (float)in.right;
    gPad.SetView((float)sz.width, (float)sz.height, insets);
    // Format parsed by scripts/ios_sim_chapter.py (TOUCH_LAYOUT).
    NSLog(@"wf_game: touch layout %gx%g pt, safe {%g,%g,%g,%g}, cell %.1f pt",
          sz.width, sz.height, in.top, in.left, in.bottom, in.right, gPad.CurrentLayout().cell);
    [self setNeedsDisplay];
    UIAccessibilityPostNotification(UIAccessibilityLayoutChangedNotification, nil);
    RecomputeTouch();   // held fingers are re-hit against the new layout
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
        gPad.Began(TouchId(t), (float)p.x, (float)p.y);
    }
    RecomputeTouch();
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    if (gInputSuspended) return;
    for (UITouch* t in touches)
    {
        const CGPoint p = [t locationInView:self];
        gPad.Moved(TouchId(t), (float)p.x, (float)p.y);
    }
    RecomputeTouch();
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    for (UITouch* t in touches)
        gPad.Ended(TouchId(t));
    RecomputeTouch();
}

// UIKit cancels only the touches it names; each lets go like a lift.
- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    for (UITouch* t in touches)
        gPad.Ended(TouchId(t));
    RecomputeTouch();
}

//-----------------------------------------------------------------------------
// Drawing: Android's HUD (WFAndroidDrawHUD, gfx/gl/android_window.cc), same
// colours and alphas. Keep the two in step.

static void
FillDisc(CGFloat cx, CGFloat cy, CGFloat r, CGFloat red, CGFloat green, CGFloat blue, CGFloat alpha)
{
    [[UIColor colorWithRed:red green:green blue:blue alpha:alpha] setFill];
    [[UIBezierPath bezierPathWithOvalInRect:CGRectMake(cx - r, cy - r, 2 * r, 2 * r)] fill];
}

- (void)drawRect:(CGRect)dirty
{
    const wftouch::Layout& l = gPad.CurrentLayout();
    if (!l.valid || !gHudEnabled) return;
    const joystickButtonsF held = gTouchButtons;
    const bool reading = !l.stick;
    if (l.stick)
    {
        const CGFloat radius = wftouch::stickRadius(l);
        const CGFloat cx = 0.5f * (l.pad.x0 + l.pad.x1), cy = 0.5f * (l.pad.y0 + l.pad.y1);
        FillDisc(cx, cy, radius, .42, .50, .62, .65);
        FillDisc(cx, cy, radius - l.cell * .03f, .05, .075, .125, .55);
        const bool moving = (held & wf_touch::kStickBits) != 0;
        const CGFloat knob = l.cell * .6f, travel = radius - knob;
        const wftouch::Stick s = gPad.StickPosition();
        FillDisc(cx + s.x * travel, cy + s.y * travel, knob,
                 moving ? .42 : .22, moving ? .62 : .32, moving ? .85 : .46, .85);
    }
    for (int i = 4; i < 8; ++i)
    {
        const wftouch::Control& c = l.controls[i];
        if (!wftouch::shown(l, c)) continue;
        const wftouch::Rect& r = c.rect;
        const CGRect rect = CGRectMake(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
        const CGFloat alpha = (held & c.bit) ? 0.85 : reading ? 0.30 : 0.55;
        [[UIColor colorWithRed:0.20 green:0.28 blue:0.43 alpha:alpha] setFill];
        UIRectFillUsingBlendMode(rect, kCGBlendModeNormal);
        // Capitals 7/16 of the button's width tall, as on Android.
        UIFont* font = [UIFont systemFontOfSize:rect.size.width * 7.0 / 16.0 / 0.7
                                         weight:UIFontWeightSemibold];
        NSDictionary* attrs = @{
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: [UIColor colorWithWhite:1.0 alpha:(reading ? 0.60 : 0.95)],
        };
        NSString* label = [NSString stringWithUTF8String:c.label];
        const CGSize ts = [label sizeWithAttributes:attrs];
        // Centre by hand: CGRectGetMidX/Y live in CoreGraphics, which wf_game does not link.
        [label drawAtPoint:CGPointMake(rect.origin.x + (rect.size.width - ts.width) / 2,
                                       rect.origin.y + (rect.size.height - ts.height) / 2)
            withAttributes:attrs];
    }
}

//-----------------------------------------------------------------------------
// Accessibility: one element per visible control (hidden ones have none).

- (NSArray*)accessibilityElements
{
    NSMutableArray* out = [NSMutableArray array];
    const wftouch::Layout& l = gPad.CurrentLayout();
    if (!l.valid || !gHudEnabled) return out;
    if (l.stick)
    {
        const CGFloat radius = wftouch::stickRadius(l);
        const CGFloat cx = 0.5f * (l.pad.x0 + l.pad.x1), cy = 0.5f * (l.pad.y0 + l.pad.y1);
        wftouch::Rect disc{ float(cx - radius), float(cy - radius), float(cx + radius), float(cy + radius) };
        [out addObject:ControlElement(self, disc, @"wf.touch.stick", @"Joystick")];
    }
    for (int i = 4; i < 8; ++i)
    {
        const wftouch::Control& c = l.controls[i];
        if (!wftouch::shown(l, c)) continue;
        NSString* name = [NSString stringWithUTF8String:c.label];
        [out addObject:ControlElement(self, c.rect, [@"wf.touch." stringByAppendingString:name],
                                      [name stringByAppendingString:@" button"])];
    }
    if (gDiagnostics)
    {
        UIAccessibilityElement* e = WF_AUTORELEASE([[UIAccessibilityElement alloc] initWithAccessibilityContainer:self]);
        e.accessibilityFrameInContainerSpace = CGRectMake(0, 0, 4, 4);
        e.accessibilityIdentifier = @"wf.touch.state";
        e.accessibilityLabel      = @"Touch state";
        e.accessibilityValue      = [NSString stringWithFormat:@"held=0x%04x seen=0x%04x reading=%d",
                                     (unsigned)gTouchButtons, (unsigned)gSeenButtons, gPad.Reading() ? 1 : 0];
        e.accessibilityTraits     = UIAccessibilityTraitStaticText;
        [out addObject:e];
    }
    return out;
}

@end

//=============================================================================

extern "C" void
WFIosSetHudEnabled(int enabled)
{
    gHudEnabled = (enabled != 0);
    gHud.hidden = !gHudEnabled;       // hidden views receive no touches
    if (!gHudEnabled)
        gPad.ReleaseAll();
    RecomputeTouch();
    NSLog(@"wf_game: touch HUD %s", gHudEnabled ? "enabled" : "disabled");
}

extern "C" void
WFIosInputSuspend(void)
{
    gInputSuspended = true;
    gPad.ReleaseAll();
    RecomputeTouch();
}

extern "C" void
WFIosInputResume(void)
{
    gInputSuspended = false;
    RecomputeTouch();
}

// Engine thread, once per frame after it is drawn (Display::RenderEnd in
// hal/ios/display_ios.cc). The card flag is written while the frame is drawn
// on this thread; the main thread only ever sees it through the queue.
extern "C" void
WFIosTouchFrame(void)
{
    static std::atomic<int> last{0};
    const int open = bitmaptext::ReaderOpen() ? 1 : 0;
    if (last.exchange(open) == open) return;
    dispatch_async(dispatch_get_main_queue(), ^{ ApplyReading(open != 0); });
}

//=============================================================================
// Simulator CI touch script. Presses each scripted button at its on-screen
// point through the same pad, shared logic and HAL path a finger uses; only
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
                if (gInputSuspended || !wf_touch::ButtonCenter(gPad.CurrentLayout(), e.button, &x, &y))
                    continue;
                gPad.Began(kScriptIdBase + i, x, y);
            }
            else
            {
                gPad.Ended(kScriptIdBase + i);
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
