// egl_rebuild: when the Android EGL glue rebuilds its context in place
// (wfsource/source/gfx/gl/egl_recovery.hp, used by gl/android_window.cc).
// Swap result, EGL error and the diagnostic drop flag in, action out; then the
// init path's single retry and the drop flag's take-once rule. Before this, a
// swap that reported EGL_CONTEXT_LOST was ignored and an eglMakeCurrent loss
// only waited for another window. The EGL calls themselves run on a device
// only (finding-your-way docs/plans/2026-11-01-device-context-loss-stress.md).
#include <gfx/gl/egl_recovery.hp>
#include <cstdio>
#include <cstring>

static int failures=0;
#define CHECK(cond) do{ if(!(cond)){ std::printf("FAIL %s:%d: %s\n",__FILE__,__LINE__,#cond); ++failures; } }while(0)

static const int32 EGL_SUCCESS_CODE=0x3000, EGL_BAD_SURFACE_CODE=0x300D, EGL_BAD_NATIVE_WINDOW_CODE=0x300B;

int main(){
    // A good swap does nothing, whatever stale error value is passed with it.
    CHECK(EglRecoveryAfterSwap(true,EGL_SUCCESS_CODE,false)==EGL_RECOVERY_NONE);
    CHECK(EglRecoveryAfterSwap(true,EGL_RECOVERY_CONTEXT_LOST,false)==EGL_RECOVERY_NONE);
    // The driver loss during play: the case that went undetected.
    CHECK(EglRecoveryAfterSwap(false,EGL_RECOVERY_CONTEXT_LOST,false)==EGL_RECOVERY_REBUILD_DRIVER);
    // Other swap failures belong to the window lifecycle, not to a lost context.
    CHECK(EglRecoveryAfterSwap(false,EGL_BAD_SURFACE_CODE,false)==EGL_RECOVERY_NONE);
    CHECK(EglRecoveryAfterSwap(false,EGL_BAD_NATIVE_WINDOW_CODE,false)==EGL_RECOVERY_NONE);
    // A debug drop always rebuilds, and is reported as one even if the swap also lost.
    CHECK(EglRecoveryAfterSwap(true,EGL_SUCCESS_CODE,true)==EGL_RECOVERY_REBUILD_DEBUG_DROP);
    CHECK(EglRecoveryAfterSwap(false,EGL_RECOVERY_CONTEXT_LOST,true)==EGL_RECOVERY_REBUILD_DEBUG_DROP);
    CHECK(EglRecoveryAfterSwap(false,EGL_BAD_SURFACE_CODE,true)==EGL_RECOVERY_REBUILD_DEBUG_DROP);

    // The log reasons the chromecast coordinator classifies: "debug drop" marks a simulated loss.
    CHECK(std::strcmp(EglRecoveryReason(EGL_RECOVERY_REBUILD_DEBUG_DROP),"debug drop")==0);
    CHECK(std::strcmp(EglRecoveryReason(EGL_RECOVERY_REBUILD_DRIVER),"driver")==0);
    CHECK(std::strstr(EglRecoveryReason(EGL_RECOVERY_REBUILD_DRIVER),"debug drop")==nullptr);

    // Init path: a lost context on a new window rebuilds and retries instead of waiting
    // for another APP_CMD_INIT_WINDOW; every other eglMakeCurrent failure gives up as before.
    CHECK(EglRecoveryAfterMakeCurrent(EGL_RECOVERY_CONTEXT_LOST)==EGL_INIT_REBUILD_AND_RETRY);
    CHECK(EglRecoveryAfterMakeCurrent(EGL_BAD_SURFACE_CODE)==EGL_INIT_GIVE_UP);
    CHECK(EglRecoveryAfterMakeCurrent(EGL_BAD_NATIVE_WINDOW_CODE)==EGL_INIT_GIVE_UP);

    // The drop flag: nothing until requested; one request is taken once; several
    // requests before the next frame boundary are one drop.
    EglDropRequest drop;
    CHECK(!drop.Take());
    drop.Request();
    CHECK(drop.Take());
    CHECK(!drop.Take());
    drop.Request();drop.Request();drop.Request();
    CHECK(drop.Take());
    CHECK(!drop.Take());

    // A frame sequence as AndroidSwapBuffers sees it: the request lands between frames,
    // the next boundary rebuilds once, and the frames after it are normal again.
    EglDropRequest flag;
    int rebuilds=0;
    for(int frame=0;frame<6;++frame){
        if(frame==2)flag.Request();
        if(EglRecoveryAfterSwap(true,EGL_SUCCESS_CODE,flag.Take())!=EGL_RECOVERY_NONE)++rebuilds;
    }
    CHECK(rebuilds==1);

    if(failures){std::printf("egl_rebuild: %d failure(s)\n",failures);return 1;}
    std::printf("egl_rebuild: all checks passed\n");
    return 0;
}
