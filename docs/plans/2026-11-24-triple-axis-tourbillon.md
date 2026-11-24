# Triple-axis Tourbillon

Status: standalone implemented and PC-verified; open for Will's review. Chromecast, bundling and deployment wait for the current batch.

## Experience

Three concentric mechanical cages surround a small balance wheel on a watchmaker's pedestal. A luminous bead on the outer cage completes one lap each minute. A separate small dial displays local hours and minutes. Slotted cage bands, inset jewels, bridges, bearings, additional tilted inner rings and open spoked toothed wheels around the balance make the cages readable as three-dimensional moving parts. A slow travelling camera reveals their depth; camera drift can be switched off.

![High-fidelity visual target for the triple-axis tourbillon](2026-11-24-triple-axis-tourbillon/concept-mockup.png)

The mockup is a visual target, not an engine capture. Model the clock itself and keep the background unobtrusive; do not add the workshop tools or other objects in the illustration. The simulation makes no claim to model the gravity correction of a real escapement.

## Motion and time

```text
             outer cage: 60 seconds / revolution ── bead = seconds
                 ╭──────────────────────╮
                 │  middle cage: 120 s  │
                 │    ╭────────────╮    │
                 │    │ inner: 180 s│    │
                 │    │   balance   │    │
                 │    ╰────────────╯    │
                 ╰──────────────────────╯
                      [ hour : minute ]

      Each inner cage inherits the rotations of the cages surrounding it.
      Its own axis is perpendicular to its parent axis. Their phases return
      to the same alignment every 360 seconds. The balance oscillates faster.
```

```text
Local wall time ──┬── hour and minute phases ──> subdial hands
                 └── seconds and minute ─────> 60 / 120 / 180 s cage phases
                                                  └── outer bead: one lap/minute
```

## Build and verification

Create the mechanical model and standalone level in the main checkout with a normal pre-approved settings holder, camera drift and Show framerate. Render and compare it with the concept before review. Verify in the PC engine the hour and minute hands at 12:00 and 10:08:22, bead and cage motion, the 60-second rollover and six-minute alignment, as well as moving and still cameras. Finally open the standalone at the computer's local time for Will to review. Do not bundle or deploy until the batch is closed.

PC results: the engine's hands, bead, inherited cage rotations and camera pose matched the model at 10:08:22 and 12:00:00; the still-camera override held the view. A live 11:59:55 rollover showed all three cage phases crossing their six-minute alignment together without exiting. The [final PC capture](2026-11-24-triple-axis-tourbillon/pc-final.png) shows the current rendering with the background panel removed; the high-fidelity mockup remains an appearance target.

## Appendix: nighttime lamps, 2026‑11‑24

The hour subdial has marks rather than numerals. Two small warm lamps at the tops of the pedestal supports now turn on from 18:00 through 05:59 local time. They use prelit geometry, switched from the wall-clock hour on each update, and do not change the clock hands or the cage and bead motion.

**Before:** the earlier PC engine capture, before the night lamps; its camera and time differ from the after views.

![Before the night lamps, the original tourbillon.](2026-11-24-triple-axis-tourbillon/pc-final.png)

**After:** matched PC captures at 10:08:22 and 22:08:22 show the lamps off and on.

![After the change, the pedestal lamps are off at 10:08.](2026-11-24-triple-axis-tourbillon/day-night-sweep.png)

![After the change, the pedestal lamps are on at 22:08.](2026-11-24-triple-axis-tourbillon/night-night-sweep.png)

The standalone rebuilt; both PC captures passed the existing hand, cage, bead and camera checks. Verify the lamps and bead remain distinguishable along the full camera path, plus switching boundaries, time jumps and Chromecast readability and profiling. This change is not yet in the installed APK.
