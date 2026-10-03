| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/3a2d595d) | Phone controller: the page sends its mask every 50 ms while connected (the TV's Wi-Fi dozes at 250 ms) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ec342020) | Phone controller: log every accepted connection and any closed before a request; record the first phone session |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/9cfb58b5) | Aquarium-Chromecast plan and phone mockups: the condo's A is doors and shade, no B button; status of Phase E |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ab919ab8) | Phone as a gamepad, E3: the QR code on the TV overlay (vendored Nayuki qrcodegen, MIT) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/6697f300) | Phone as a gamepad, E2: Android wiring, INTERNET for aquarium and condo, the TV overlay with URL and PIN |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/3c51eafc) | Phone as a gamepad, E1: portable server, protocol and controller page, tested headless on Linux |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/8776018f) | Soundfont: a reproducible recipe (task soundfont) replaces the never-committed florestan-subset.sf2 |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/15dd5ee6) | Aquarium-Chromecast plan: snowgoons is silent on Android (no soundfont, Q*bert sfx not found), so it is not the audio-route check; the display chain does advertise audio, the monitor just has no speakers |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/b655fb35) | Aquarium-Chromecast plan, Phase D: the soundfont is gitignored and absent, so snowgoons' release build fails lint and no flavor can play MIDI music yet |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/712ccf92) | Aquarium-Chromecast plan: tilt steering and haptics in Phase E; Phase D (audio) tied to the SFX plan |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/f583faff) | Aquarium-Chromecast plan: add Phase D, the phone as a gamepad (web controller over the LAN), with mockups |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/c48d5a8b) | Write the missing aquarium-on-Chromecast plan (four docs linked to it): rebuilt from the commits and device-run evidence |

