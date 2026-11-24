# Nine-room Parmenides: Cast1 walkthrough video

## Current status

The desktop recording below is retained as an input-route reference. The requested
deliverable is a Cast1 video that starts on the opening Temple sheet, walks every
gate without a debug teleport, shows the completed Being card, closes it, returns
to the Temple, and pans around the Temple before ending. The Cast1 capture is in
progress; the earlier Cast1 attempt began after the opening sheet and does not
satisfy this plan.

## Goal

Record one playthrough of the unmerged nine-room chapter candidate on Cast1,
from a fresh launch through the completed ending, Temple return, and final pan.
Use ordinary directional and Select input to traverse Love, Reason, Truth, God,
and the Being ending. Do not
set player position, realm, progress, or story mailboxes. The level's own
doorway transitions are part of gameplay and are permitted.

## Capture method

1. Freeze the candidate level and runtime hashes before launch. Record the
   nine-room `RM0`–`RM8` table of contents and the authored all-active room
   render scope in the receipt.
2. Start a fresh process with no saved progress and begin recording while the
   opening sheet is still visible. Keep the coordinator-owned recording session
   active through the completion sheet, Temple return, and pan. The coordinator
   rotates screenrecord files after at most 120 seconds; preserve every raw part
   and record each rotation gap in the receipt.
3. Use directional input for every approach. Use Select to open and advance
   sheets and to cross the authored doorways. Observe native position, focus,
   realm, and progress mailboxes only; readback must never change gameplay.
4. Log each button hold with its start and end time relative to the recording,
   plus the observed area and position. Stop the run if a debug transform or
   progress write occurs. Do not splice another attempt into the video.
5. Verify the video decodes, the opening and completion frames and final Temple
   pan are present, the route reaches the completed Being ending, and input covers the
   entire run. Save video, input log, runtime hashes, and verification receipt
   together under `docs/diagnostics/parmenides/` or an explicitly linked
   temporary evidence directory.

The earlier desktop reference used the native runtime and its debug bridge for
input and readback only. It is not the requested final Cast1 deliverable.

The former 120-second job cap was set by the coordinator request schema. The
reviewed long-record change raises the job cap to 360 seconds and rotates
Android `screenrecord` processes at 120 seconds each, keeping the same device
lease throughout. The updated downloader's final deployment is blocked on local
administrator authentication; two deployment prompts timed out without changing
the installed service.

## Minimal route

| Order | Area | Required action | Expected transition |
|---:|---|---|---|
| 1 | Temple | Read the opening, walk to the Love gate, Select | Love street |
| 2 | Love | Read First Love, Starlet, Advice Column; choose Being | Temple |
| 3 | Temple | Walk to the Reason gate, Select | Reason grove |
| 4 | Reason | Read White Self, Weather / Why?, Wild Self, Younger Self; choose Being | Temple |
| 5 | Temple | Walk to the Truth gate, Select | Truth court |
| 6 | Truth | Read Prosecutor, Defence, Student, Facts, Interpretations, Presentation; choose Being | Temple |
| 7 | Temple | Walk to the Goddess gate, Select | God ascent |
| 8 | God | Read Young Man, Poster, Holy Man, Icon, Question; choose Being | Temple |
| 9 | Temple | Read the return, walk to the Being exit, confirm, finish the source | Completed Being ending |
| 10 | Temple | Close the final card, walk into the Temple, pan left and hold the view | Final Temple clip |

## Desktop reference recording and input timeline

The continuous [walkthrough video](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/walkthrough.mp4)
lasts **05:31.450** at 1280 × 720, 20 fps, with no audio track. Times below are relative to its first encoded frame.
Directional rows group short holds within one walked leg; sheet rows group Select
presses while reading. The [401 individual button holds](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/button-timeline.csv)
list each press and release time, button, realm, and start/end position.
The first 9.3 seconds include the recorder starting and the chapter launch.

