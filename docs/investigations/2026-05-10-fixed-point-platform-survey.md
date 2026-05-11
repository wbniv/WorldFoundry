---
title: Fixed-point vs floating-point — platform survey and WF removal cost
date: 2026-05-10
status: investigation
---

# Fixed-point vs floating-point: platform survey and WF removal cost

WF is built around a `Scalar` abstraction (`wfsource/source/math/scalar.hp`) that compiles three ways:

- `SCALAR_TYPE_FIXED` — 16.16 fixed-point (PS1-era target)
- `SCALAR_TYPE_FLOAT` — IEEE 754 single
- `SCALAR_TYPE_DOUBLE` — IEEE 754 double

The Linux build currently uses `SCALAR_TYPE_FLOAT` (`engine/build_game.sh:128`). The fixed-point path still compiles and gates code in ~10 `.cc/.hp` files. This document answers: what FPU support exists across mainline platforms, what we lose by dropping fixed point, and what removal looks like in practice.

## 1. Floating-point support across mainline computers and consoles

### Desktop CPUs

| Era | Family | FPU |
|---|---|---|
| 1980s | x86 (8086–80386) | optional 8087/80287/80387 coprocessor |
| 1989+ | 80486DX | on-die x87 (DX); 486SX had none |
| 1993+ | Pentium and later | x87 + later SSE/SSE2/AVX |
| 1985+ | 68020 + 68881/2 | optional coprocessor |
| 1990+ | 68040/68060 | integrated (LC variants lacked it) |
| 1995+ | PowerPC | integrated |
| 2005+ | x86-64 | SSE2 mandatory (scalar FP via SSE) |
| ARM desktop (Apple Silicon, Windows-on-ARM) | NEON + VFP mandatory in AArch64 |

By 1995 every shipping desktop CPU had hardware floating point. Today every desktop / laptop / phone has both scalar and SIMD FP.

### Home consoles (last-without-FPU bolded)

| Console | Year | CPU | FPU? |
|---|---|---|---|
| Atari 2600 | 1977 | 6507 | no |
| NES | 1983 | 6502 | no |
| Sega Master System | 1985 | Z80 | no |
| Genesis / Mega Drive | 1988 | 68000 | no |
| TurboGrafx-16 | 1987 | HuC6280 | no |
| SNES | 1990 | 65C816 | no |
| Neo Geo | 1990 | 68000 | no |
| 3DO | 1993 | ARM60 | no |
| **Atari Jaguar** | 1993 | 68000 + Tom/Jerry | **no** (last Atari home console) |
| **Sega Saturn** | 1994 | dual SH-2 | **no** (last Sega home console without FPU) |
| **Sony PlayStation** | 1994 | R3000A + GTE | **no on CPU** — GTE is a fixed-point geometry coprocessor (last Sony home console without FPU) |
| **Nintendo 64** predecessor: **SNES** | — | — | — |
| Nintendo 64 | 1996 | MIPS R4300i | yes (paired-single-style FPU) |
| Dreamcast | 1998 | SH-4 | yes (single + SIMD FV4) |
| PS2 | 2000 | Emotion Engine + VU0/VU1 | yes |
| GameCube | 2001 | Gekko (PowerPC) | yes |
| Xbox | 2001 | x86 (Coppermine) | yes |
| Everything since (Wii, 360, PS3, Wii U, PS4, XBO, Switch, PS5, XSX, Switch 2) | — | — | yes |

**Last home console without FPU per lineage:**

- **Sony** — PlayStation 1 (1994). The GTE coprocessor is fixed-point, but the R3000A CPU itself has no FPU.
- **Sega** — Saturn (1994).
- **Nintendo** — SNES (1990). N64 added an FPU.
- **Atari** — Jaguar (1993). Atari exited the console market afterward.
- **Microsoft** — never shipped one; the Xbox debuted with x86 + x87/SSE.

### Handhelds

| Handheld | Year | CPU | FPU? |
|---|---|---|---|
| Game Boy | 1989 | Sharp LR35902 | no |
| Game Boy Color | 1998 | LR35902 | no |
| **Game Boy Advance** | 2001 | ARM7TDMI | **no** |
| **Nintendo DS** | 2004 | ARM9 + ARM7 | **no** (last Nintendo handheld without FPU) |
| PSP | 2004 | MIPS Allegrex + VFPU | yes |
| 3DS | 2011 | ARM11 (VFPv2) | yes |
| PS Vita | 2011 | Cortex-A9 (VFPv3 + NEON) | yes |
| Switch / Switch 2 | 2017 / 2024 | ARM Cortex-A / Ampere | yes |
| Steam Deck | 2022 | x86-64 (Zen 2) | yes |

**Last handheld without FPU per lineage:**

- **Nintendo** — DS (2004). 3DS added VFPv2.
- **Sony** — never shipped one; PSP had a VFPU from launch.
- **Sega Game Gear / Atari Lynx / NGPC** — none had FPUs, all defunct lineages.

## 2. Embedded SoC and MCU floating-point

