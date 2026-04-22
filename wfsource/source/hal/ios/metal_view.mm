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

// Read from backend_metal.mm (engine thread). __strong by default under ARC.
CAMetalLayer*       gWFMetalLayer = nil;
id<MTLCommandQueue> gWFMetalQueue = nil;

@implementation WFMetalView
{
    id<MTLDevice>        _device;
    id<MTLCommandQueue>  _queue;
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
}

@end
