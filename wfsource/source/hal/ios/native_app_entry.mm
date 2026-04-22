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
#include <hal/hal.h>

#include <pthread.h>

// Defined in hal/ios/platform.mm. C++ linkage (matches the Linux/Android HAL;
// extern "C" here would mismatch the definition's mangling and fail at link).
void _PlatformSpecificInit(int argc, char** argv,
                           int maxTasks, int maxMessages, int maxPorts);
extern "C" void WFIosSetSurfaceSize(int w, int h);

// Defined in hal/ios/lifecycle.mm.
extern "C" void HALNotifySuspend(void);
extern "C" void HALNotifyResume(void);

//=============================================================================
// Engine thread. Phase 2C-A pattern: UIApplicationMain + CADisplayLink
// stay on the main thread; HALStart → PIGSMain → WFGame's blocking game
// loop runs on a dedicated background thread that we spawn from
// viewDidLoad. HALStart itself calls _PlatformSpecificInit, so we don't
// pre-init from the main thread; the AssetAccessor becomes valid on the
// engine thread just before PIGSMain.
//=============================================================================

static pthread_t sEngineThread;
static bool      sEngineThreadStarted = false;

static void* WFEngineThreadMain(void* /*arg*/)
{
    NSLog(@"wf_game: engine thread enter");
    static int   argc    = 1;
    static char  arg0[]  = "wf_game";
    static char* argv[2] = { arg0, nullptr };
    HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    NSLog(@"wf_game: engine thread exit (HALStart returned)");
    return nullptr;
}

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

    // Phase 2C-A: spawn the engine thread. HALStart → _PlatformSpecificInit
    // → PIGSMain → WFGame → RunGameScript happen on this thread; the main
    // thread remains owned by UIApplication + the CADisplayLink in
    // WFMetalView. Thread sync for the Metal encoder handoff lands in
    // Phase 2C-B — for now, Display::PageFlip sleeps ~16ms and the Metal
    // backend drops any batched triangles because no encoder is set.
    if (!sEngineThreadStarted) {
        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setstacksize(&attr, 8 * 1024 * 1024);  // WF eats stack
        int rc = pthread_create(&sEngineThread, &attr,
                                WFEngineThreadMain, nullptr);
        pthread_attr_destroy(&attr);
        if (rc == 0) {
            sEngineThreadStarted = true;
            NSLog(@"wf_game: engine thread spawned");
        } else {
            NSLog(@"wf_game: engine thread spawn failed (errno=%d)", rc);
        }
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
