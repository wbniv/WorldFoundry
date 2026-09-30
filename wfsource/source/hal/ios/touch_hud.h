//=============================================================================
// hal/ios/touch_hud.h: on-screen touch controls (UIKit overlay) + input hooks
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Implemented in hal/ios/input.mm. native_app_entry.mm adds a WFTouchHudView
// over the WFMetalView and drives the suspend/resume hooks below. All of
// these are main-thread only.
//=============================================================================

#ifndef _WF_TOUCH_HUD_H
#define _WF_TOUCH_HUD_H

#import <UIKit/UIKit.h>

// Transparent full-screen view: draws the D-pad + A/B (same layout and
// colours as Android's HUD, gfx/gl/android_window.cc) and receives the
// touches that drive them. Hidden when the HUD is disabled, which also
// stops its touches, as Android suppresses touch in TV mode.
@interface WFTouchHudView : UIView
@end

#ifdef __cplusplus
extern "C" {
#endif

// iOS twin of WFAndroidSetHudEnabled. Default ON.
void WFIosSetHudEnabled(int enabled);

// Suspend releases every held touch bit, so no button can stay stuck
// across a background/foreground trip, and ignores new touches until
// resume.
void WFIosInputSuspend(void);
void WFIosInputResume(void);

// Simulator CI hook: plays the synthetic touch script in the launch
// argument `-WFTouchScript <script>` or the environment variable
// WF_TOUCH_SCRIPT (grammar in touch_pad.hp). No-op when neither is set.
void WFIosStartTouchScript(void);

#ifdef __cplusplus
}
#endif

#endif
