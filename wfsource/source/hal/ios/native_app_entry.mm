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
//
// Phase 3: a WFTouchHudView (hal/ios/input.mm) sits over the Metal view and
// turns touches into the joystick bitmask. Lifecycle — mirrors Android's
// APP_CMD_PAUSE / RESUME (hal/android/native_app_entry.cc):
//   applicationWillResignActive, viewWillDisappear → WFSuspend
//   applicationDidBecomeActive,  viewDidAppear     → WFResume
// WFSuspend flips HALIsSuspended (game.cc skips render + PageFlip), releases
// every held touch bit so no button stays stuck, and pauses the display
// link. Both are idempotent, since UIKit may send more than one of these.
//=============================================================================

#import <UIKit/UIKit.h>
#import "metal_view.h"
#import "touch_hud.h"
#include <hal/args_file.hp>
#include <hal/asset_accessor.hp>
#include <hal/hal.h>
#include <pigsys/pigsys.hp>

#include <pthread.h>
#include <string>
#include <vector>

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

// The engine's command line: argv[0], then the bundle's wf_args.txt (the
// format Android reads from assets/, hal/args_file.hp), then any launch
// arguments. A home-screen launch has no launch arguments, so the bundled
// file is the only way an app such as the Finding Your Way chapter gets its
// VRAM slot sizes; a simulator `simctl launch <udid> <id> --flag` still adds
// to (and, for last-one-wins switches, overrides) them. Static: HALStart and
// the pigsys globals keep pointing at these strings for the process lifetime.
static std::vector<std::string> sArgStore;
static std::vector<char*>       sArgv;

static void WFBuildEngineArguments()
{
    @autoreleasepool {
        std::string fileText;
        NSString* path = [[NSBundle mainBundle] pathForResource:@"wf_args" ofType:@"txt"];
        if (path) {
            NSData* data = [NSData dataWithContentsOfFile:path];
            if (data)
                fileText.assign((const char*)data.bytes, (size_t)data.length);
        }
        std::vector<std::string> launchArgs;
        NSArray<NSString*>* processArgs = [[NSProcessInfo processInfo] arguments];
        for (NSUInteger i = 1; i < processArgs.count; ++i)   // [0] is the executable
            launchArgs.push_back(std::string([processArgs[i] UTF8String]));

        std::vector<std::string> settings;   // qr_logo=: no phone overlay on iOS
        sArgStore = wfargs::ComposeArgs("wf_game", fileText, launchArgs, &settings);
        sArgv.clear();
        for (std::string& arg : sArgStore)
            sArgv.push_back(&arg[0]);
        sArgv.push_back(nullptr);

        const size_t fileArgs = sArgStore.size() - 1 - launchArgs.size();
        NSLog(@"wf_game: wf_args.txt %s, gave %zu argument(s); %zu launch argument(s)",
              path ? "found" : "absent", fileArgs, launchArgs.size());
        for (size_t i = 1; i < sArgStore.size(); ++i)
            NSLog(@"wf_game: arg[%zu] %s", i, sArgStore[i].c_str());
    }
}

static void* WFEngineThreadMain(void* /*arg*/)
{
    NSLog(@"wf_game: engine thread enter");
    WFBuildEngineArguments();
    // HALStart hands PIGSMain the pigsys globals, not its own argc/argv (see
    // hal/android/native_app_entry.cc); set them, or every argument is dropped.
    __argc = (int)sArgv.size() - 1;
    __argv = sArgv.data();
    HALStart(__argc, __argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    NSLog(@"wf_game: engine thread exit (HALStart returned)");
    return nullptr;
}

//=============================================================================
// Suspend / resume. Main thread.

// Android suppresses the HUD (and touch) in TV mode; iOS has no TV mode, so
// the conditional is wired but always false. Phase 5 turns it on while a
// GCController (MFi gamepad) is connected.
static bool sHudSuppressed = false;

static void WFSetRenderingPaused(UIView* root, BOOL paused)
{
    if ([root isKindOfClass:[WFMetalView class]])
        [(WFMetalView*)root setRenderingPaused:paused];
}

static void WFSuspend(UIView* root, const char* why)
{
    NSLog(@"wf_game: suspend (%s)", why);
    HALNotifySuspend();
    WFIosInputSuspend();
    WFSetRenderingPaused(root, YES);
}

static void WFResume(UIView* root, const char* why)
{
    NSLog(@"wf_game: resume (%s)", why);
    WFSetRenderingPaused(root, NO);
    WFIosInputResume();
    HALNotifyResume();
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

    // Phase 3: touch controls over the Metal view (autoresizes with it).
    WFTouchHudView* hud = [[WFTouchHudView alloc] initWithFrame:self.view.bounds];
    [self.view addSubview:hud];
    WFIosSetHudEnabled(sHudSuppressed ? 0 : 1);
    WFIosStartTouchScript();   // Simulator CI only; no-op without a script
}

- (void)viewDidAppear:(BOOL)animated
{
    [super viewDidAppear:animated];
    WFResume(self.view, "viewDidAppear");
}

- (void)viewWillDisappear:(BOOL)animated
{
    [super viewWillDisappear:animated];
    WFSuspend(self.view, "viewWillDisappear");
}

// A game: keep the home indicator out of the way and make a swipe from the
// bottom / side edges reach the D-pad and A/B first (a second swipe still
// goes to the system).
- (BOOL)prefersHomeIndicatorAutoHidden
{
    return YES;
}

- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures
{
    return UIRectEdgeBottom | UIRectEdgeLeft | UIRectEdgeRight;
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
    WFSuspend(self.window.rootViewController.view, "applicationWillResignActive");
}

- (void)applicationDidBecomeActive:(UIApplication*)application
{
    WFResume(self.window.rootViewController.view, "applicationDidBecomeActive");
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
