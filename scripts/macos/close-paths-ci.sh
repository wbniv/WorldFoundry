#!/bin/bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: scripts/macos/close-paths-ci.sh [-h|--help]

Codemagic macos-desktop-debug step: prove wf_game's macOS close paths and
-fullscreen with no human and no VNC client.
Plan: docs/plans/2026-09-21-macos-close-paths.md ("CI step").

  MACOS CMD-Q          real ⌘Q key event -> process exits, status 0
  MACOS RED BUTTON     press the window's AXCloseButton -> exits, status 0
  MACOS ESC STAYS OPEN Esc x2 -> still running 4 s later (with a key-delivery
                       control, or the check is vacuous)
  MACOS FULLSCREEN     -fullscreen -> the window's frame equals the main display's
  MACOS BUNDLE LAUNCH  open engine/wf_game.app the way a double-click does (Finder,
                       else LaunchServices `open`), no arguments -> a process with
                       an on-screen window, which then quits on ⌘Q
  MACOS BUNDLE KEYS    the same launch with WF_MACOS_KEYLOG=1: which mechanisms'
                       keys reach GLFW's key callback (informational)

Key delivery is read from the engine's own key log (WF_MACOS_KEYLOG=1 prints
"macos: key <glfw-key> ... action <0|1|2>" from hal/macos/window_macos.mm), not
from the player moving: the "ball pos" logger that used to stand in for it was
deleted from jolt_backend.cc on 2026-10-10 (d6851aa7).

Each check tries delivery mechanisms in order and names the one that worked:
  system-events  osascript -> System Events (Accessibility, granted below)
  ax-api         AXUIElement from wf_ui_probe (Accessibility)
  cgevent-pid    CGEvent.postToPid from wf_ui_probe (PostEvent)

!! It writes the runner's TCC database (Accessibility / PostEvent / Apple
!! Events / ScreenCapture grants) with sudo. That is ONLY acceptable on an
!! ephemeral CI VM; never run this on a machine you keep.

Environment:
  CM_BUILD_DIR         repo checkout (required; Codemagic sets it)
  OUT_DIR              where logs go (default: $CM_BUILD_DIR)
  CLOSE_PATHS_STRICT   space-separated subset of "cmdq red esc fullscreen bundle";
                       exit 1 if any of those checks FAILs (default: none)
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") ;;
    *) usage >&2; exit 2 ;;
esac

: "${CM_BUILD_DIR:?CM_BUILD_DIR must be set (the repo checkout)}"
OUT_DIR="${OUT_DIR:-$CM_BUILD_DIR}"
STRICT="${CLOSE_PATHS_STRICT:-}"
APP="$CM_BUILD_DIR/engine/wf_game.app"
WF_GAME="$APP/Contents/MacOS/wf_game"
LEVEL="$CM_BUILD_DIR/wflevels/snowgoons-blender/snowgoons-standalone.iff"
GAME_DIR="$CM_BUILD_DIR/wfsource/source/game"
PROBE_SRC="$CM_BUILD_DIR/scripts/macos/wf_ui_probe.swift"
PROBE="$OUT_DIR/wf_ui_probe"
mkdir -p "$OUT_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "$(ts) $*"; }

# run_to SECS cmd... — run with a hard timeout (macOS ships no `timeout`).
# A first Apple Event can raise a consent dialog nobody will answer; that must
# cost seconds, not the whole build. Returns the command's status, 124 on timeout.
run_to() {
    local secs=$1; shift
    "$@" &
    local p=$! n=0
    while kill -0 "$p" 2>/dev/null; do
        if [ "$n" -ge $((secs * 5)) ]; then
            kill -KILL "$p" 2>/dev/null || true
            wait "$p" 2>/dev/null || true
            return 124
        fi
        sleep 0.2; n=$((n + 1))
    done
    local rc=0
    wait "$p" || rc=$?
    return "$rc"
}

# se "applescript line" ... — osascript with a timeout; prints result and status.
se() {
    local rc=0 outp a
    local argv=()
    for a in "$@"; do argv+=(-e "$a"); done
    outp=$(run_to 20 osascript "${argv[@]}" 2>&1) || rc=$?
    say "  osascript rc=$rc: ${outp:-<no output>}"
    return "$rc"
}

