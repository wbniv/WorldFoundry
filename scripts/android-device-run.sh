#!/usr/bin/env bash
# android-device-run.sh — install one World Foundry Android app on a device
# (Chromecast with Google TV over network ADB, or a phone), launch it, let it
# run, and collect a screenshot, the logs and the frame pacing into ~/tmp/.
#
# See docs/plans/2026-09-30-aquarium-chromecast.md (Verification, device steps).
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/android-device-run.sh [options] [TARGET]

Install a World Foundry app on an Android device, launch it, wait, and collect
evidence into ~/tmp/android-device-run/<app>-<UTC time>/:
  screen.png        adb exec-out screencap -p, after the wait
  logcat-wf.txt     wf_game + crash lines (AndroidRuntime, DEBUG, libc, ActivityManager)
  logcat-full.txt   the whole logcat since the launch
  wf.log            the engine's stdout/stderr (the app's external files dir), if readable
  frames.txt        SurfaceFlinger present times of the app's layer → frame interval / fps
  summary.txt       the PASS / FAIL / INFO lines printed at the end
It is idempotent: re-running reconnects, reinstalls (-r) and relaunches.

TARGET  Chromecast / phone IP for network debugging (port 5555 is added when
        missing), host:port, or a USB serial. Omitted: the one device adb
        already lists.

Options:
  --app NAME     aquarium (default) or snowgoons
  --release      install the release APK (-O3 + LTO, debug-keystore signed)
                 instead of the debug APK (-O0); the release APK is the one to
                 judge frame rate with
  --build        build the APK first (gradlew assemble<App><Type>)
  --apk PATH     install this APK instead of the Gradle output
  --seconds N    how long the app runs before the screenshot (default 20)
  --poke         after the first screenshot, send D-pad RIGHT (held 1.5 s),
                 then UP, and take screen-after-keys.png (information only)
  -h, --help     this help

Environment:
  ADB            adb binary (default: <SDK>/platform-tools/adb)
  ANDROID_HOME   the SDK, used when it has platform-tools/; else ~/android-sdk-local
                 (also the SDK --build hands to Gradle)
  DEVICE_RUN_OUT output root (default ~/tmp/android-device-run)

The one manual step (Chromecast): Settings → System → About → Android TV OS
build, press OK 7 times; then Settings → System → Developer options → turn on
Network debugging (named USB debugging on some builds; either way this script
reaches the Chromecast over the network, port 5555 by default). The IP
is in Settings → Network & Internet → (your network). Accept the "Allow
debugging?" prompt on the TV the first time (tick "Always allow from this
computer"). If the build offers only Wireless debugging with a pairing code,
run "$ADB pair <ip>:<pairing port> <code>" once, then pass <ip>:<port> shown
under Wireless debugging as TARGET.

Examples:
  task chromecast-aquarium -- 192.168.1.50
  scripts/android-device-run.sh --app snowgoons --release --build 192.168.1.50
EOF
}

# ---- arguments ---------------------------------------------------------------
APP=aquarium
TYPE=debug
BUILD=0
APK=""
SECONDS_TO_RUN=20
POKE=0
TARGET=""
while (($#)); do
    case "$1" in
        -h|--help)  usage; exit 0 ;;
        --app)      APP="${2:?--app needs a name}"; shift 2 ;;
        --release)  TYPE=release; shift ;;
        --build)    BUILD=1; shift ;;
        --apk)      APK="${2:?--apk needs a path}"; shift 2 ;;
        --seconds)  SECONDS_TO_RUN="${2:?--seconds needs a number}"; shift 2 ;;
        --poke)     POKE=1; shift ;;
        -*)         echo "android-device-run: unknown option $1 (see --help)" >&2; exit 2 ;;
        *)          if [[ -n "$TARGET" ]]; then echo "android-device-run: one TARGET only" >&2; exit 2; fi
                    TARGET="$1"; shift ;;
    esac
done

case "$APP" in
    aquarium)  PKG=org.worldfoundry.wf_game.aquarium ;;
    snowgoons) PKG=org.worldfoundry.wf_game ;;
    *) echo "android-device-run: --app must be aquarium or snowgoons, not '$APP'" >&2; exit 2 ;;
