// Real taps on the chapter's touch controls (layer 3 of finding-your-way
// docs/plans/2026-11-08-ios-touch-parity.md). XCUITest synthesises touch
// events that reach wf_game through UIKit's own hit-testing, so these taps
// land in WFTouchHudView's touchesBegan, unlike WF_TOUCH_SCRIPT, which presses
// the pad directly. The app runs with -WFTouchDiagnostics 1, which adds the
// accessibility element wf.touch.state whose value is
// "held=0x.... seen=0x.... reading=0|1" (hal/ios/input.mm); `seen` holds every
// button bit pressed since launch. Each check prints one TOUCHTEST line that
// scripts/ios_touch_uitest.py collects.
import XCTest

final class WFTouchUITests: XCTestCase {
    let bundleId = "org.worldfoundry.wf-game"

    override func setUp() {
        continueAfterFailure = true
    }

    func testRealTapsLandscape() throws { try tour(orientation: "landscape", device: .landscapeLeft) }
    func testRealTapsPortrait() throws { try tour(orientation: "portrait", device: .portrait) }

    private func report(_ orientation: String, _ name: String, _ ok: Bool, _ detail: String) {
        print("TOUCHTEST \(orientation) \(name) \(ok ? "PASS" : "FAIL") \(detail)")
        XCTAssertTrue(ok, "\(orientation) \(name): \(detail)")
    }

    private func element(_ app: XCUIApplication, _ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }

    private func state(_ app: XCUIApplication) -> String {
        let e = element(app, "wf.touch.state")
        return e.exists ? ((e.value as? String) ?? "") : ""
    }

    private func field(_ s: String, _ key: String) -> UInt32? {
        guard let r = s.range(of: key + "=") else { return nil }
        let rest = s[r.upperBound...].prefix { !$0.isWhitespace }
        return rest.hasPrefix("0x") ? UInt32(rest.dropFirst(2), radix: 16) : UInt32(rest)
    }

    private func waitFor(_ app: XCUIApplication, _ seconds: Double, _ test: (String) -> Bool) -> String {
        let end = Date().addingTimeInterval(seconds)
        var s = state(app)
        while !test(s) && Date() < end {
            Thread.sleep(forTimeInterval: 0.5)
            s = state(app)
        }
        return s
    }

    private func tour(orientation: String, device: UIDeviceOrientation) throws {
        XCUIDevice.shared.orientation = device
        let app = XCUIApplication(bundleIdentifier: bundleId)
        let extra = (ProcessInfo.processInfo.environment["WF_LAUNCH_ARGS"] ?? "")
            .split(separator: " ").map(String.init)
        app.launchArguments = extra + ["-WFTouchDiagnostics", "1", "-WFOrientation", orientation]
        app.launch()

        // The opening card: only A and C, and the app says it is reading.
        let a = element(app, "wf.touch.A")
        report(orientation, "hud-present", a.waitForExistence(timeout: 90), "wf.touch.A exists")
        var s = waitFor(app, 60) { self.field($0, "reading") == 1 }
        report(orientation, "card-narrows", field(s, "reading") == 1
               && !element(app, "wf.touch.B").exists && !element(app, "wf.touch.D").exists
               && !element(app, "wf.touch.stick").exists && element(app, "wf.touch.C").exists, s)
        let seenBefore = field(s, "seen") ?? 0xffff

        // A real tap where B would be (directly above A) sends nothing over the card.
        a.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: -0.5)).tap()
        Thread.sleep(forTimeInterval: 1.0)
        s = state(app)
        report(orientation, "hidden-b-ignored", field(s, "seen") == seenBefore && field(s, "reading") == 1, s)

        // A real tap on C sends C and closes the card.
        element(app, "wf.touch.C").tap()
        s = waitFor(app, 10) { self.field($0, "reading") == 0 }
        report(orientation, "c-closes-card", (field(s, "seen") ?? 0) & 0x0004 != 0 && field(s, "reading") == 0, s)

        // The full HUD: real taps on B and D, and a held press on the stick's top.
        let b = element(app, "wf.touch.B")
        report(orientation, "full-hud", b.waitForExistence(timeout: 10)
               && element(app, "wf.touch.D").exists && element(app, "wf.touch.stick").exists, s)
        if b.exists { b.tap() }
        if element(app, "wf.touch.D").exists { element(app, "wf.touch.D").tap() }
        let stick = element(app, "wf.touch.stick")
        if stick.exists {
            // 0.9 of the radius up from the centre: inside the ring, past half the radius.
            stick.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.05)).press(forDuration: 1.0)
        }
        Thread.sleep(forTimeInterval: 1.0)
        s = state(app)
        let seen = field(s, "seen") ?? 0
        report(orientation, "b-d-up", seen & 0x0002 != 0 && seen & 0x0008 != 0 && seen & 0x0800 != 0, s)
        report(orientation, "released", field(s, "held") == 0, s)

        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "touch-\(orientation)"
        shot.lifetime = .keepAlways
        add(shot)
        app.terminate()
    }
}