probe() {
    [ -x "$PROBE" ] || { say "  probe unavailable"; return 1; }
    local rc=0
    run_to 20 "$PROBE" "$@" || rc=$?
    [ "$rc" -eq 0 ] || say "  probe $1 rc=$rc"
    return "$rc"
}

#------------------------------------------------------------------------------
say "=== environment ==="
sw_vers || true
csrutil status 2>&1 || true
say "user: $(id -un)  passwordless sudo: $(sudo -n true 2>/dev/null && echo yes || echo NO)"
say "process ancestry of this step (TCC charges events to the responsible one):"
ANCESTORS=()
p=$$
while [ -n "$p" ] && [ "$p" -gt 1 ]; do
    exe=$(ps -o comm= -p "$p" 2>/dev/null | sed 's/^-//' || true)
    [ -n "$exe" ] || break
    say "  pid $p: $exe"
    case "$exe" in
        /*) ANCESTORS+=("$exe") ;;
        *) r=$(command -v "$exe" 2>/dev/null || true); [ -n "$r" ] && ANCESTORS+=("$r") ;;
    esac
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ' || true)
done

say "=== build wf_ui_probe ==="
if run_to 180 swiftc -O -o "$PROBE" "$PROBE_SRC"; then
    say "wf_ui_probe built: $PROBE"
else
    say "wf_ui_probe did NOT build — ax-api / cgevent-pid mechanisms and window bounds unavailable"
    rm -f "$PROBE"
fi

#------------------------------------------------------------------------------
say "=== TCC grants (ephemeral CI VM only) ==="
SYS_DB="/Library/Application Support/com.apple.TCC/TCC.db"
USR_DB="$HOME/Library/Application Support/com.apple.TCC/TCC.db"
CLIENTS=(/usr/bin/osascript /usr/libexec/sshd-keygen-wrapper /bin/bash /bin/zsh /bin/sh)
[ -x "$PROBE" ] && CLIENTS+=("$PROBE")
[ "${#ANCESTORS[@]}" -gt 0 ] && CLIENTS+=("${ANCESTORS[@]}")

tcc_grant() {  # db service client [indirect-bundle-id]
    local db=$1 svc=$2 client=$3 ind=${4:-}
    local cols="service,client,client_type,auth_value,auth_reason,auth_version,flags"
    local vals="'$svc','$client',1,2,4,1,0"
    if [ -n "$ind" ]; then
        cols="$cols,indirect_object_identifier_type,indirect_object_identifier"
        vals="$vals,0,'$ind'"
    fi
    sudo -n sqlite3 "$db" "INSERT OR REPLACE INTO access ($cols) VALUES ($vals);" 2>&1
}

TCC_OK=0 TCC_FAIL=0
if sudo -n true 2>/dev/null; then
    for db in "$SYS_DB" "$USR_DB"; do
        say "schema of $db:"
        sudo -n sqlite3 "$db" "PRAGMA table_info(access);" 2>&1 | awk -F'|' '{printf "%s ", $2} END {print ""}' || true
    done
    seen=" "
    for c in "${CLIENTS[@]}"; do
        case "$seen" in *" $c "*) continue ;; esac
        seen="$seen$c "
        for svc in kTCCServiceAccessibility kTCCServicePostEvent kTCCServiceScreenCapture; do
            if e=$(tcc_grant "$SYS_DB" "$svc" "$c"); then TCC_OK=$((TCC_OK + 1))
            else TCC_FAIL=$((TCC_FAIL + 1)); say "  grant FAILED $svc $c: $e"; fi
        done
        for target in com.apple.systemevents com.apple.finder; do
            if e=$(tcc_grant "$USR_DB" kTCCServiceAppleEvents "$c" "$target"); then TCC_OK=$((TCC_OK + 1))
            else TCC_FAIL=$((TCC_FAIL + 1)); say "  grant FAILED AppleEvents->$target $c: $e"; fi
        done
    done
    say "TCC rows written: $TCC_OK ok, $TCC_FAIL failed"
    say "rows now in the system db for our clients:"
    sudo -n sqlite3 "$SYS_DB" "SELECT service,client,auth_value FROM access WHERE service IN ('kTCCServiceAccessibility','kTCCServicePostEvent','kTCCServiceScreenCapture');" 2>&1 || true
    # tccd caches decisions; launchd restarts it on demand.
    sudo -n killall tccd 2>/dev/null || true
    killall tccd 2>/dev/null || true
    sleep 1
else
    say "no passwordless sudo: TCC grants skipped"
fi

say "=== permission preflight ==="
probe preflight || true
say "System Events 'UI elements enabled' (Accessibility as seen by osascript):"
se 'tell application "System Events" to get UI elements enabled' || true
say "main display before any run:"
probe screen | tee "$OUT_DIR/macos-screen-before.txt" || true

#------------------------------------------------------------------------------
# One wf_game run at a time. The wrapper records the exit status in a file so
# "quit cleanly" is a number, not an impression.
RUN_PID="" RUN_NAME="" RUN_LOG="" RUN_RC=""

start_run() {  # name extra-args...
    RUN_NAME=$1; shift
    RUN_LOG="$OUT_DIR/macos-close-$RUN_NAME.log"
    RUN_RC="$OUT_DIR/macos-close-$RUN_NAME.rc"
    local pidf="$OUT_DIR/macos-close-$RUN_NAME.pid"
    rm -f "$RUN_RC" "$pidf"
    say "--- run '$RUN_NAME': wf_game --windowed $* -L<snowgoons> (real time, runs until closed)"
    (
        set +e
        cd "$GAME_DIR"
        WF_MACOS_KEYLOG=1 "$WF_GAME" --windowed "$@" -L"$LEVEL" >"$RUN_LOG" 2>&1 &
        echo $! > "$pidf"
        wait $!
        echo $? > "$RUN_RC"
    ) &
    local n=0
    while [ ! -s "$pidf" ] && [ "$n" -lt 50 ]; do sleep 0.1; n=$((n + 1)); done
    RUN_PID=$(cat "$pidf")
    n=0
    while [ "$n" -lt 225 ]; do   # 45 s for level load + window
        grep -q "CAMetalLayer attached" "$RUN_LOG" 2>/dev/null && break
        [ -s "$RUN_RC" ] && break
        sleep 0.2; n=$((n + 1))
    done
    if grep -q "CAMetalLayer attached" "$RUN_LOG" 2>/dev/null; then
        say "  pid $RUN_PID: $(grep -m1 '^macos: window ' "$RUN_LOG")"
        sleep 3   # let the game loop settle into steady frames
        return 0
    fi
    say "  NO WINDOW (rc file: $(cat "$RUN_RC" 2>/dev/null || echo none)); log tail:"
    tail -20 "$RUN_LOG" || true
    return 1
}

alive() { [ ! -s "$RUN_RC" ] && kill -0 "$RUN_PID" 2>/dev/null; }

EXIT_SECS=""
wait_exit() {  # timeout-secs; 0 if the process exited in time
    local n=0 lim=$(($1 * 5))
    while [ "$n" -lt "$lim" ]; do
        if [ -s "$RUN_RC" ]; then
            EXIT_SECS=$(awk -v n="$n" 'BEGIN { printf "%.1f", n / 5 }')
            return 0
        fi
        sleep 0.2; n=$((n + 1))
    done
    return 1
}

stop_run() {
    if alive; then
        say "  terminating pid $RUN_PID (SIGTERM, then SIGKILL)"
        kill -TERM "$RUN_PID" 2>/dev/null || true
        wait_exit 5 || { kill -KILL "$RUN_PID" 2>/dev/null || true; wait_exit 5 || true; }
    fi
    wait_exit 5 || true
}

front() {  # make the run frontmost: AX-free first, System Events second
    probe activate "$RUN_PID" || true
    se "tell application \"System Events\" to set frontmost of (first process whose unix id is $RUN_PID) to true" || true
}

# keys LOG GLFW-KEY — presses (action 1) of that key logged by the engine's key
# callback so far. GLFW_KEY_RIGHT=262, GLFW_KEY_ESCAPE=256.
keys() { grep -c "^macos: key $2 scancode [0-9-]* action 1 " "$1" 2>/dev/null || true; }
focus_lines() { grep -E "^macos: (keylog on|window focus)" "$1" 2>/dev/null | tr '\n' ';' || true; }
shutdown_seen() { grep -qi "Calling PIGSExit" "$RUN_LOG" && echo yes || echo no; }

#------------------------------------------------------------------------------
V_CMDQ="FAIL (not run)" V_RED="FAIL (not run)" V_ESC="FAIL (not run)" V_FS="FAIL (not run)"
R_CMDQ=FAIL R_RED=FAIL R_ESC=FAIL R_FS=FAIL
KEY_MECH=""   # the mechanism that delivered ⌘Q, reused to quit later runs

say "=== run A: input control, Esc, then ⌘Q ==="
if start_run cmdq; then
    front
    probe windows "$RUN_PID" || true

    # Input control: does each mechanism reach the game's key callback at all?
    # Counted from the engine's key log (Right = virtual key 124 = GLFW 262), so
    # a press+release inside one glfwPollEvents still counts, which a moving
    # player could not show. Builds 6abd322f/6abd3554 used "ball pos" and saw
    # nothing move; from d6851aa7 on that logger no longer existed at all.
    say "  focus at start: $(focus_lines "$RUN_LOG")"
    k0=$(keys "$RUN_LOG" 262)
    probe hold "$RUN_PID" 124 1 || true
    sleep 0.5
    k1=$(keys "$RUN_LOG" 262)
    front
    se 'tell application "System Events"' 'repeat 5 times' 'key code 124' 'delay 0.1' 'end repeat' 'end tell' || true
    sleep 0.5
    k2=$(keys "$RUN_LOG" 262)
    front
    probe hidhold 124 1 || true
    sleep 0.5
    k3=$(keys "$RUN_LOG" 262)
    say "  Right presses in the key log: start $k0, after cgevent-pid $k1, after system-events $k2, after hid-tap $k3"
    say "  focus after: $(focus_lines "$RUN_LOG")"
    IN_CG=no IN_SE=no IN_HID=no
    [ "${k1:-0}" -gt "${k0:-0}" ] && IN_CG=yes
    [ "${k2:-0}" -gt "${k1:-0}" ] && IN_SE=yes
    [ "${k3:-0}" -gt "${k2:-0}" ] && IN_HID=yes
    say "INPUT CONTROL: cgevent-pid reached=$IN_CG, system-events reached=$IN_SE, hid-tap reached=$IN_HID"

    # Esc x2 via each mechanism, then it must still be running.
    front
    se 'tell application "System Events" to key code 53' || true
    sleep 0.5
    se 'tell application "System Events" to key code 53' || true
    probe key "$RUN_PID" 53 || true
    sleep 0.5
    probe key "$RUN_PID" 53 || true
    front
    probe hidkey 53 || true
    sleep 0.5
    probe hidkey 53 || true
    sleep 4
    if alive; then ESC_ALIVE=yes; else ESC_ALIVE=no; fi
    ESC_SEEN=$(keys "$RUN_LOG" 256)
    say "  after Esc x2 each via system-events, cgevent-pid, hid-tap; 4 s later: still running=$ESC_ALIVE; Esc presses in the key log: ${ESC_SEEN:-0}"

    # ⌘Q ladder.
    if [ "$ESC_ALIVE" = yes ]; then
        front
        say "  ⌘Q via system-events (keystroke \"q\" using command down)"
        se 'tell application "System Events" to keystroke "q" using command down' || true
        if wait_exit 10; then KEY_MECH=system-events; fi
        if [ -z "$KEY_MECH" ]; then
            front
            say "  ⌘Q via cgevent-pid (key code 12 + command, posted to pid $RUN_PID)"
            probe key "$RUN_PID" 12 cmd || true
            if wait_exit 10; then KEY_MECH=cgevent-pid; fi
        fi
    fi
    stop_run
    rc=$(cat "$RUN_RC" 2>/dev/null || echo "?")
    if [ -n "$KEY_MECH" ] && [ "$rc" = 0 ]; then
        R_CMDQ=OK
        V_CMDQ="OK (via $KEY_MECH; exited ${EXIT_SECS} s after the chord; exit status 0; shutdown line: $(shutdown_seen))"
    elif [ -n "$KEY_MECH" ]; then
        V_CMDQ="FAIL (via $KEY_MECH exited after ${EXIT_SECS} s but exit status $rc; shutdown line: $(shutdown_seen))"
    else
        V_CMDQ="FAIL (no mechanism made it exit within 10 s; esc-alive=$ESC_ALIVE; final exit status $rc after termination)"
    fi

    # Esc is only a pass if Esc itself demonstrably reached GLFW's key
    # callback and the app kept running. ⌘Q is a menu key-equivalent, a
    # different route, so it proves the app was frontmost but not that a plain
    # key reached the key handler.
    ctrl=""
    [ "$IN_HID" = yes ] && ctrl="hid-tap"
    [ "$IN_CG" = yes ] && ctrl="${ctrl:+$ctrl, }cgevent-pid"
    [ "$IN_SE" = yes ] && ctrl="${ctrl:+$ctrl, }system-events"
    if [ "$ESC_ALIVE" = yes ] && [ "${ESC_SEEN:-0}" -gt 0 ]; then
        R_ESC=OK
        V_ESC="OK (Esc reached the key callback ${ESC_SEEN} time(s) and the app was still running 4 s later; Right reached it via: ${ctrl:-none})"
    elif [ "$ESC_ALIVE" = yes ]; then
        V_ESC="FAIL (still running, but no Esc press reached the key callback, so Esc is unproven; Right reached it via: ${ctrl:-none}; focus: $(focus_lines "$RUN_LOG"); ⌘Q mechanism: ${KEY_MECH:-none})"
    else
        V_ESC="FAIL (process gone after Esc; exit status $rc)"
    fi
else
    V_CMDQ="FAIL (no window)"; V_ESC="FAIL (no window)"
    stop_run
fi

#------------------------------------------------------------------------------
say "=== run B: red close button ==="
if start_run red; then
    front
    probe windows "$RUN_PID" || true
    se "tell application \"System Events\" to tell (first process whose unix id is $RUN_PID) to get subrole of buttons of window 1" || true
    probe axbutton "$RUN_PID" | tee "$OUT_DIR/macos-close-red-button.txt" || true
    MECH=""
    say "  red button via system-events (click the AXCloseButton)"
    se "tell application \"System Events\" to tell (first process whose unix id is $RUN_PID) to click (first button of window 1 whose subrole is \"AXCloseButton\")" || true
    if wait_exit 10; then MECH=system-events; fi
    if [ -z "$MECH" ]; then
        say "  red button via ax-api (AXPress on kAXCloseButtonAttribute)"
        probe axclose "$RUN_PID" || true
        if wait_exit 10; then MECH=ax-api; fi
    fi
    if [ -z "$MECH" ]; then
        # Last resort: a pointer click posted to the pid at the button's centre
        # (from AX when available, else estimated from the window's top-left).
        c=$(sed -n 's/.*center \([0-9-]*\),\([0-9-]*\).*/\1 \2/p' "$OUT_DIR/macos-close-red-button.txt" 2>/dev/null || true)
        how="from AX"
        if [ -z "$c" ]; then
            c=$(probe windows "$RUN_PID" | sed -n 's/.*onscreen=true bounds=\([0-9-]*\),\([0-9-]*\) .*/\1 \2/p' | head -1 || true)
            [ -n "$c" ] && c="$(( ${c% *} + 14 )) $(( ${c#* } + 14 ))"
            how="ESTIMATED as window origin + (14,14)"
        fi
        if [ -n "$c" ]; then
            say "  red button via cgevent-pid click at $c ($how)"
            probe click "$RUN_PID" $c || true
            if wait_exit 10; then MECH="cgevent-pid click ($how)"; fi
        fi
    fi
    stop_run
    rc=$(cat "$RUN_RC" 2>/dev/null || echo "?")
    if [ -n "$MECH" ] && [ "$rc" = 0 ]; then
        R_RED=OK
        V_RED="OK (via $MECH; exited ${EXIT_SECS} s after the press; exit status 0; shutdown line: $(shutdown_seen))"
    elif [ -n "$MECH" ]; then
        V_RED="FAIL (via $MECH exited but exit status $rc)"
    else
        V_RED="FAIL (no mechanism made it exit within 10 s; final exit status $rc after termination)"
    fi
