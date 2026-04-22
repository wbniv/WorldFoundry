//=============================================================================
// hal/ios/metal_view.mm: CAMetalLayer-backed UIView, owner of device + queue
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2C-B: the view no longer drives its own per-frame clear/present via a
// CADisplayLink. Instead, the engine thread owns the frame end-to-end (mirror
// of how Linux works): Display::RenderBegin calls WFIosRenderBegin (defined in
// backend_metal.mm) which acquires a drawable, builds a command buffer +
// encoder, and hands the encoder to the MetalRendererBackend. RenderEnd calls
// WFIosRenderEnd which flushes any batched triangles, ends the encoder, and
// commits/presents.
//
// This file's remaining responsibilities:
//   - Create the CAMetalLayer as the view's backing layer.
//   - Own the MTLDevice + MTLCommandQueue.
//   - Expose the layer + queue to backend_metal.mm via two globals
//     (gWFMetalLayer, gWFMetalQueue) — Obj-C __strong, so they stay alive for
//     the app's lifetime.
//   - Keep drawableSize in sync with the view's pixel bounds via layoutSubviews.
//=============================================================================

#import "metal_view.h"
#import <Metal/Metal.h>
#include <hal/hal.h>

// Defined in hal/ios/input.mm. Android has the same forward-decl in its
// native_app_entry.cc for the same reason — the prototype isn't in hal.h.
extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

// Read from backend_metal.mm (engine thread). __strong by default under ARC.
CAMetalLayer*       gWFMetalLayer = nil;
id<MTLCommandQueue> gWFMetalQueue = nil;

// WF_TARGET_IOS button bitmask constants mirror the Android Phase-3 layout
// (hal/android/native_app_entry.cc:128-181). D-pad in the bottom-left,
// A/B in the bottom-right, all in raw pixel coordinates (origin top-left,
// +Y down). UITouch coords are points; we multiply by contentsScale before
// hit-testing.
static joystickButtonsF WFHitTestTouch(CGFloat px, CGFloat py, int w, int h)
{
    if (w <= 0 || h <= 0) return 0;

    // D-pad region (bottom-left 200x200).
    if (px >= 0.0f   && px < 200.0f &&
        py >= h-200  && py < h)
    {
        if (px < 66.0f   && py >= h-133 && py <  h-66)   return EJ_BUTTONF_LEFT;
        if (px >= 133.0f && py >= h-133 && py <  h-66)   return EJ_BUTTONF_RIGHT;
        if (px >= 66.0f  && px < 133.0f && py <  h-133)  return EJ_BUTTONF_UP;
        if (px >= 66.0f  && px < 133.0f && py >= h-66)   return EJ_BUTTONF_DOWN;
    }
    // A (far bottom-right).
    if (px >= w-120 && px < w   && py >= h-120 && py < h)
        return EJ_BUTTONF_A;
    // B (inside of A).
    if (px >= w-240 && px < w-120 && py >= h-120 && py < h)
        return EJ_BUTTONF_B;
    return 0;
}

// HUD color constants, lifted from gfx/gl/android_window.cc:338-347 so the
// iOS on-screen controls look the same as Android's. Directions are a
// semi-transparent gray, A is red (primary action), B is blue.
static UIColor* WFHudDPadColor(void)   { return [UIColor colorWithWhite:0.55 alpha:0.50]; }
static UIColor* WFHudAColor(void)      { return [UIColor colorWithRed:0.80 green:0.25 blue:0.25 alpha:0.55]; }
static UIColor* WFHudBColor(void)      { return [UIColor colorWithRed:0.25 green:0.35 blue:0.85 alpha:0.55]; }

@implementation WFMetalView
{
    id<MTLDevice>        _device;
    id<MTLCommandQueue>  _queue;
    // HUD child views — non-interactive overlays whose frames track the
    // same pixel-space hit regions as WFHitTestTouch. CAMetalLayer renders
    // the engine scene underneath; these UIViews composite over it.
    UIView*              _hudLeft;
    UIView*              _hudRight;
    UIView*              _hudUp;
    UIView*              _hudDown;
    UIView*              _hudA;
    UIView*              _hudB;
}

+ (Class)layerClass { return [CAMetalLayer class]; }