esac
[[ "$SECONDS_TO_RUN" =~ ^[0-9]+$ ]] || { echo "android-device-run: --seconds wants a whole number" >&2; exit 2; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The first SDK that exists: $ANDROID_HOME (this machine's shell profile has pointed it at a
# directory that no longer exists), then ~/android-sdk-local (where the NDK + platform-tools live).
sdk=""
for d in "${ANDROID_HOME:-}" "$HOME/android-sdk-local"; do
    if [[ -n "$d" && -d "$d/platform-tools" ]]; then sdk="$d"; break; fi
done
export ANDROID_HOME="${sdk:-$HOME/android-sdk-local}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
ACTIVITY="$PKG/android.app.NativeActivity"
[[ -n "$APK" ]] || APK="$REPO/android/app/build/outputs/apk/$APP/$TYPE/worldfoundry-$APP-$TYPE.apk"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "$(ts) $*"; }
RESULTS=()
result() { RESULTS+=("$1  $2"); say "$1  $2"; }
die() {   # die "what failed" "next step" ...
    say "FAIL  $1"
    shift
    local s
    for s in "$@"; do echo "      → $s"; done
    exit 1
}

[[ -x "$ADB" ]] || die "adb not found at $ADB" \
    "set ADB=/path/to/adb, or ANDROID_HOME to an SDK with platform-tools"

# ---- build (optional) -----------------------------------------------------------
if ((BUILD)); then
    task="assemble${APP^}${TYPE^}"
    say "building: (cd android && ./gradlew :app:$task)"
    (cd "$REPO/android" && ./gradlew ":app:$task" --console=plain) \
        || die "Gradle $task failed" "read the Gradle output above; ANDROID_HOME=$ANDROID_HOME"
fi
[[ -f "$APK" ]] || die "APK not found: $APK" \
    "build it: scripts/android-device-run.sh --build ... (or: cd android && ANDROID_HOME=$ANDROID_HOME ./gradlew :app:assemble${APP^}${TYPE^})" \
    "or download worldfoundry-$APP-debug.apk from the Codemagic android-apk-debug build and pass --apk PATH"

# ---- connect ------------------------------------------------------------------------
if [[ -n "$TARGET" && "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    TARGET="$TARGET:5555"
fi
if [[ -n "$TARGET" && "$TARGET" == *:* ]]; then
    say "adb connect $TARGET (20 s limit)"
    # An address nobody answers on makes adb connect wait for the TCP timeout (minutes).
    out="$(timeout 20 "$ADB" connect "$TARGET" 2>&1 || true)"
    [[ -n "$out" ]] || out="no answer in 20 s"
    say "adb connect $TARGET: $out"
    case "$out" in
        *"connected to"*) ;;
        *) die "cannot connect to $TARGET" \
               "on the TV: Settings → System → Developer options → Network debugging is ON" \
               "check the IP (Settings → Network & Internet) and that this computer is on the same network" \
               "then re-run this command" ;;
    esac
fi
if [[ -z "$TARGET" ]]; then
    mapfile -t devs < <("$ADB" devices | awk 'NR > 1 && NF >= 2 {print $1}')
    ((${#devs[@]} == 1)) || die "${#devs[@]} devices attached; say which one" \
        "pass the Chromecast's IP (or a serial from 'adb devices') as TARGET"
    TARGET="${devs[0]}"
fi
A=("$ADB" -s "$TARGET")

state=""
for _ in $(seq 1 30); do
    state="$("${A[@]}" get-state 2>&1 || true)"
    [[ "$state" == device ]] && break
    [[ "$state" == *unauthorized* ]] && break
    sleep 1
done
case "$state" in
    device) result PASS "device $TARGET online" ;;
    *unauthorized*) die "device $TARGET is unauthorized" \
        "on the TV, accept 'Allow network debugging?' (tick 'Always allow from this computer')" \
        "if no prompt shows: $ADB disconnect $TARGET; toggle Network debugging off and on; re-run" ;;
    *offline*) die "device $TARGET is offline" \
        "$ADB disconnect $TARGET, then re-run; if it stays offline, toggle Network debugging off and on" ;;
    *) die "device $TARGET not ready: $state" "check '$ADB devices'; re-run" ;;
esac

OUTDIR="${DEVICE_RUN_OUT:-$HOME/tmp/android-device-run}/$APP-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUTDIR"

