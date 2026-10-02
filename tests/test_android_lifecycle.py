"""Exercise the real Android lifecycle HAL with simulated native events."""
import pathlib
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_android_close_and_resume(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("no C++ compiler")
    harness = tmp_path / "lifecycle.cc"
    harness.write_text(r'''
#include <hal/lifecycle.h>
#include <cassert>
bool close_requested = false, window_ready = true;
int pumps = 0;
extern "C" int WFAndroidHasWindow() { return window_ready; }
extern "C" int WFAndroidCloseRequested() { return close_requested; }
extern "C" void WFAndroidRequestClose() { close_requested = true; }
extern "C" void WFAndroidPumpEvents() { ++pumps; }
int main() {
    assert(!HALWindowCloseRequested());
    assert(!HALIsSuspended());
    HALNotifySuspend();
    window_ready = false;
    HALNotifyResume();
    assert(HALIsSuspended()); // Resume arrives before the surface.
    HALPumpSuspendedEvents();
    assert(pumps == 1);
    window_ready = true;
    assert(!HALIsSuspended());
    close_requested = true; // APP_CMD_DESTROY, including while suspended.
    HALNotifySuspend();
    assert(HALWindowCloseRequested());
    close_requested = false;
    HALRequestClose();
    assert(HALWindowCloseRequested());
}
''')
    binary = tmp_path / "lifecycle"
    subprocess.run([compiler, "-std=c++17", "-I", str(ROOT / "wfsource/source"),
                    str(harness), str(ROOT / "wfsource/source/hal/android/lifecycle.cc"),
                    "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_launcher_reuses_the_single_native_engine():
    manifest = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml")
    ns = "{http://schemas.android.com/apk/res/android}"
    native = next(a for a in manifest.findall("application/activity")
                  if a.get(ns + "name") == "android.app.NativeActivity")
    assert native.get(ns + "launchMode") == "singleTask"