else
    V_RED="FAIL (no window)"
    stop_run
fi

#------------------------------------------------------------------------------
say "=== run C: -fullscreen ==="
if start_run fullscreen -fullscreen; then
    sleep 2
    probe windows "$RUN_PID" | tee "$OUT_DIR/macos-fullscreen-windows.txt" || true
    probe screen | tee "$OUT_DIR/macos-screen-during.txt" || true
    run_to 20 screencapture -x "$OUT_DIR/macos-fullscreen.png" || say "  screencapture failed"
    disp=$(sed -n 's/.*main display id=[0-9]* bounds=\(.*\)$/\1/p' "$OUT_DIR/macos-screen-during.txt" | head -1 || true)
    wins=$(sed -n 's/.*onscreen=true bounds=\(.*\)$/\1/p' "$OUT_DIR/macos-fullscreen-windows.txt" || true)
    mode_before=$(sed -n 's/.*main display mode \([^,]*\),.*/\1/p' "$OUT_DIR/macos-screen-before.txt" | head -1 || true)
    mode_during=$(sed -n 's/.*main display mode \([^,]*\),.*/\1/p' "$OUT_DIR/macos-screen-during.txt" | head -1 || true)
    scale=$(sed -n 's/.*NSScreen\[0\].*backingScaleFactor=\(.*\)$/\1/p' "$OUT_DIR/macos-screen-during.txt" | head -1 || true)
    winline=$(grep -m1 '^macos: window ' "$RUN_LOG" || true)
    say "  display: [$disp]  onscreen windows: [$(echo $wins)]"
    say "  display mode before [$mode_before] during [$mode_during]; backingScaleFactor $scale"
    match=no
    if [ -n "$disp" ]; then
        while IFS= read -r w; do [ "$w" = "$disp" ] && match=yes; done <<< "$wins"
    fi
    # Quit it the way run A proved works, if any; otherwise terminate.
    if [ "$KEY_MECH" = system-events ]; then
        front; se 'tell application "System Events" to keystroke "q" using command down' || true
    elif [ "$KEY_MECH" = cgevent-pid ]; then
        probe key "$RUN_PID" 12 cmd || true
    fi
    wait_exit 10 || true
    stop_run
    sleep 1
    probe screen | tee "$OUT_DIR/macos-screen-after.txt" || true
    mode_after=$(sed -n 's/.*main display mode \([^,]*\),.*/\1/p' "$OUT_DIR/macos-screen-after.txt" | head -1 || true)
    restored=$([ "$mode_after" = "$mode_before" ] && echo yes || echo NO)
    rc=$(cat "$RUN_RC" 2>/dev/null || echo "?")
    detail="window [$(echo $wins)] vs main display [$disp]; mode before $mode_before, during $mode_during, after $mode_after (restored: $restored); backingScaleFactor $scale — Retina NOT testable here; engine: $winline; exit status $rc"
    if [ "$match" = yes ]; then R_FS=OK; V_FS="OK ($detail)"; else V_FS="FAIL ($detail)"; fi
    # Build 1 found GLFW switching the display to the mode nearest the 640x480
    # request (1024x768 -> 800x600) instead of covering it at native size.
    if [ -n "$mode_before" ] && [ "$mode_during" = "$mode_before" ]; then
        V_FSN="OK (display stayed at $mode_before)"
    else
        V_FSN="FAIL (display mode switched $mode_before -> $mode_during while fullscreen; restored after exit: $restored)"
    fi
