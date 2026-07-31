//=============================================================================
// hal/ios/metal_view.mm: CAMetalLayer-backed UIView + CADisplayLink driver
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 2A: minimal Metal bring-up. Creates a CAMetalLayer-hosting UIView,
// owns a MTLDevice + MTLCommandQueue, and clears to a solid color every frame
// via a CADisplayLink. No rendering yet — proves Metal links on iOS Simulator,
// CAMetalLayer renders drawables, and the display-link callback fires.
//
// Phase 2B replaces the clear with the real RendererBackend path (MSL shader
// + vertex buffer + snowgoons triangles).
//=============================================================================

#import "metal_view.h"
#import <Metal/Metal.h>

@implementation WFMetalView
{
    id<MTLDevice>        _device;
    id<MTLCommandQueue>  _queue;
    CADisplayLink*       _displayLink;
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

    // Phase 2A debug color: a distinctive cornflower blue. If the screenshot
    // shows this, Metal is running; Phase 2B will replace with real rendering.
    self.backgroundColor  = [UIColor colorWithRed:0.39 green:0.58 blue:0.93 alpha:1.0];

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
    } else if (!self.window && _displayLink) {
        [_displayLink invalidate];
        _displayLink = nil;
    }
}

- (void)tick:(CADisplayLink*)link
{
    CAMetalLayer* ml = (CAMetalLayer*)self.layer;
    ml.drawableSize = CGSizeMake(self.bounds.size.width  * ml.contentsScale,
                                 self.bounds.size.height * ml.contentsScale);

    id<CAMetalDrawable> drawable = [ml nextDrawable];
    if (!drawable) return;

    MTLRenderPassDescriptor* rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture     = drawable.texture;
    rp.colorAttachments[0].loadAction  = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    rp.colorAttachments[0].clearColor  = MTLClearColorMake(0.39, 0.58, 0.93, 1.0);

    id<MTLCommandBuffer> cb = [_queue commandBuffer];
    id<MTLRenderCommandEncoder> enc =
        [cb renderCommandEncoderWithDescriptor:rp];
    [enc endEncoding];

    [cb presentDrawable:drawable];
    [cb commit];
}

@end