prop() { "${A[@]}" shell getprop "$1" 2>/dev/null | tr -d '\r'; }
model="$(prop ro.product.model)"; sdk="$(prop ro.build.version.sdk)"; abis="$(prop ro.product.cpu.abilist)"
soc="$(prop ro.soc.model)"; [[ -n "$soc" ]] || soc="$(prop ro.board.platform)"
size="$("${A[@]}" shell wm size 2>/dev/null | tr -d '\r' | tail -1)"
uimode="$("${A[@]}" shell dumpsys uimode 2>/dev/null | tr -d '\r' | grep -m1 -o 'mCurUiMode=0x[0-9a-f]*' || true)"
result INFO "model '$model', SoC '$soc', API $sdk, ABIs $abis, $size, $uimode"
# The APK's native ABIs (lib/<abi>/) must overlap the device's. The Chromecast HD is armeabi-v7a only
# (Amlogic S805X2, 32-bit Android), the Chromecast 4K and phones are arm64-v8a.
apk_abis="$(unzip -l "$APK" | grep -o 'lib/[A-Za-z0-9_-]*/' | cut -d/ -f2 | sort -u | tr '\n' ' ')"
match=""
for a in $apk_abis; do [[ ",$abis," == *",$a,"* ]] && match="$match$a "; done
result INFO "APK ABIs: ${apk_abis:-none}; usable on this device: ${match:-none}"
[[ -n "$match" ]] || die "the APK has no native ABI this device supports (APK: ${apk_abis:-none}; device: $abis)" \
    "build the missing ABI (android/app/build.gradle.kts abiFilters) and re-run"

# ---- install + launch -------------------------------------------------------------------
say "installing $APK ($(stat -c%s "$APK") bytes)"
if ! out="$("${A[@]}" install -r "$APK" 2>&1)"; then
    echo "$out"
    case "$out" in
        *INSTALL_FAILED_UPDATE_INCOMPATIBLE*) die "install failed: signature differs from the installed $PKG" \
            "$ADB -s $TARGET uninstall $PKG   (drops the app's data), then re-run" ;;
        *INSTALL_FAILED_NO_MATCHING_ABIS*) die "install failed: no matching ABI (APK: ${apk_abis:-none}; device: $abis)" ;;
        *INSTALL_FAILED_INSUFFICIENT_STORAGE*) die "install failed: not enough storage" \
            "free space on the device (Settings → System → Storage), then re-run" ;;
        *INSTALL_FAILED_OLDER_SDK*) die "install failed: device API $sdk is below the APK's minSdk" ;;
        *) die "install failed (output above)" "re-run; if it persists: $ADB -s $TARGET uninstall $PKG" ;;
    esac
fi
result PASS "installed $PKG"

"${A[@]}" shell am force-stop "$PKG" >/dev/null 2>&1 || true
"${A[@]}" logcat -c >/dev/null 2>&1 || true
say "launching $ACTIVITY"
start="$("${A[@]}" shell am start -W -n "$ACTIVITY" 2>&1 | tr -d '\r')"
echo "$start" > "$OUTDIR/am-start.txt"
if [[ "$start" == *Error* || "$start" == *Exception* ]]; then
    echo "$start"
    die "am start failed" "see $OUTDIR/am-start.txt"
fi
result PASS "launched ($(grep -m1 -o 'TotalTime: [0-9]*' <<<"$start" || echo 'TotalTime: ?') ms)"

say "running for $SECONDS_TO_RUN s"
sleep "$SECONDS_TO_RUN"

pid="$("${A[@]}" shell pidof "$PKG" 2>/dev/null | tr -d '\r' || true)"
if [[ -n "$pid" ]]; then result PASS "process alive after $SECONDS_TO_RUN s (pid $pid)"
else result FAIL "process not running after $SECONDS_TO_RUN s (crashed or exited; see logcat-wf.txt)"; fi

# ---- evidence ---------------------------------------------------------------------------
"${A[@]}" exec-out screencap -p > "$OUTDIR/screen.png" 2>/dev/null || true
"${A[@]}" logcat -d -v threadtime > "$OUTDIR/logcat-full.txt" 2>/dev/null || true
"${A[@]}" logcat -d -v threadtime -s wf_game:V AndroidRuntime:E DEBUG:V libc:F ActivityManager:I \
    > "$OUTDIR/logcat-wf.txt" 2>/dev/null || true
"${A[@]}" exec-out cat "/sdcard/Android/data/$PKG/files/wf.log" > "$OUTDIR/wf.log" 2>/dev/null || true
[[ -s "$OUTDIR/wf.log" ]] || { rm -f "$OUTDIR/wf.log"; result INFO "wf.log not readable over adb (Android 11+ scoping); open it with the log viewer app"; }