else
    V_FS="FAIL (no window)"
    stop_run
fi

#------------------------------------------------------------------------------
# Runs D and E: the bundle, launched the way a double-click launches it. No -L,
# no flags: hal/macos/platform_main.cc opens a window when there are no
# arguments, and the level comes from Contents/Resources/cd.iff. The process is
# launchd's child, not ours, so there is no exit status: "quit cleanly" here is
# "gone within 10 s of ⌘Q".
bundle_pid() { pgrep -n -x wf_game 2>/dev/null || true; }
B_PID=""
wait_bundle_up() {  # 45 s for a wf_game process with an on-screen window
    local n=0
    B_PID=""
    while [ "$n" -lt 90 ]; do
        B_PID=$(bundle_pid)
        if [ -n "$B_PID" ] && probe windows "$B_PID" 2>/dev/null | grep -q "onscreen=true"; then
            return 0
        fi
        sleep 0.5; n=$((n + 1))
    done
    return 1
}
bundle_quit() {  # ⌘Q via System Events; 0 if the process is gone within 10 s
    local n=0
    probe activate "$B_PID" || true
    se "tell application \"System Events\" to set frontmost of (first process whose unix id is $B_PID) to true" || true
    se 'tell application "System Events" to keystroke "q" using command down' || true
    while [ "$n" -lt 50 ]; do
        kill -0 "$B_PID" 2>/dev/null || { EXIT_SECS=$(awk -v n="$n" 'BEGIN { printf "%.1f", n / 5 }'); return 0; }
        sleep 0.2; n=$((n + 1))
    done
    return 1
}
bundle_kill() {
    if [ -n "$B_PID" ] && kill -0 "$B_PID" 2>/dev/null; then
        say "  terminating pid $B_PID"
        kill -TERM "$B_PID" 2>/dev/null || true
        sleep 2
        kill -KILL "$B_PID" 2>/dev/null || true
    fi
}