Floating-point coverage on small parts is much more uneven than on mainline platforms. Rough survey:

### No FPU (software float only)

- **AVR 8-bit** — every Arduino classic (Uno, Nano, Mega, Leonardo, Micro). Float costs ~thousands of cycles per op.
- **PIC8/PIC16/PIC18, MSP430** — entire lineage.
- **Cortex-M0 / M0+** — Raspberry Pi Pico (RP2040), STM32 F0/L0/G0, SAMD21 (Arduino Zero), nRF51.
- **Cortex-M3** — STM32 F1/F2/L1, SAM3X8E (Arduino Due), nRF52810.
- **ESP8266** (Tensilica L106) — no FPU.
- **ESP32-C3 / C2 / C6 / H2** — RISC-V cores without hardware FP.
- **GBA/DS retro targets** (ARM7TDMI, ARM9) — same situation, just for hobbyist ports.

### Hardware single-precision FPU

- **Cortex-M4F** — STM32 F3/F4/L4, nRF52832/40, SAMD51, RP2350 (M33F).
- **Cortex-M7** — STM32 F7/H7, Teensy 4.x (IMXRT1062), portenta.
- **ESP32 (LX6), ESP32-S2, ESP32-S3** — single-precision FPU; doubles are software.
- **RISC-V with `F` extension** — ESP32-P4, BL808, K210, JH7110 (VisionFive 2).
- **Most Cortex-A class SoCs** (Raspberry Pi 3/4/5, Allwinner, Rockchip, Jetson, BeagleBone) — full NEON + VFP.

### Hardware double-precision FPU

Almost exclusively Cortex-A (Linux-capable) and high-end Cortex-M7 with `-D` variant. Doubles on Cortex-M4F and ESP32 are emulated.

**Rule of thumb:** anything that runs Linux has full FP; anything you flash a `.hex` to is a coin-flip; anything 8-bit or sub-Cortex-M4 has none.

## 3. What platforms does keeping fixed-point support enable for WF?

The interesting question isn't "are these reachable in theory" but "is fixed-point support load-bearing for them." The categories:

**Genuinely require fixed-point for usable performance** — and how the RAM budget shakes out (PS1 reference: 2 MB main + 1 MB VRAM + 512 KB sound):

- **AVR Arduinos** (Uno: 2 KB SRAM, Mega: 8 KB). RAM disqualifies regardless of FP.
- **SAMD21** (Arduino Zero): 32 KB SRAM, no external RAM bus. Disqualified.
- **RP2040** (Pi Pico, Cortex-M0+): 264 KB SRAM, no PSRAM support. Doesn't fit 2 MB.
- **ESP32-C3 / C6** (RISC-V no-F): 400–512 KB SRAM, no PSRAM. Doesn't fit.
- **RP2350-without-FPU** (Cortex-M33, FPU is optional): 520 KB SRAM **+ external PSRAM** over QSPI → 2 MB+ reachable. **This is the one genuine case where fixed-point support would unlock a platform that has enough RAM.** Configurations with the FPU enabled obviously prefer float.

For reference, MCUs with enough RAM *and* a hardware FPU (no fixed-point needed):

- **ESP32-S3**: 512 KB SRAM + up to 8 MB octal PSRAM, single-precision FPU. Fits.
- **Teensy 4.x** (Cortex-M7): 1 MB SRAM + optional 8 MB PSRAM, single + double FPU. Fits.

The original WF target was PS1 (2 MB, no CPU FPU, GTE coprocessor for fixed-point geometry). That target is gone. Of today's small-MCU landscape, only RP2350-no-FPU is a realistic "fixed-point support unlocks this for us" candidate, and even then someone has to write the GPU/audio shim.

**Helped by fixed-point but not blocked:**

- ESP32-S3 with PSRAM has a single FPU; doubles are slow, singles are fine. WF would use singles. Fixed-point not needed.
- Cortex-M7 boards (Teensy 4, Portenta H7) have FPUs. Not needed.
- Old retro targets (PS1, Saturn, GBA, DS) — these are the *original* reason fixed-point exists, and they remain the only realistic platforms where dropping fixed-point removes meaningful capability.

**Not helped at all (already have FPUs):**

- Every console from N64 / Dreamcast forward.
- Every PSP/3DS/Vita/Switch/Steam Deck.
- Every desktop, laptop, phone, tablet, Pi, Jetson, modern smart TV.

**Conclusion:** in 2026, keeping `SCALAR_TYPE_FIXED` is essentially a *retro-target option* — PS1/Saturn/GBA/DS homebrew ports. It is not a gate for any modern shipping platform.

## 4. Removing fixed-point from WF — cost survey

### What's there now

- `wfsource/source/math/scalar.hp` — defines `Scalar` as fixed or float behind macros.
- `wfsource/source/math/linux/scalar.hpi` + `scalar.cc` — fixed-point inline implementations and assembly fallbacks.
- 16.16 internal representation; `SCALAR_ONE_LS = 1<<16`.
- ~10 `.cc/.hp` files contain `#ifdef SCALAR_TYPE_FIXED` branches (scalar, vector2, vector3, matrix34, angle, level.cc, main.cc, mathtest).
- `floatscalar.hpi` already exists as the float counterpart.
- `Angle` stores 16-bit revolutions and converts via `Scalar(0, _value)` — angle.hpi has fixed-only inlines that vanish under float builds.

