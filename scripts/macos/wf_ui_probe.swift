// wf_ui_probe — a tiny macOS CLI used by scripts/macos/close-paths-ci.sh on the
// Codemagic runner to observe and drive wf_game's window without a human.
//
// Plan: docs/plans/2026-09-21-macos-close-paths.md ("CI step").
//
// Build (on the runner; Xcode's swiftc):
//     swiftc -O -o wf_ui_probe scripts/macos/wf_ui_probe.swift
//
// Subcommands (all output is one fact per line, "probe: ..." prefixed):
//   preflight            AXIsProcessTrusted / CGPreflightPostEventAccess /
//                        CGPreflightScreenCaptureAccess for THIS binary
//   screen               main display bounds, current mode, every NSScreen's
//                        frame and backingScaleFactor
//   windows PID          every window owned by PID from CGWindowList (bounds are
//                        readable without Accessibility or Screen Recording)
//   activate PID         NSRunningApplication.activate — no Accessibility needed
//   key PID CODE [cmd]   CGEvent key down+up posted to PID (optionally with ⌘)
//   hold PID CODE SECS   CGEvent key down, wait, key up, posted to PID
//   axclose PID          AX API: press window 1's close button (needs Accessibility)
//   axbutton PID         AX API: print window 1's close-button position/size
//   click PID X Y        CGEvent left click at global top-left coords, posted to PID
//
// It never claims success on its own: the caller asserts on the target
// process (exit status, still running, window bounds).

import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

func out(_ s: String) {
    print("probe: " + s)
    fflush(stdout)
}

func usage() {
    print("""
    usage: wf_ui_probe <preflight|screen|windows PID|activate PID|key PID CODE [cmd]|
                        hold PID CODE SECS|axclose PID|axbutton PID|click PID X Y>
    """)
}

func pidArg(_ i: Int) -> pid_t {
    let a = CommandLine.arguments
    guard a.count > i, let p = Int32(a[i]) else { usage(); exit(2) }
    return p
}

func fmt(_ r: CGRect) -> String {
    return "\(Int(r.origin.x)),\(Int(r.origin.y)) \(Int(r.width))x\(Int(r.height))"
}

func postKey(_ pid: pid_t, _ code: CGKeyCode, down: Bool, cmd: Bool) {
    let src = CGEventSource(stateID: .hidSystemState)
    guard let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down) else {
        out("key: CGEvent create failed"); exit(1)
    }
    if cmd { e.flags = .maskCommand }
    e.postToPid(pid)
}

func axWindow1(_ pid: pid_t) -> AXUIElement? {
    let app = AXUIElementCreateApplication(pid)
    var v: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &v)
    guard err == .success, let wins = v as? [AXUIElement], let w = wins.first else {
        out("ax: no window (AXError \(err.rawValue); -25211 = not trusted for Accessibility)")
        return nil
    }
    return w
}

func axCloseButton(_ pid: pid_t) -> AXUIElement? {
    guard let w = axWindow1(pid) else { return nil }
    var b: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(w, kAXCloseButtonAttribute as CFString, &b)
    guard err == .success, let btn = b else {
        out("ax: no close button (AXError \(err.rawValue))")
        return nil
    }
    return (btn as! AXUIElement)
}

let args = CommandLine.arguments
guard args.count >= 2 else { usage(); exit(2) }

switch args[1] {
case "-h", "--help":
    usage()
    exit(0)

case "preflight":
    out("AXIsProcessTrusted=\(AXIsProcessTrusted())")
    if #available(macOS 10.15, *) {
        out("CGPreflightPostEventAccess=\(CGPreflightPostEventAccess())")
        out("CGPreflightScreenCaptureAccess=\(CGPreflightScreenCaptureAccess())")
    }

case "screen":
    let id = CGMainDisplayID()
    out("main display id=\(id) bounds=\(fmt(CGDisplayBounds(id)))")
    if let m = CGDisplayCopyDisplayMode(id) {
        out("main display mode \(m.width)x\(m.height) points, \(m.pixelWidth)x\(m.pixelHeight) pixels, refresh \(m.refreshRate)")
    }
    var n: UInt32 = 0
    CGGetOnlineDisplayList(0, nil, &n)
    out("online displays=\(n)")
    for (i, s) in NSScreen.screens.enumerated() {
        out("NSScreen[\(i)] frame=\(fmt(s.frame)) backingScaleFactor=\(s.backingScaleFactor)")
    }