| Video time | Area / position | Button press or hold | Observed result |
|---|---|---|---|
| 00:09.301–00:10.814 | Temple: sheet 1 | Select × 1 | sheet closed 1.0 |
| 00:10.814–00:18.067 | Temple: Love gate | Up × 6 | Reached focus 1 |
| 00:18.067 | Temple: Love gate | Select | Interacted at (0.0, 6.7) |
| 00:19.641–00:24.306 | Love: First Love | Up × 3, Left × 1 | Reached focus 4 |
| 00:24.306 | Love: First Love | Select | Interacted at (96.4, 1.2) |
| 00:25.200–00:26.006 | Love: sheet 2 | Select × 1 | sheet closed 2.0 |
| 00:26.007–00:37.053 | Love: Starlet | Up × 5, Right × 5 | Reached focus 5 |
| 00:37.053 | Love: Starlet | Select | Interacted at (103.6, 3.9) |
| 00:37.696–00:39.188 | Love: sheet 5 | Select × 3 | sheet closed 5.0 |
| 00:39.189–01:17.922 | Love: Advice Column | Up × 20, Right × 20 | Reached focus 6 |
| 01:17.923 | Love: Advice Column | Select | Interacted at (100.7, 8.3) |
| 01:18.296–01:19.024 | Love: sheet 13 | Select × 1 | sheet closed 13.0 |
| 01:19.024–01:29.271 | Love: Love Being gate | Up × 9, Right × 5 | Reached focus 7 |
| 01:29.272 | Love: Love Being gate | Select | Interacted at (94.5, 11.4) |
| 01:29.904–01:31.462 | Love: sheet 14 | Select × 2 | sheet closed 14.0 |
| 01:31.462–01:39.514 | Temple: Reason gate | Up × 7, Left × 1, Right × 1 | Reached focus 3 |
| 01:39.514 | Temple: Reason gate | Select | Interacted at (7.5, 7.5) |
| 01:40.449–01:43.706 | Reason: White Self | Up × 6, Left × 1 | Reached focus 11 |
| 01:43.706 | Reason: White Self | Select | Interacted at (196.7, 0.4) |
| 01:44.133–01:45.930 | Reason: sheet 20 | Select × 4 | sheet closed 20.0 |
| 01:45.930–01:52.157 | Reason: Weather apparatus | Up × 5, Left × 2, Right × 2 | Reached focus 12 |
| 01:52.158 | Reason: Weather apparatus | Select | Interacted at (199.8, 2.1) |
| 01:52.680–01:53.831 | Reason: sheet 31 | Select × 2 | sheet closed 31.0 |
| 01:53.832–01:59.355 | Reason: Wild Self | Up × 8, Left × 2, Right × 1 | Reached focus 13 |
| 01:59.356 | Reason: Wild Self | Select | Interacted at (203.9, 5.7) |
| 01:59.844–02:00.791 | Reason: sheet 33 | Select × 2 | sheet closed 33.0 |
| 02:00.791–02:03.574 | Reason: Younger Self | Up × 4, Left × 1 | Reached focus 14 |
| 02:03.574 | Reason: Younger Self | Select | Interacted at (200.6, 10.4) |
| 02:04.028–02:04.700 | Reason: sheet 38 | Select × 1 | sheet closed 38.0 |
| 02:04.700–02:07.882 | Reason: Reason Being gate | Up × 5, Left × 1 | Reached focus 15 |
| 02:07.882 | Reason: Reason Being gate | Select | Interacted at (194.1, 13.4) |
| 02:08.276–02:11.380 | Reason: sheet 40 | Select × 5 | sheet closed 40.0 |
| 02:11.380–02:19.378 | Temple: Truth gate | Up × 8, Left × 1, Right × 1 | Reached focus 10 |
| 02:19.379 | Temple: Truth gate | Select | Interacted at (-6.9, 7.3) |
| 02:20.529–02:21.413 | Truth: sheet 61 | Select × 1 | sheet closed 61.0 |
| 02:21.413–02:26.333 | Truth: Prosecutor | Up × 4, Left × 2 | Reached focus 18 |
| 02:26.333 | Truth: Prosecutor | Select | Interacted at (294.5, 0.4) |
| 02:26.819–02:29.055 | Truth: sheet 62 | Select × 6 | sheet closed 62.0 |
| 02:29.055–02:39.384 | Truth: Defence | Up × 8, Right × 5 | Reached focus 19 |
| 02:39.384 | Truth: Defence | Select | Interacted at (305.3, 1.2) |
| 02:39.962–02:41.751 | Truth: sheet 78 | Select × 4 | sheet closed 78.0 |
| 02:41.751–02:54.689 | Truth: Student | Up × 9, Left × 6 | Reached focus 20 |
| 02:54.691 | Truth: Student | Select | Interacted at (300.7, 6.0) |
| 02:55.208–02:55.909 | Truth: sheet 87 | Select × 1 | sheet closed 87.0 |
| 02:55.909–02:58.417 | Truth: Facts | Up × 3, Right × 1 | Reached focus 21 |
| 02:58.417 | Truth: Facts | Select | Interacted at (295.0, 6.4) |
| 02:58.904–02:59.577 | Truth: sheet 90 | Select × 1 | sheet closed 90.0 |
| 02:59.577–03:11.965 | Truth: Interpretations | Up × 7, Right × 5 | Reached focus 22 |
| 03:11.966 | Truth: Interpretations | Select | Interacted at (304.9, 7.1) |
| 03:12.359–03:13.006 | Truth: sheet 91 | Select × 1 | sheet closed 91.0 |
| 03:13.006–03:24.916 | Truth: Presentation | Up × 7, Left × 7 | Reached focus 23 |
| 03:24.916 | Truth: Presentation | Select | Interacted at (300.3, 12.2) |
| 03:25.312–03:25.955 | Truth: sheet 92 | Select × 1 | sheet closed 92.0 |
| 03:25.955–03:34.284 | Truth: Truth Being gate | Up × 7, Right × 5 | Reached focus 24 |
| 03:34.284 | Truth: Truth Being gate | Select | Interacted at (293.0, 16.3) |
| 03:34.649–03:37.045 | Truth: sheet 93 | Select × 3 | sheet closed 93.0 |
| 03:37.045–03:51.736 | Temple: Goddess gate | Up × 9, Right × 7 | Reached focus 25 |
| 03:51.736 | Temple: Goddess gate | Select | Interacted at (0.6, -8.4) |
| 03:52.434–03:53.289 | God: sheet 123 | Select × 1 | sheet closed 123.0 |
| 03:53.289–03:56.638 | God: Young Man | Up × 4 | Reached focus 28 |
| 03:56.638 | God: Young Man | Select | Interacted at (400.0, -0.2) |
| 03:57.365–03:59.631 | God: sheet 124 | Select × 6 | sheet closed 124.0 |
| 03:59.632–04:02.907 | God: Poster | Up × 3, Left × 1 | Reached focus 29 |
| 04:02.908 | God: Poster | Select | Interacted at (397.0, 5.6) |
| 04:03.572–04:04.268 | God: sheet 146 | Select × 1 | sheet closed 146.0 |
| 04:04.268–04:26.296 | God: Holy Man | Up × 27, Right × 1 | Reached focus 30 |
| 04:26.296 | God: Holy Man | Select | Interacted at (399.4, 11.6) |
| 04:26.992–04:28.325 | God: sheet 138 | Select × 3 | sheet closed 138.0 |
| 04:28.325–04:32.599 | God: Icon | Up × 4, Left × 1, Right × 1 | Reached focus 31 |
| 04:32.601 | God: Icon | Select | Interacted at (403.0, 17.5) |
| 04:33.240–04:33.974 | God: sheet 147 | Select × 1 | sheet closed 147.0 |
| 04:33.974–04:40.691 | God: Question | Up × 5, Left × 2 | Reached focus 32 |
| 04:40.692 | God: Question | Select | Interacted at (397.0, 23.2) |
| 04:41.328–04:42.056 | God: sheet 148 | Select × 1 | sheet closed 148.0 |
| 04:42.056–05:03.076 | God: God Being gate | Up × 27, Left × 1, Right × 1 | Reached focus 33 |
| 05:03.077 | God: God Being gate | Select | Interacted at (396.2, 32.0) |
| 05:03.657–05:06.647 | God: sheet 150 | Select × 3 | sheet closed 150.0 |
| 05:06.647–05:23.197 | Temple: Final Being gate | Up × 10, Left × 5 | Reached focus 36 |
| 05:23.197 | Temple: Final Being gate | Select | Interacted at (-6.5, -11.4) |
| 05:23.770–05:25.232 | Temple: sheet 205 | Select × 2 | completed Being ending visible |