- (instancetype)initWithFrame:(CGRect)frame
{
    self = [super initWithFrame:frame];
    if (!self) return nil;

    _device = MTLCreateSystemDefaultDevice();
    if (!_device) {
        NSLog(@"wf_game: MTLCreateSystemDefaultDevice returned nil");
        return nil;
    }
    _queue = [_device newCommandQueue];

    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    ml.device             = _device;
    ml.pixelFormat        = MTLPixelFormatBGRA8Unorm;
    ml.framebufferOnly    = YES;
    ml.contentsScale      = [UIScreen mainScreen].scale;

    // Publish to the engine-thread side of the bridge.
    gWFMetalLayer = ml;
    gWFMetalQueue = _queue;

    // HUD buttons — semi-transparent UIViews over the Metal layer. Non-
    // interactive so UITouch events pass through to WFMetalView itself.
    // Layout is done in layoutSubviews using point-space frames derived
    // from the same pixel regions as WFHitTestTouch.
    auto makeHud = ^(UIColor* color, CGFloat cornerRadius) {
        UIView* v = [[UIView alloc] initWithFrame:CGRectZero];
        v.backgroundColor = color;
        v.userInteractionEnabled = NO;
        v.layer.cornerRadius = cornerRadius;
        [self addSubview:v];
        return v;
    };
    _hudLeft  = makeHud(WFHudDPadColor(), 4.0);
    _hudRight = makeHud(WFHudDPadColor(), 4.0);
    _hudUp    = makeHud(WFHudDPadColor(), 4.0);
    _hudDown  = makeHud(WFHudDPadColor(), 4.0);
    _hudA     = makeHud(WFHudAColor(),    22.0);
    _hudB     = makeHud(WFHudBColor(),    22.0);

    NSLog(@"wf_game: MetalView init, device=%@, scale=%g",
          _device.name, ml.contentsScale);
    return self;
}

- (void)layoutSubviews
{
    [super layoutSubviews];
    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    ml.drawableSize = CGSizeMake(self.bounds.size.width  * ml.contentsScale,
                                 self.bounds.size.height * ml.contentsScale);

    // HUD layout: convert the Android-parallel pixel regions back to points
    // for UIView frames (UIView works in points; WFHitTestTouch does the
    // reverse conversion on every UITouch).
    const CGFloat s = ml.contentsScale;
    const CGFloat w = self.bounds.size.width;
    const CGFloat h = self.bounds.size.height;
    const CGFloat px  = 1.0 / s;     // 1 pixel in points
    const CGFloat p66 = 66.0 * px;
    const CGFloat p120= 120.0 * px;
    const CGFloat p133= 133.0 * px;
    const CGFloat p67 = 67.0 * px;   // height of d-pad middle row: h-133..h-66 is 67px
    const CGFloat p200= 200.0 * px;
    const CGFloat p240= 240.0 * px;

    // D-pad cross (bottom-left). Mirror gfx/gl/android_window.cc:340-343.
    _hudLeft.frame  = CGRectMake(0,        h - p133, p66,           p67);
    _hudRight.frame = CGRectMake(p133,     h - p133, p200 - p133,   p67);
    _hudUp.frame    = CGRectMake(p66,      h - p200, p133 - p66,    p200 - p133);
    _hudDown.frame  = CGRectMake(p66,      h - p66,  p133 - p66,    p66);

    // Action buttons (bottom-right). A is the outer one; B is inside.
    _hudA.frame = CGRectMake(w - p120,          h - p120, p120,          p120);
    _hudB.frame = CGRectMake(w - p240,          h - p120, p240 - p120,   p120);
}

//=============================================================================
// Touch input (Phase 3). Each UITouch event recomputes the full bitmask from
// all currently-down touches, then pushes it through _HALSetJoystickButtons.
// This matches hal/android/native_app_entry.cc's RecomputeTouchState pattern.
// The engine thread reads the atomic value in hal/ios/input.mm every frame.
//=============================================================================

- (void)wf_recomputeButtonsFromTouches:(NSSet<UITouch*>*)activeTouches
{
    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    const int w = (int)ml.drawableSize.width;
    const int h = (int)ml.drawableSize.height;
    const CGFloat scale = ml.contentsScale;

    joystickButtonsF bits = 0;
    for (UITouch* t in activeTouches) {
        if (t.phase == UITouchPhaseEnded ||
            t.phase == UITouchPhaseCancelled) continue;
        CGPoint p = [t locationInView:self];
        bits |= WFHitTestTouch(p.x * scale, p.y * scale, w, h);
    }
    _HALSetJoystickButtons(bits);
}

- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    [self wf_recomputeButtonsFromTouches:[event allTouches]];
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    [self wf_recomputeButtonsFromTouches:[event allTouches]];
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    [self wf_recomputeButtonsFromTouches:[event allTouches]];
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event
{
    [self wf_recomputeButtonsFromTouches:[event allTouches]];
}

@end
