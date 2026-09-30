//=============================================================================
// hal/ios/metal_view.mm: CAMetalLayer-backed UIView + CADisplayLink driver
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2C-B: the view no longer draws. The engine thread renders each frame
// into this layer's drawable and presents it (gfx/metal/backend_metal.mm,
// wf_metal::BeginFrameToLayer / EndFrameToLayer, called from
// hal/ios/display_ios.cc). The main-thread CADisplayLink only paces the engine:
// each tick releases at most one pending Display::PageFlip wait.
// Rejected: rendering from the display-link callback on the main thread. The
// engine's game loop is a blocking loop on its own thread; inverting it into a
// per-tick callback would restructure WFGame, not the iOS HAL.
//=============================================================================

#import "metal_view.h"
#import <Metal/Metal.h>
#include <atomic>
#include <dispatch/dispatch.h>

static CAMetalLayer*        sLayer      = nil;
static dispatch_semaphore_t sVsync      = nullptr;
static std::atomic<int>     sVsyncArmed{0};

extern "C" void* WFIosMetalLayer(void) { return (__bridge void*)sLayer; }

// Engine thread: block until the next display-link tick (or timeout_ms, so a
// paused link while backgrounded cannot wedge the game loop). Returns true
// when a tick arrived.
extern "C" bool WFIosWaitForVSync(int timeout_ms)
{
    if (!sVsync) return false;
    const long rc = dispatch_semaphore_wait(
        sVsync, dispatch_time(DISPATCH_TIME_NOW, (int64_t)timeout_ms * 1000000LL));
    sVsyncArmed.store(0);
    return rc == 0;
}

@implementation WFMetalView
{
    id<MTLDevice>        _device;
    CADisplayLink*       _displayLink;
    BOOL                 _renderingPaused;
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

    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    ml.device             = _device;
    ml.pixelFormat        = MTLPixelFormatBGRA8Unorm;
    ml.framebufferOnly    = YES;
    ml.contentsScale      = [UIScreen mainScreen].scale;

    // Black, not a debug colour: until the engine presents its first frame
    // the screen must not look like "something rendered".
    self.backgroundColor  = [UIColor blackColor];
    ml.opaque             = YES;

    sLayer = ml;
    if (!sVsync) sVsync = dispatch_semaphore_create(0);

    NSLog(@"wf_game: MetalView init, device=%@, scale=%g",
          _device.name, ml.contentsScale);
    return self;
}

- (void)didMoveToWindow
{
    [super didMoveToWindow];
    if (self.window && !_displayLink) {
        _displayLink = [CADisplayLink displayLinkWithTarget:self
                                                   selector:@selector(tick:)];
        [_displayLink addToRunLoop:[NSRunLoop mainRunLoop]
                           forMode:NSRunLoopCommonModes];
        _displayLink.paused = _renderingPaused;
    } else if (!self.window && _displayLink) {
        [_displayLink invalidate];
        _displayLink = nil;
    }
}

- (void)setRenderingPaused:(BOOL)paused
{
    _renderingPaused    = paused;
    _displayLink.paused = paused;   // nil-safe before didMoveToWindow
}

- (void)layoutSubviews
{
    [super layoutSubviews];
    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    ml.drawableSize = CGSizeMake(self.bounds.size.width  * ml.contentsScale,
                                 self.bounds.size.height * ml.contentsScale);
}

- (void)tick:(CADisplayLink*)link
{
    // Signal at most once per engine wait so a slow engine never banks a
    // burst of ticks and then runs several frames unpaced.
    if (sVsyncArmed.exchange(1) == 0)
        dispatch_semaphore_signal(sVsync);
}

@end