V_BUNDLE="FAIL (not run)" R_BUNDLE=FAIL V_BKEYS="FAIL (not run)"
say "=== run D: launch the .app like a double-click (no arguments) ==="
if [ -n "$(bundle_pid)" ]; then
    say "  a wf_game process is still running before the launch; terminating it"
    B_PID=$(bundle_pid); bundle_kill
fi
PL_EXE=$(plutil -extract CFBundleExecutable raw "$APP/Contents/Info.plist" 2>&1 || true)
if [ -x "$APP/Contents/MacOS/$PL_EXE" ]; then PL_OK=yes; else PL_OK=NO; fi
say "  Info.plist CFBundleExecutable=[$PL_EXE]; Contents/MacOS/$PL_EXE executable: $PL_OK"
ls -l "$APP/Contents/Resources" 2>&1 | tee "$OUT_DIR/macos-bundle-resources.txt" || true
B_MECH=""
say "  launch via Finder (open POSIX file — the double-click's own Apple Event)"
se "tell application \"Finder\" to open (POSIX file \"$APP\")" || true
if wait_bundle_up; then
    B_MECH=finder
else
    bundle_kill
    say "  launch via LaunchServices: open $APP"
    o=$(run_to 30 open "$APP" 2>&1) || say "  open rc=$?: ${o:-<no output>}"
    wait_bundle_up && B_MECH="launchservices-open"
