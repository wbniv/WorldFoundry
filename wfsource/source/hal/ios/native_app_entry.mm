//=============================================================================
// hal/ios/native_app_entry.mm: UIApplicationMain + AppDelegate + root VC
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 1 goal: .app launches to a black UIViewController without crashing.
// _PlatformSpecificInit is called on viewDidLoad so HALGetAssetAccessor() is
// safe to call. The actual render/game loop (CADisplayLink-driven PIGSMain
// invocation, CAMetalLayer surface, lifecycle hook wiring) lands in Phase 2.
//=============================================================================

#import <UIKit/UIKit.h>
#import "metal_view.h"
#include <hal/asset_accessor.hp>

// Defined in hal/ios/platform.mm. C++ linkage (matches the Linux/Android HAL;
// extern "C" here would mismatch the definition's mangling and fail at link).
void _PlatformSpecificInit(int argc, char** argv,
                           int maxTasks, int maxMessages, int maxPorts);
extern "C" void WFIosSetSurfaceSize(int w, int h);

// Defined in hal/ios/lifecycle.mm.
extern "C" void HALNotifySuspend(void);
extern "C" void HALNotifyResume(void);

//=============================================================================

@interface WFRootViewController : UIViewController
@end

@implementation WFRootViewController

- (void)loadView
{
    // Phase 2A: root view is a CAMetalLayer-backed WFMetalView (see
    // hal/ios/metal_view.mm). CADisplayLink drives clear-to-color each frame;
    // Phase 2B will replace the clear with the real RendererBackend path.
    self.view = [[WFMetalView alloc] initWithFrame:[UIScreen mainScreen].bounds];
}

- (void)viewDidLoad
{
    [super viewDidLoad];

    // Phase 1 HAL bring-up. Args are dummies; HAL_MAX_* match hal/linux's call.
    static int  argc = 1;
    static char arg0[] = "wf_game";
    static char* argv[] = { arg0, nullptr };
    _PlatformSpecificInit(argc, argv, 32, 256, 32);

    // Sanity check: can we open cd.iff via NSBundle?
    AssetHandle* h = HALGetAssetAccessor().OpenForRead("cd.iff");
    if (h) {
        int64_t sz = HALGetAssetAccessor().Size(h);
        NSLog(@"wf_game: cd.iff opened, size=%lld", sz);
        HALGetAssetAccessor().Close(h);
    } else {
        NSLog(@"wf_game: cd.iff NOT found in bundle (Phase 1 expected, assets land in Phase 1C)");
    }
}

- (void)viewWillLayoutSubviews
{
    [super viewWillLayoutSubviews];
    CGSize sz = self.view.bounds.size;
    CGFloat scale = self.view.contentScaleFactor;
    WFIosSetSurfaceSize((int)(sz.width * scale), (int)(sz.height * scale));
}

@end

//=============================================================================

@interface WFAppDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow* window;
@end

@implementation WFAppDelegate

- (BOOL)application:(UIApplication*)application
    didFinishLaunchingWithOptions:(NSDictionary*)launchOptions
{
    self.window = [[UIWindow alloc] initWithFrame:[[UIScreen mainScreen] bounds]];
    self.window.rootViewController = [[WFRootViewController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}

- (void)applicationWillResignActive:(UIApplication*)application
{
    HALNotifySuspend();
}

- (void)applicationDidBecomeActive:(UIApplication*)application
{
    HALNotifyResume();
}

@end

//=============================================================================

int
main(int argc, char* argv[])
{
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([WFAppDelegate class]));
    }
}