case "windows":
    let pid = pidArg(2)
    let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
    var found = 0
    for w in list where (w[kCGWindowOwnerPID as String] as? Int32) == pid {
        guard let bd = w[kCGWindowBounds as String] as? NSDictionary,
              let r = CGRect(dictionaryRepresentation: bd as CFDictionary) else { continue }
        let layer = w[kCGWindowLayer as String] as? Int ?? -1
        let on = w[kCGWindowIsOnscreen as String] as? Bool ?? false
        out("window layer=\(layer) onscreen=\(on) bounds=\(fmt(r))")
        found += 1
    }
    out("windows owned by \(pid): \(found)")

case "activate":
    let pid = pidArg(2)
    guard let app = NSRunningApplication(processIdentifier: pid) else {
        out("activate: no running application for pid \(pid)"); exit(1)
    }
    let ok = app.activate(options: [.activateIgnoringOtherApps])
    usleep(300_000)
    out("activate: returned \(ok); frontmost pid now \(NSWorkspace.shared.frontmostApplication?.processIdentifier ?? -1)")

case "key":
    let pid = pidArg(2)
    guard args.count > 3, let code = UInt16(args[3]) else { usage(); exit(2) }
    let cmd = args.count > 4 && args[4] == "cmd"
    postKey(pid, code, down: true, cmd: cmd)
    usleep(60_000)
    postKey(pid, code, down: false, cmd: cmd)
    out("key: posted code \(code)\(cmd ? " with command" : "") to pid \(pid)")

case "hold":
    let pid = pidArg(2)
    guard args.count > 4, let code = UInt16(args[3]), let secs = Double(args[4]) else { usage(); exit(2) }
    postKey(pid, code, down: true, cmd: false)
    usleep(useconds_t(secs * 1_000_000))
    postKey(pid, code, down: false, cmd: false)
    out("hold: posted code \(code) down for \(secs) s to pid \(pid)")

case "axbutton":
    let pid = pidArg(2)
    guard let btn = axCloseButton(pid) else { exit(1) }
    var pv: CFTypeRef?, sv: CFTypeRef?
    AXUIElementCopyAttributeValue(btn, kAXPositionAttribute as CFString, &pv)
    AXUIElementCopyAttributeValue(btn, kAXSizeAttribute as CFString, &sv)
    var p = CGPoint.zero, s = CGSize.zero
    if let pv = pv { AXValueGetValue(pv as! AXValue, .cgPoint, &p) }
    if let sv = sv { AXValueGetValue(sv as! AXValue, .cgSize, &s) }
    out("axbutton: close button at \(Int(p.x)),\(Int(p.y)) size \(Int(s.width))x\(Int(s.height)) center \(Int(p.x + s.width / 2)),\(Int(p.y + s.height / 2))")

case "axclose":
    let pid = pidArg(2)
    guard let btn = axCloseButton(pid) else { exit(1) }
    let err = AXUIElementPerformAction(btn, kAXPressAction as CFString)
    out("axclose: AXPress on close button -> AXError \(err.rawValue)")
    exit(err == .success ? 0 : 1)

case "click":
    let pid = pidArg(2)
    guard args.count > 4, let x = Double(args[3]), let y = Double(args[4]) else { usage(); exit(2) }
    let src = CGEventSource(stateID: .hidSystemState)
    let pt = CGPoint(x: x, y: y)
    for t in [CGEventType.leftMouseDown, .leftMouseUp] {
        guard let e = CGEvent(mouseEventSource: src, mouseType: t, mouseCursorPosition: pt, mouseButton: .left) else {
            out("click: CGEvent create failed"); exit(1)
        }
        e.postToPid(pid)
        usleep(80_000)
    }
    out("click: posted left click at \(Int(x)),\(Int(y)) to pid \(pid)")

default:
    usage()
    exit(2)
}