## Recording and verification

- [Video](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/walkthrough.mp4): H.264, 6627 frames, 82,067,256 bytes; SHA-256 `21cb5c49c20538d6596a3838487743dd8acf79fe5f99cfe39aa419db9d37aae2`.
- [Verification receipt](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/verification.json), [full input events](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/events.json), and [input driver](../diagnostics/parmenides/nine-room-walkthrough-2026-10-12/input-driver.py) are retained beside it. The video decoded with ffmpeg; sampled opening, Truth, and completion frames were inspected.
- The completion sheet appears at **05:25.232** in realm 5. The run stops after holding that sheet for three seconds. The candidate CD SHA-256 is `75d34e42389b3a8043cbf6c49de8cf8a70c80a9b3464d580828cf2f2178d104e`; desktop runtime SHA-256 is `b55693bc26147f3243332e21cd704cc0c1e60c4223597a`.
- The input driver uses `inject_input` and read-only mailbox watches. Its source contains no `set_mailbox`, `scene:set_transform`, or `fy-teleport` call. Game-authored doorway transitions internally reposition the player, as specified above. No Chromecast claim is made; this is a desktop capture while cast1 is unavailable.

## Desktop reference acceptance

- [x] One continuous, decodable video from fresh intro to completed Being ending.
- [x] No harness teleport, position write, realm write, or progress write.
- [x] Every area transition follows a player-reached doorway and Select press in the video.
- [x] Timestamp and button table derives from the input log and video capture epoch.
- [x] Nine-room candidate and runtime hashes are recorded; main remains untouched pending review.

## Cast1 acceptance

- [ ] Opening Temple sheet appears before the first input.
- [ ] One coordinator-owned session records the walk through all four areas and the Being ending.
- [ ] Final card is closed and the player returns to the Temple for a visible pan.
- [ ] Every raw video part is retained; decoded joined video and segment gaps are documented.
- [ ] Cast1 video has its own timestamp and button-press table.
