# Coordinator feature request: scripted touchscreen gameplay

**Requested 2026-11-05.** Add coordinator-owned, repeatable touch gameplay on
phones and tablets. Reef acceptance currently needs the boxfish steered near
animals, held still, and moved away while recording their reactions. The Pixel
8 Pro is enrolled and works for install and idle profiling, but a profile
recipe with `input_script` was refused: “Owned timed input requires a TV
profile with held-key support.” The Lenovo tablet is also a target when its
own capabilities are verified. The Chromecasts are unavailable until further
notice; do not require them as controllers or as a workaround.

## Required user outcome

From one coordinator-owned job, launch a frozen APK, capture an initial
frame, press and continuously hold a specified point on the in-app virtual
joystick, move or release it on a timed schedule, capture named checkpoints,
and record video. Support an uninterrupted touch-down/move/up sequence,
including stationary holds and multi-touch for simultaneous virtual buttons.
A 10–15 second joystick hold must be a continuous contact, not a series of
taps or independent swipes. Phone and tablet support must be admitted per
verified device capability; do not infer it from Android version or model.

Scripts must describe coordinates in a documented orientation-aware frame,
with an explicit captured-frame size and display/rotation identity. Reject a
stale or changed frame before applying its input; either provide a safe
recalibration step or fail with a clear typed outcome. Define the mapping for
system bars, cutouts, letterboxing and app content, and make timing and
coordinate rounding deterministic. Named captures and video need timestamps
that correlate with each input edge, held interval, device, frozen APK hash,
display geometry and run ID. Capture initial and final state and expose a
machine-readable timeline and verified evidence through the existing Task
and coordinator CLI workflows.

## Ownership, recovery and safety

Use the existing session, reservation, foreground-app and cleanup policies.
Never synthesize a PIN, unlock a device, dismiss security prompts or fall back
to raw ADB outside coordinator ownership. A locked or unavailable device
should wait and resume according to coordinator policy. Detect focus loss,
unexpected app exit, rotation, cancellation, helper death, transport loss and
deadline expiry. Release all active contacts on every exit; journal any
uncertain contact/release obligation and reconcile it before admitting another
input job. Do not report successful input merely because an ADB command was
accepted. Provide bounded operation, clear typed failures and a health result
that distinguishes verified cleanup from uncertainty. Protect personal
reservations and foreground playback under the existing policy.

## Suggested interface and acceptance

Extend the versioned recipe with touch-down, touch-move and touch-up steps
identified by contact ID, plus held contacts and named frame/video captures.
Keep existing TV key scripts compatible, validate the entire timeline and all
capabilities before admission, and enforce ordered balanced contacts, bounded
duration, contact count and coordinates. Allow a check or profile to use the
same touch script in one run and a recorded interactive session to perform
decision-driven input. The precise schema is for the coordinator agent to
choose and document; do not silently reinterpret existing TV key events.

Acceptance must include unit and fake-transport tests for invalid and
overlapping contacts, stale frames, rotation and focus changes, timeout,
cancel, disconnect, crashes, held-contact release and recovery; a balanced
multi-touch recording; evidence provenance; and preservation of existing TV
held-key behavior. On the Pixel, demonstrate a real virtual-joystick hold,
direction change and release in the reef, with recorded visible movement,
at least one animal reaction and no movement after release. Repeat the
equivalent on the Lenovo only after its own input capability is verified.
Retain before/after device state, cleanup, final foreground, hashes and
receipts; never mark acceptance passed from a simulator or an idle screenshot.

## Current workaround and limitation

World Foundry has queued near/far diagnostic builds for several reef animals,
which can compare reactions after the Pixel unlocks. Those builds place the
fish at a chosen starting location; they do not demonstrate steering or a
continuous touch and do not replace the requested feature. The latest reef
verification context is `WorldFoundry-wbniv/docs/diagnostics/reef-gameplay-verification-2026-11-05/README.md`.
