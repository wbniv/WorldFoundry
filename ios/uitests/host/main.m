// Empty host app for the touch UI tests (ios/uitests/project.yml): a UI-test
// bundle needs a target application; the tests drive wf_game by bundle id.
#import <UIKit/UIKit.h>

@interface WFTouchHostDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow* window;
@end

@implementation WFTouchHostDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options
{
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[UIViewController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char* argv[])
{
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([WFTouchHostDelegate class]));
    }
}