<!--history-meta v1
3a2d595d	author	Will Norris
3a2d595d	added	12
3a2d595d	deleted	3
3a2d595d	files	1
3a2d595d	body	The user chose option (a) over a WifiLock. The Chromecast's radio dozes between packets: median round\ntrip 156 ms with 250 ms frames against 21 to 28 ms with 20 to 50 ms frames, and plain ping behaves the\nsame, so it is the radio. controller.html sends the current mask every KEEPALIVE_MS = 50 ms while the\nsocket is open; a press still goes at once from the pointer handler; t: pings stay at 1 Hz. The TV's 1 s\nrelease-all timeout is unchanged.\n\nTests: the constant is at most 50 ms, about 20 mask frames a second flow, a press leaves the page in the\nsame task as the touch (fails at 250 ms); a hidden page releases at once and a page whose script stops is\nreleased by the TV's timeout; on the server, 50 ms frames hold a button with no log line per frame,\na 2000-frame burst overflows nothing, and 1.2 s gaps (a throttled tab) still release.\nOn the Chromecast HD (condo build installed 18:48 +07), a PC client sending 50 ms frames measured a median\nround trip of 21.5 ms (p90 35 ms, 60 samples) with no timeout in 60 s. Plan design item 1, risk table,\nfinding and verification 14 updated; mockups 2 and 4 regenerated.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
ec342020	author	Will Norris
ec342020	added	20
ec342020	deleted	3
ec342020	files	1
ec342020	body	The user's first scan showed a page that never loaded and the TV logged nothing, because only completed\nrequests were logged; the phone turned out to be on another network. phonepad.cc now logs "connection\nfrom <peer>" on accept, "<peer> closed the connection before a complete request (N bytes received)", and\nthe byte count on the 5 s request timeout, so "never reached the TV" is visible in logcat. Test included\n(fails on the previous phonepad.cc).\n\nPlan: a risk-table row for a phone on another network; verification 14 and 15 record the user's session\non the Chromecast HD (condo, PASS by hand report, backed by the TV's log: page served, A/C/D/E/F, the stick,\nD+stick orbit, two unexplained 1 s timeouts while idle that released and reconnected) and what was not\ntested (aquarium, latency, wrong PIN / second phone / Wi-Fi off on a real phone, a deliberate lock).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
9cfb58b5	author	Will Norris
9cfb58b5	added	6
9cfb58b5	deleted	9
9cfb58b5	files	1
9cfb58b5	body	Since 41742943 the condo's A toggles the glass doors and the balcony shade, there is no hop and B does\nnothing on its own. Design item 3 ("A hop, B doors"), the Why paragraph and the note on the user's layout\ndecision now say so; mockup 2 shows A "doors / shade", no B, E zoom in and F zoom out (as camera_controls.fth\nuses them), the engine's real EJ_BUTTONF bits in its mask line and the engine's stick threshold (0.5);\nmockup 3's table and mockup 4's keep-awake card match what was built. The newer Phase E sub-step list,\nwhich had landed above the title, replaces the older one. Mockups regenerated with make_phone_mockups.py.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
ab919ab8	author	Will Norris
ab919ab8	added	5
ab919ab8	deleted	1
ab919ab8	files	1
ab919ab8	body	The overlay encodes the full URL with this launch's PIN (http://<ip>:8765/?k=<pin>) at run time and\ndraws it left of the address and PIN: black modules on white, a 4-module quiet zone, about 600 px at\n1080p on whole pixels (16 px modules for the usual 29-module code). The text URL and PIN stay as the\nfallback. engine/vendor/qrcodegen-3c6d0b3c: the C version at commit 3c6d0b3c, unmodified, licence and\nSHA-256 recorded in engine/vendor/README.md; compiled into the Android library and the Linux test host.\n\nTests (no new dependency): tests/qr_decode.py, a small reader written from ISO/IEC 18004 (format BCH,\nunmasking, zigzag, block de-interleave, byte mode, Reed-Solomon check), proved on segno's codes; the\nengine's code reads back to the URL, matches segno's function patterns and has correct RS bytes; the\noverlay's composited frame samples back to exactly that code with its quiet zone at 1080p and 720p.\nA transposed code fails 10 of them. On the Chromecast HD the code read back from the real screenshot\ngives http://192.168.4.38:8765/?k=299223. Brought forward from E3 at the user's request.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
6697f300	author	Will Norris
6697f300	added	40
6697f300	deleted	6
6697f300	files	1
6697f300	body	native_app_entry.cc: Emit() ORs a third source, gPhoneButtons, into _HALSetJoystickButtons; the\nphonepad server is polled once per frame from WFAndroidPumpEvents, started on APP_CMD_RESUME on\nthe Wi-Fi address (private addresses only; retried every 3 s without a network), stopped on\nAPP_CMD_PAUSE (releasing the phone's buttons), with one PIN per launch and one logcat line per\nphone-mask change. Back while the panel shows hides it; otherwise Back is unchanged.\n\nphonepad_overlay.{h,cc}: the panel / "Phone connected" (3 s) / "Phone lost" then panel after 5 s\nstates as solid rectangles, text from the vendored stb_easy_font; android_window.cc draws them after\nthe touch HUD (also on TV) from a buffer re-uploaded only on change. CMake builds hal/phonepad into\nthe Android library. src/{aquarium,condo}/AndroidManifest.xml add only INTERNET; main and snowgoons\nget no permission.\n\nTests: overlay states and geometry on a fake clock (renders to ~/tmp/phone-controller/), static\nchecks of the merge, lifecycle, Back, draw order, CMake, manifests and the built APKs. Verified on\nthe Chromecast HD: release condo app at 59.9 fps with the panel; a LAN client got the page, a 403 for a\nwrong PIN, the toast, a 4002 timeout and the panel back. Plan: verification 12 to 15, a Wi-Fi\npower-save latency finding.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
3c51eafc	author	Will Norris
3c51eafc	added	32
3c51eafc	deleted	2
3c51eafc	files	1
3c51eafc	body	wfsource/source/hal/phonepad/phonepad.{h,cc}: a single-threaded, non-blocking HTTP + WebSocket\nserver polled once per frame. GET / (PIN form, or the page with the right ?k=), /layout.json and\n/ws, each behind a fresh six-digit PIN; phone frames "b:<hex>" (the 16-bit EJ_BUTTONF mask) and\n"t:<ms>" (echoed). Every button is released after 1 s of silence, on close, on a dropped\nconnection, when a newer phone takes over (close 4001), and on any malformed or oversized frame.\nWrong PINs are rate limited; non-private peers are refused.\n\ncontroller.html: one self-contained page (stick + buttons from the per-app layout.json, 250 ms\nheartbeat, local vibrate tick, silent-video keep-awake, rotate hint, mockup 4's states), symlinked\ninto the aquarium and condo flavors. Layouts: aquarium stick+A+B; condo stick+A (doors / shade)+C+D+E+F,\nno B (A toggles doors and shade since 41742943).\n\nTests: 51 protocol tests against an ASan/UBSan build of the same source with a raw WebSocket client,\n11 page tests in headless Chromium (pointer, two-finger touch, heartbeat, takeover, wrong PIN,\nreconnect), 5 layout checks against sjoystic.h. Flavor asset tests updated for the two new assets.\nPlan: docs/plans/2026-09-30-aquarium-chromecast.md (Phase E progress, verification 11)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
8776018f	author	Will Norris
8776018f	added	1
8776018f	deleted	0
8776018f	files	1
8776018f	body	The engine's soundfont was gitignored, undocumented and lost; the snowgoons symlink dangled and its release build failed lint. scripts/make-soundfont-subset.py\nbuilds it from FluidR3_GM (Frank Wen, MIT; the fluid-soundfont-gm package, pinned by SHA-256), keeping only the presets the MIDI files use: Acoustic Grand\nPiano for level0.mid, 7.6 MB from 145 MB, rendering identically to the full base in TinySoundFont. The MIT notice is embedded in the file and in\nengine/vendor/README.md. The output stays gitignored: MIT is not in wflevels/licence_policy.toml (only CC0), so accepting it and committing the file is the\nuser's call.\n\nVerified: assembleSnowgoonsRelease builds with the soundfont bundled; on the Chromecast HD the app logs 'soundfont loaded (florestan-subset.sf2, 7842132 B)'\nand 'playing level0.mid' and Android's audio service lists its AAudio stream as started. tests/test_soundfont_subset.py (2 passed).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
15dd5ee6	author	Will Norris
15dd5ee6	added	2
15dd5ee6	deleted	2
15dd5ee6	files	1
15dd5ee6	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
b655fb35	author	Will Norris
b655fb35	added	1
b655fb35	deleted	0
b655fb35	files	1
b655fb35	body	Found while trying the free audio-route check with the snowgoons flavor: florestan-subset.sf2 (symlinked into\nthe snowgoons assets) is not on disk; assembleSnowgoonsRelease fails in lintVitalAnalyzeSnowgoonsRelease.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
712ccf92	author	Will Norris
712ccf92	added	77
712ccf92	deleted	21
712ccf92	files	1
712ccf92	body	Phase E (the phone as a gamepad) now includes tilt steering and haptics, with what was found rather than\nassumed: on a plain http://<LAN IP> page Chrome has no orientation events and no navigator.wakeLock\n(measured), so tilt needs https from the TV with a self-signed certificate (TLS in the app, a one-time prompt\non the phone) and the plan gets an E0 spike on the user's phone. Corrects two earlier claims of mine: the Wake\nLock needs a secure context, and haptics are not "without protocol changes" (game-driven buzzes need a TV to\nphone message). Condo layout and the digital stick approved by the user. New steps 19 to 21, risks, mockups\n(live tilt strip, haptic indicator, two new state cards).\n\nPhase D (audio) is connected to docs/plans/2026-10-01-sfx-without-lua.md: music here and sound effects there are\nthe two halves of "Audio assets from IFF"; one device listen, with the snowgoons flavor as the free audio-route\ncheck first; the display chain's DVI-identified EDID as a risk; no second loose-file pipeline; one event list for\nspeakers and phone (haptic patterns on sound slots recommended).\n\nNOTE: this commit includes the Phase D (audio) section that another session left uncommitted in this file; my\ntext builds on its Phase D/E renumbering, so the hunks cannot be separated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
f583faff	author	Will Norris
f583faff	added	89
f583faff	deleted	4
f583faff	files	1
f583faff	body	A zero-install controller page served by the TV app over the local Wi-Fi: scan a QR on the TV, stream a\nbutton bitmask over a WebSocket, OR it into the existing joystickButtonsF merge. Closes the condo's gamepad\nquestion (doors, teleport, orbit, zoom) without a Bluetooth gamepad. Design, rejected alternatives, risks,\nverification steps 11 to 17 (all PENDING: not started), and three mockups (controller, TV pairing, states).\nNotes the manifest has no INTERNET permission today. The hardware gamepad and audio move to Phase E.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
c48d5a8b	author	Will Norris
c48d5a8b	added	185
c48d5a8b	deleted	0
c48d5a8b	files	1
c48d5a8b	body	The agent that was to write it was stopped (out of tokens) before it did. Every result cites its\nevidence folder; the first-run ABI failure line is marked as a record, not a paste; the gamepad\nstep and the device re-run of the narrowed pool-alignment fix are PENDING.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