fi
if [ -n "$B_MECH" ]; then
    ps -o pid=,ppid=,user=,command= -p "$B_PID" | tee "$OUT_DIR/macos-bundle-ps.txt" || true
    B_PPID=$(ps -o ppid= -p "$B_PID" 2>/dev/null | tr -d ' ' || true)
    # Everything after the executable's name (greedy: the last "wf_game" in the line).
    B_ARGS=$(ps -o command= -p "$B_PID" 2>/dev/null | sed 's|^.*wf_game *||' || true)
    probe windows "$B_PID" | tee "$OUT_DIR/macos-bundle-windows.txt" || true
    B_WIN=$(sed -n 's/.*onscreen=true bounds=\(.*\)$/\1/p' "$OUT_DIR/macos-bundle-windows.txt" | head -1 || true)
    sleep 5   # let the level load and draw before the screenshot
    run_to 20 screencapture -x "$OUT_DIR/macos-bundle-launch.png" || say "  screencapture failed"
    if bundle_quit; then
        R_BUNDLE=OK
        V_BUNDLE="OK (via $B_MECH; pid $B_PID, parent pid $B_PPID, arguments [${B_ARGS}]; on-screen window $B_WIN; quit by ⌘Q, gone ${EXIT_SECS} s later; CFBundleExecutable=$PL_EXE)"
    else
        V_BUNDLE="FAIL (via $B_MECH a window came up ($B_WIN) but ⌘Q did not end pid $B_PID within 10 s)"
        bundle_kill
    fi