if [[ "$(head -c 8 "$OUTDIR/screen.png" | od -An -tx1 | tr -d ' \n')" == 89504e470d0a1a0a ]]; then
    colours="$(python3 - "$OUTDIR/screen.png" <<'PY' 2>/dev/null || echo "?"
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
print(len(set(im.resize((160, 90)).getdata())), "%dx%d" % im.size)
PY
)"
    if [[ "${colours%% *}" =~ ^[0-9]+$ ]] && (("${colours%% *}" < 8)); then
        result FAIL "screenshot is (nearly) uniform ($colours colours): black or blank screen"
    else
        result PASS "screenshot $OUTDIR/screen.png ($colours distinct colours at 160x90) — open it and look"
    fi
else
    result FAIL "screencap did not return a PNG (see $OUTDIR/screen.png)"
fi

crash="$(grep -E 'Fatal signal|wf_game crashed|FatalError|FATAL EXCEPTION|Abort message' "$OUTDIR/logcat-full.txt" | head -5 || true)"
if [[ -n "$crash" ]]; then result FAIL "crash lines in logcat:"; echo "$crash"
else result PASS "no crash lines in logcat"; fi

tvline="$(grep -m1 -o 'android_main: uiMode=[0-9]* (tv=[01])' "$OUTDIR/logcat-wf.txt" || true)"
case "$tvline" in
    *"tv=1"*) result INFO "TV mode detected ($tvline): the touch HUD is hidden" ;;
    *"tv=0"*) result INFO "not TV mode ($tvline): the touch HUD is drawn (expected on a phone)" ;;
    *)        result FAIL "no 'android_main: uiMode=' line from wf_game in logcat: the native side did not start" ;;
esac
grep -q 'android_main: EGL ready' "$OUTDIR/logcat-wf.txt" \
    && result PASS "EGL context up (android_main: EGL ready)" \
    || result FAIL "no 'android_main: EGL ready' in logcat"

# Frame pacing: SurfaceFlinger's last ~127 present times of the app's layer. The engine logs no
# per-frame timing of its own, so this is the frame interval the display actually got.
layer="$("${A[@]}" shell dumpsys SurfaceFlinger --list 2>/dev/null | tr -d '\r' | grep -F "$PKG" | grep -F NativeActivity | head -1 || true)"
if [[ -n "$layer" ]]; then
    "${A[@]}" shell dumpsys SurfaceFlinger --latency "\"$layer\"" 2>/dev/null | tr -d '\r' > "$OUTDIR/frames.txt" || true
    pacing="$(awk 'NR == 1 {refresh = $1 / 1e6; next}
                   NF == 3 && $2 > 0 && $2 < 9e18 {t[n++] = $2}
                   END {
                       if (n < 10) {print "too few frames (" n ")"; exit}
                       for (i = 1; i < n; i++) d[i - 1] = (t[i] - t[i - 1]) / 1e6
                       m = n - 1
                       for (i = 0; i < m; i++) for (j = i + 1; j < m; j++) if (d[j] < d[i]) {x = d[i]; d[i] = d[j]; d[j] = x}
                       printf "%d frames: median %.1f ms (%.1f fps), p90 %.1f ms, worst %.1f ms; display refresh %.2f ms",
                              n, d[int(m / 2)], ((d[int(m / 2)] > 0) ? 1000 / d[int(m / 2)] : 0), d[int(m * 0.9)], d[m - 1], refresh
                   }' "$OUTDIR/frames.txt")"
    result INFO "frame pacing ($layer): $pacing"
else
    result INFO "no SurfaceFlinger layer for $PKG found; frame pacing not measured"
fi

if ((POKE)); then
    say "poke: D-pad RIGHT held 1.5 s, then UP"
    "${A[@]}" shell input keyevent --longpress KEYCODE_DPAD_RIGHT >/dev/null 2>&1 || true
    "${A[@]}" shell input keyevent --longpress KEYCODE_DPAD_RIGHT >/dev/null 2>&1 || true
    "${A[@]}" shell input keyevent --longpress KEYCODE_DPAD_UP >/dev/null 2>&1 || true
    sleep 2
    "${A[@]}" exec-out screencap -p > "$OUTDIR/screen-after-keys.png" 2>/dev/null || true
    result INFO "screen-after-keys.png taken: compare the fish's position with screen.png"
fi

printf '%s\n' "${RESULTS[@]}" > "$OUTDIR/summary.txt"
echo
say "evidence in $OUTDIR"
if printf '%s\n' "${RESULTS[@]}" | grep -q '^FAIL'; then
    say "RESULT: FAIL — see the FAIL lines above and $OUTDIR/logcat-wf.txt"
    exit 1
fi
say "RESULT: PASS — now look at $OUTDIR/screen.png, then play with a gamepad (see the plan's control table)"