### What removing it gains

- Delete ~200 lines of platform asm in `scalar.cc` and dead branches across `vector2.cc`, `vector3.cc`, `matrix34.hpi`, `mathtest.cc`, `level.cc`, `main.cc`.
- One fewer build axis (current matrix already only uses float on Linux/Android/iOS — fixed-point is no longer exercised by CI).
- Removes a class of latent bugs from overflow in 16.16 arithmetic that no shipping target sees.
- `Scalar` becomes a thin typedef / wrapper around `float`. Eventually it can be deleted outright and replaced with `float`, but that's a much bigger refactor.

### What removing it costs

- Loses the ability to retarget PS1/Saturn/GBA/DS without writing a fixed-point math layer from scratch.
- The fixed-point `Angle` representation (16-bit revolutions stored as `uint16`) is *also* the on-disk and on-the-wire representation. That has to stay regardless of `Scalar`'s internal type.
- Any oracle-byte-identical test that round-trips a level through fixed-point Scalar arithmetic would need to be re-baselined.

### Storage: on-disk fixed-point is a separate question

The Scalar runtime type and the .iff on-disk representation are independent decisions. Today:

- Mailboxes are fixed-point on real target, float on PC dev (`project_mailboxes_fixed_point` memory).
- Angles are revolutions in `uint16` — already a fixed-point format on disk and intentional.
> [!IMPORTANT]
> `Vector3` fields in OAS/asset chunks are stored as `Scalar` payload, which under `SCALAR_TYPE_FLOAT` is a 32-bit IEEE float — not the original fixed-point on-disk format. So WF on PC has already silently moved away from the PS1-era 16.16 disk encoding; the disk layout drifted with the runtime type. Anyone reading a current PC-built `cd.iff` expecting 16.16 in those fields will get floats instead.

If we wanted to recover disk space (and re-enable fixed-point disk encoding without bringing back fixed-point runtime), the path is:

1. Define a `Scalar16_16` storage type for the iff/oad layer.
2. Convert at load time only — runtime `Scalar` remains `float`.
3. Limit it to fields where 16.16 is sufficient precision (positions in level units, scale, time). Floats stay for anything precision-critical (matrices after concatenation, quat components, normalized vectors).

This is a level-compression project, not a math-library project. It can be deferred and considered independently from "delete `SCALAR_TYPE_FIXED`."

### Proposed phasing

1. **Remove `SCALAR_TYPE_FIXED` runtime build mode.** Delete the platform asm, simplify scalar.hp/hpi to "Scalar wraps float (or double)." Keep `SCALAR_TYPE_FLOAT`/`SCALAR_TYPE_DOUBLE` for now — doubles still useful on desktop for testing precision regressions.
2. **Collapse the typedef.** Replace `Scalar` with `float` everywhere it's purely numeric; keep `Angle` as its own type because its on-disk encoding is a revolution-uint16.
3. **(Optional, later)** Add a `Scalar16_16` *storage* format for level chunks if disk-size testing shows that current float encoding is bloating cd.iff.

Step 1 is mechanical and safe; step 2 is a wide rename; step 3 is independent of the others.

## 5. Recommendation

Drop `SCALAR_TYPE_FIXED` as a runtime option. It guards code paths that are not exercised by any current or planned WF target (Linux desktop, Android, iOS — all have hardware FPUs). The platforms it would still enable are:

- Retro targets (PS1, Saturn, GBA, DS) — feasible RAM-wise (PS1 itself had 2 MB), but each needs its own GPU/audio shim, and that work dwarfs the math-layer cost either way.
- RP2350 with the FPU left off — the only modern MCU that *both* lacks an FPU *and* has enough RAM (via external PSRAM) to plausibly host the engine.

Neither is on any roadmap. Anyone seriously porting to one would be doing a much larger platform-bringup project, of which the math layer is a small part — and they can just as easily implement `Scalar` on top of a fixed-point library at that point, without us carrying the option in mainline.

Keep on-disk fixed-point as a *separate* level-file compression discussion. Removing the runtime mode does not preclude adding a fixed-point storage format later if level size becomes a real constraint.

## Sources

- ARM Cortex-M reference manuals — FPU presence per part: [ARM Cortex-M comparison](https://developer.arm.com/Processors/Cortex-M)
- Espressif chip series comparison — [ESP product selector](https://products.espressif.com/)
- Console CPU specs cross-referenced against [Copetti's "Architecture of Consoles"](https://www.copetti.org/writings/consoles/) series for SNES, PS1, Saturn, N64, Dreamcast, PS2, GameCube, GBA, DS, 3DS, Vita.
- PlayStation GTE as a fixed-point geometry coprocessor (not a general FPU): [PS1 architecture writeup](https://www.copetti.org/writings/consoles/playstation/).