else
    V_BUNDLE="FAIL (neither Finder nor open produced a wf_game process with an on-screen window in 45 s; CFBundleExecutable=[$PL_EXE] executable=$PL_OK)"
    bundle_kill
fi

say "=== run E: the same launch with the key log, through open --env/--stdout ==="
B_LOG="$OUT_DIR/macos-bundle-keys.log"
rm -f "$B_LOG" "$OUT_DIR/macos-bundle-keys.err"
o=$(run_to 30 open --env WF_MACOS_KEYLOG=1 --stdout "$B_LOG" --stderr "$OUT_DIR/macos-bundle-keys.err" "$APP" 2>&1) \
    || say "  open rc=$?: ${o:-<no output>}"
if wait_bundle_up; then
    n=0
    while [ "$n" -lt 100 ] && ! grep -q "CAMetalLayer attached" "$B_LOG" 2>/dev/null; do sleep 0.2; n=$((n + 1)); done
    grep -E "^macos: (launched|window |keylog)" "$B_LOG" || true
    k0=$(keys "$B_LOG" 262)
    probe hold "$B_PID" 124 1 || true
    sleep 0.5
    k1=$(keys "$B_LOG" 262)
    se 'tell application "System Events"' 'repeat 5 times' 'key code 124' 'delay 0.1' 'end repeat' 'end tell' || true
    sleep 0.5
    k2=$(keys "$B_LOG" 262)
    probe hidhold 124 1 || true
    sleep 0.5
    k3=$(keys "$B_LOG" 262)
    e0=$(keys "$B_LOG" 256)
    probe hidkey 53 || true
    se 'tell application "System Events" to key code 53' || true
    sleep 2
    e1=$(keys "$B_LOG" 256)
    kill -0 "$B_PID" 2>/dev/null && e_alive=yes || e_alive=no
    V_BKEYS="Right presses logged: cgevent-pid $((${k1:-0} - ${k0:-0})), system-events $((${k2:-0} - ${k1:-0})), hid-tap $((${k3:-0} - ${k2:-0})); Esc presses logged $((${e1:-0} - ${e0:-0})), still running after Esc: $e_alive; focus: $(focus_lines "$B_LOG")"
    bundle_quit || bundle_kill
