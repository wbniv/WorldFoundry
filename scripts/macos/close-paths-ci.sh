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
  CLOSE_PATHS_STRICT   space-separated subset of "cmdq red esc fullscreen";
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
WF_GAME="$CM_BUILD_DIR/engine/wf_game.app/Contents/MacOS/wf_game"
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
        if e=$(tcc_grant "$USR_DB" kTCCServiceAppleEvents "$c" com.apple.systemevents); then TCC_OK=$((TCC_OK + 1))
        else TCC_FAIL=$((TCC_FAIL + 1)); say "  grant FAILED AppleEvents $c: $e"; fi
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
        "$WF_GAME" --windowed "$@" -L"$LEVEL" >"$RUN_LOG" 2>&1 &
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

ballpos() { grep "^ball pos" "$RUN_LOG" 2>/dev/null | tail -1 || true; }
shutdown_seen() { grep -qi "Calling PIGSExit" "$RUN_LOG" && echo yes || echo no; }

#------------------------------------------------------------------------------
V_CMDQ="FAIL (not run)" V_RED="FAIL (not run)" V_ESC="FAIL (not run)" V_FS="FAIL (not run)"
R_CMDQ=FAIL R_RED=FAIL R_ESC=FAIL R_FS=FAIL
KEY_MECH=""   # the mechanism that delivered ⌘Q, reused to quit later runs

say "=== run A: input control, Esc, then ⌘Q ==="
if start_run cmdq; then
    front
    probe windows "$RUN_PID" || true

    # Input control: does each mechanism reach the game's key handler at all?
    # Right arrow (key code 124) held moves the player; the engine logs
    # "ball pos" about once a second.
    b0=$(ballpos)
    probe hold "$RUN_PID" 124 2.5 || true
    sleep 1.5
    b1=$(ballpos)
    se 'tell application "System Events"' 'repeat 25 times' 'key code 124' 'delay 0.1' 'end repeat' 'end tell' || true
    sleep 1.5
    b2=$(ballpos)
    say "  ball pos: start [$b0] after cgevent-pid hold [$b1] after system-events presses [$b2]"
    IN_CG=no IN_SE=no
    [ -n "$b1" ] && [ "$b1" != "$b0" ] && IN_CG=yes
    [ -n "$b2" ] && [ "$b2" != "$b1" ] && IN_SE=yes
    say "INPUT CONTROL: cgevent-pid moved=$IN_CG, system-events moved=$IN_SE"

    # Esc x2 via both mechanisms, then it must still be running.
    front
    se 'tell application "System Events" to key code 53' || true
    sleep 0.5
    se 'tell application "System Events" to key code 53' || true
    probe key "$RUN_PID" 53 || true
    sleep 0.5
    probe key "$RUN_PID" 53 || true
    sleep 4
    if alive; then ESC_ALIVE=yes; else ESC_ALIVE=no; fi
    say "  after Esc x2 (system-events) + Esc x2 (cgevent-pid), 4 s later: still running=$ESC_ALIVE"

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

    # Esc is only a pass if keys demonstrably reached the app in this process.
    ctrl=""
    [ -n "$KEY_MECH" ] && ctrl="⌘Q via $KEY_MECH quit the same process"
    [ "$IN_CG" = yes ] && ctrl="${ctrl:+$ctrl; }Right via cgevent-pid moved the player"
    [ "$IN_SE" = yes ] && ctrl="${ctrl:+$ctrl; }Right via system-events moved the player"
    if [ "$ESC_ALIVE" = yes ] && [ -n "$ctrl" ]; then
        R_ESC=OK
        V_ESC="OK (still running 4 s after Esc x4; delivery control: $ctrl)"
    elif [ "$ESC_ALIVE" = yes ]; then
        V_ESC="FAIL (still running, but no control shows keys reached the app — vacuous)"
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
else
    V_FS="FAIL (no window)"
    stop_run
fi

#------------------------------------------------------------------------------
echo
echo "--- macOS close paths / fullscreen verdict ---"
echo "MACOS CMD-Q: $V_CMDQ"
echo "MACOS RED BUTTON: $V_RED"
echo "MACOS ESC STAYS OPEN: $V_ESC"
echo "MACOS FULLSCREEN: $V_FS"
echo "(mechanisms: system-events/ax-api/cgevent-pid are real OS events delivered to the"
echo " running app; none is an in-app self-post. Retina: runner scale ${scale:-?}, untested.)"

fail=0
for k in $STRICT; do
    case "$k" in
        cmdq) [ "$R_CMDQ" = OK ] || { echo "STRICT: cmdq failed"; fail=1; } ;;
        red) [ "$R_RED" = OK ] || { echo "STRICT: red failed"; fail=1; } ;;
        esc) [ "$R_ESC" = OK ] || { echo "STRICT: esc failed"; fail=1; } ;;
        fullscreen) [ "$R_FS" = OK ] || { echo "STRICT: fullscreen failed"; fail=1; } ;;
        *) echo "STRICT: unknown check '$k'"; fail=1 ;;
    esac
done
exit "$fail"
