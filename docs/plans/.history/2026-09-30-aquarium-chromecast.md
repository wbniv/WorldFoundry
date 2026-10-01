| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/8776018f) | Soundfont: a reproducible recipe (task soundfont) replaces the never-committed florestan-subset.sf2 |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/15dd5ee6) | Aquarium-Chromecast plan: snowgoons is silent on Android (no soundfont, Q*bert sfx not found), so it is not the audio-route check; the display chain does advertise audio, the monitor just has no speakers |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/b655fb35) | Aquarium-Chromecast plan, Phase D: the soundfont is gitignored and absent, so snowgoons' release build fails lint and no flavor can play MIDI music yet |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/712ccf92) | Aquarium-Chromecast plan: tilt steering and haptics in Phase E; Phase D (audio) tied to the SFX plan |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/f583faff) | Aquarium-Chromecast plan: add Phase D, the phone as a gamepad (web controller over the LAN), with mockups |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/c48d5a8b) | Write the missing aquarium-on-Chromecast plan (four docs linked to it): rebuilt from the commits and device-run evidence |

<!--history-meta v1
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
