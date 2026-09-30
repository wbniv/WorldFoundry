//=============================================================================
// hal/ios/metal_view.h: CAMetalLayer-backed UIView
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================

#ifndef _WF_METAL_VIEW_H
#define _WF_METAL_VIEW_H

#import <UIKit/UIKit.h>
#import <QuartzCore/CAMetalLayer.h>

@interface WFMetalView : UIView
// Pauses the CADisplayLink while the app is inactive / backgrounded, so no
// drawable is acquired or presented then (iOS rejects GPU work from the
// background). Driven by the suspend/resume path in native_app_entry.mm.
- (void)setRenderingPaused:(BOOL)paused;
@end

#endif