else
    V_BKEYS="FAIL (no window from open --env; open output: ${o:-none})"
    bundle_kill
fi

#------------------------------------------------------------------------------
echo
echo "--- macOS close paths / fullscreen verdict ---"
echo "MACOS CMD-Q: $V_CMDQ"
echo "MACOS RED BUTTON: $V_RED"
echo "MACOS ESC STAYS OPEN: $V_ESC"
echo "MACOS FULLSCREEN: $V_FS"
echo "MACOS FULLSCREEN NATIVE MODE: ${V_FSN:-FAIL (not run)}"
echo "MACOS BUNDLE LAUNCH: $V_BUNDLE"
echo "MACOS BUNDLE KEYS: $V_BKEYS"
echo "(mechanisms: system-events/ax-api/cgevent-pid/hid-tap are real OS events delivered to"
echo " the running app; none is an in-app self-post. Retina: runner scale ${scale:-?}, untested."
echo " This Debug build compiles DBSTREAM1 out, so no engine shutdown line is logged: exit"
echo " status 0 is the evidence, not a 'Calling PIGSExit()' line.)"

fail=0
for k in $STRICT; do
    case "$k" in
        cmdq) [ "$R_CMDQ" = OK ] || { echo "STRICT: cmdq failed"; fail=1; } ;;
        red) [ "$R_RED" = OK ] || { echo "STRICT: red failed"; fail=1; } ;;
        esc) [ "$R_ESC" = OK ] || { echo "STRICT: esc failed"; fail=1; } ;;
        fullscreen) [ "$R_FS" = OK ] || { echo "STRICT: fullscreen failed"; fail=1; } ;;
        bundle) [ "$R_BUNDLE" = OK ] || { echo "STRICT: bundle failed"; fail=1; } ;;
        *) echo "STRICT: unknown check '$k'"; fail=1 ;;
    esac
done
exit "$fail"
