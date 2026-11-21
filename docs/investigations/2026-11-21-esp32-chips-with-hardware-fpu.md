# ESP32 family: which chips have a hardware FPU, and what each one offers

**Date:** 2026-11-21
**Status:** Complete (research only; nothing is built or decided)
**Asked by:** Will, 2026‑11‑21: "i want to know which models of ESP32 support FP hardware, then for each of those, i want to know its specs (cpus/speed/memory/communication protocols supported (bluetooth ble, wifi, etc.)"

## Summary

- **Four Espressif chips have a hardware FPU:** the **ESP32**, **ESP32‑S3**, **ESP32‑H4** and **ESP32‑P4**. Seven others have none: S2, C2, C3, C5, C6, C61 and H2.
- **Every Espressif FPU is single-precision only.** `float` runs in hardware; `double` is emulated in software on all four.
- **Only two of the four have Wi-Fi.** The ESP32 and ESP32‑S3 do. The H4 has Bluetooth LE 5.4 and IEEE 802.15.4 (Thread, Zigbee) but no Wi-Fi. The P4 has **no radio at all**.
- **Memory differs by two orders of magnitude.** From 384 KB of on-chip SRAM (H4) to 768 KB plus 16 MB or 32 MB of in-package PSRAM (P4).
- **For World Foundry:** nothing here picks a chip. It does show that an engine level with megabytes of RAM regions cannot live in on-chip SRAM on any of them, so any port needs external or in-package PSRAM. See [what this means for World Foundry](#what-this-means-for-world-foundry).

## Why this was asked

The [Forth math words plan](../plans/2026-11-21-forth-trig-words.md) asks (D8, D9) whether ESP32 support would need fixed point again, and its first draft listed the FPU facts from memory. Will asked for them to be verified, then for a spec sheet for each chip that has an FPU. This report is that sheet. Its first finding corrects the plan's draft: it had left out the H4 and the P4 and the C5 and C61.

## Which chips have an FPU

The authority is Espressif's own developer-portal article, [Floating-Point Units on Espressif SoCs](https://developer.espressif.com/blog/2025/10/cores_with_fpu/) (October 2025). Its table:

| Core | FPU | Core | FPU |
|---|---|---|---|
| ESP32 | **yes** | ESP32‑C5 | no |
| ESP32‑S2 | no | ESP32‑C6 | no |
| ESP32‑S3 | **yes** | ESP32‑C61 | no |
| ESP32‑C2 | no | ESP32‑H2 | no |
| ESP32‑C3 | no | ESP32‑H4 | **yes** |
| | | ESP32‑P4 | **yes** |

The article also states that "for Espressif cores, all currently available FPUs support single-precision only", and that on a core without an FPU the `newlib` library does the arithmetic in software: correct IEEE 754, but slower.

**Not covered:** Espressif's product menu also lists the **ESP32‑S31**, **ESP32‑H21** and **ESP32‑E22**. The article predates or omits them, and I did not check their datasheets, so whether they have an FPU is unknown.

Cross-checks I made against the datasheets themselves:

| Chip | What the datasheet says |
|---|---|
| ESP32 | The CPU feature list includes "Support for Floating Point Unit" ([datasheet v5.3](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)) |
| ESP32‑S3 | "Single precision floating point unit (FPU)" ([datasheet v2.2](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)); the ESP-IDF [speed guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/performance/speed.html) adds that "double precision calculations are emulated in software and are very slow" |
| ESP32‑P4 | The two high-performance cores implement `RV32IMAFC` (the **F** is the single-precision FPU); the single low-power core implements `RV32IMAC` and has none ([datasheet v0.7](https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf)) |
| ESP32‑H4 | Not checked: the datasheet is not public (see [the H4 row](#esp32-h4)). It rests on the article alone |
| ESP32‑C6 | The [technical reference manual](https://www.espressif.com/sites/default/files/documentation/esp32-c6_technical_reference_manual_en.pdf) shows the single- and double-precision extension bits both 0, which agrees with the article |

## The four chips side by side

| | **ESP32** | **ESP32‑S3** | **ESP32‑H4** | **ESP32‑P4** |
|---|---|---|---|---|
| **CPU** | Xtensa LX6, single or dual core | Xtensa LX7, dual core, five-stage pipeline, 128-bit data bus with SIMD instructions | RISC-V, dual core, with DSP extensions | RISC-V: dual-core high-performance (HP) system plus single-core low-power (LP) system |
| **Clock** | up to 240 MHz | up to 240 MHz | up to 96 MHz | HP up to 400 MHz; LP up to 40 MHz |
| **CoreMark** (Espressif's figures) | 539.98 (1 core), 1079.96 (2 cores) at 240 MHz | 1329.92 (2 cores) at 240 MHz, 5.54 per MHz | not published | 6.92 per MHz (2 cores) |
| **FPU** | single-precision | single-precision | single-precision (article only) | single-precision on the HP cores; none on the LP core |
| **ROM** | 448 KB | 384 KB | 128 KB | 128 KB (HP) + 16 KB (LP) |
| **On-chip SRAM** | 520 KB + 16 KB in the RTC domain | 512 KB + 16 KB in the RTC domain | 384 KB | 768 KB (HP L2 memory) + 32 KB (LP) + 8 KB scratchpad |
| **External memory** | flash up to 16 MB; RAM up to 8 MB (4 MB mapped at a time) | SPI, Dual, Quad, Octal flash and RAM, up to 1 GB | external PSRAM supported; size not published | in-package PSRAM: **16 MB** (`ESP32-P4NRW16X`) or **32 MB** (`ESP32-P4NRW32X`), 1.8 V, 16-line OPI/HPI |
| **Wi-Fi** | IEEE 802.11 b/g/n, 2.4 GHz | IEEE 802.11 b/g/n, 2.4 GHz, with 802.11mc fine timing measurement | none | none: **no radio on the chip** |
| **Bluetooth** | v4.2 BR/EDR (Classic) and Bluetooth LE | Bluetooth LE 5 (125 kbps, 500 kbps, 1 Mbps, 2 Mbps; advertising extensions; Mesh); **no Classic** | Bluetooth LE 5.4, certified to 6.0: LE Audio, isochronous channels, subrating, PAwR, AoA and AoD direction finding | none |
| **Other radio** | none | none | IEEE 802.15.4: Thread 1.4, Zigbee 3.0, Matter-over-Thread | none |
| **GPIOs** | 34 | 45 | up to 40 (15 touch-sensing) | 55 |
| **Serial and bus** | 4 SPI, 3 UART, 2 I2C, 2 I2S, SD host and SD slave, CAN (TWAI) | 2 + 2 SPI, 3 UART, 2 I2C, 2 I2S, SD/MMC host (2 slots), CAN (TWAI) | I2C, I2S, SPI, UART, CAN (TWAI), MCPWM | 5 UART + LP UART, 4 SPI + LP SPI, 2 I2C + LP I2C, I3C, 3 I2S + LP I2S, SDHOST, CAN (TWAI) |
| **Network and USB** | Ethernet MAC (IEEE 1588), no USB | full-speed USB OTG, USB Serial/JTAG, no Ethernet MAC | USB-OTG | USB 2.0 high-speed OTG, USB 2.0 full-speed OTG, USB Serial/JTAG, Ethernet MAC |
| **Display and camera** | none | LCD interface; 8 to 16-bit DVP camera | none | MIPI CSI and DSI, LCD and camera controllers, ISP, pixel-processing accelerator, JPEG codec, H.264 encoder |
| **Analogue** | 12-bit ADC (18 channels), two 8-bit DACs, 10 touch sensors | two 12-bit ADCs (20 channels), temperature sensor, 14 touch pins | ADC | analogue signal processing (see datasheet) |
| **Low-power helpers** | ULP coprocessor | ULP-RISC-V and ULP-FSM coprocessors | integrated DC-DC | the LP RISC-V system |
| **Deep-sleep current** | 10 µA | see datasheet | not published | see datasheet |
| **Document** | datasheet v5.3 | datasheet v2.2 | **no datasheet**; the [product page](https://www.espressif.com/en/products/socs/esp32-h4) only | datasheet **v0.7** (preliminary) |

## Notes on each chip

### ESP32

The original, and the only one of the four with Classic Bluetooth. Only it and the P4 have an Ethernet MAC. A single-core and a dual-core version exist. Its 520 KB of SRAM is about the same as the S3's 512 KB, but the external RAM it can address (8 MB, 4 MB at a time) is small beside the S3's 1 GB.

### ESP32‑S3

The "AI" part: SIMD instructions, a wider data bus and about 23 % more CoreMark than two ESP32 cores at the same clock. It has Wi-Fi and Bluetooth LE 5 (no Classic), full-speed USB and a camera and LCD interface. It has no Ethernet MAC.

### ESP32‑H4

A low-power wireless chip, not a Wi-Fi chip: Bluetooth LE 5.4 and 802.15.4 for Thread and Zigbee. It is the slowest of the four (96 MHz) and has the least on-chip SRAM (384 KB). Its datasheet link at `documentation.espressif.com` and the PDF path both return a placeholder page, so every H4 figure here comes from Espressif's product page, which gives the clock, the memory sizes, the radios and the pin count but not CoreMark or an FPU statement.

### ESP32‑P4

A compute chip with no wireless: 400 MHz dual-core RISC-V with an FPU, 768 KB of L2 memory and 16 or 32 MB of PSRAM in the package, MIPI display and camera, and an H.264 encoder. The datasheet mentions Wi-Fi and Bluetooth only in a trademark notice, so a product that needs a radio pairs it with a second chip. The datasheet is version 0.7, so figures may still change. The feature list I extracted shows image and voice blocks (JPEG, ISP, PPA, H.264) and no 3D graphics unit.

## What this means for World Foundry

These are my inferences from numbers in the repository, not measurements on an ESP32.

- **`float` is the right cell on all four.** `zf_cell` is a 32-bit float, and every one of these FPUs is single-precision, so float arithmetic is in hardware and `double` is not. That is what the Forth math plan's D8 `Real` typedef is for.
- **Chips without an FPU run `float` in software.** That is where fixed point could start to pay: the seven chips in the first table that are marked "no". It is not a reason to build fixed point for the four here.
- **RAM is the real constraint.** The Minute Machine's standalone wrapper asks for RAM regions of 1 MB (`OBJD`), 2 MB (`PERM`) and 12 MB (`ROOM`), and zForth's dictionary is 128 KB (`ZF_DICT_SIZE=131072`). Those are configured budgets, not measured needs, but they are far above 384 to 768 KB of on-chip SRAM. Any port would use PSRAM: the P4's 16 or 32 MB in the package, or external PSRAM on an ESP32 or S3.
- **There is no GPU on any of them.** The engine's renderers are OpenGL ES and Metal. An ESP32 port would need a software renderer or a different output path; the P4's 2D blocks help with display, not with 3D.
- **No ESP32 plan or chip choice exists in the repository.** ESP32 appears only in two allocator-alignment plans ([lmalloc non-aligned requests](../plans/2026-05-31-lmalloc-nonaligned-caller-requests.md) and [hard-coded HAL alignment](../plans/2026-05-19-replace-hard-coded-hal-allocator-alignment-with.md)).

## What I could not confirm

- **ESP32‑H4:** no datasheet; CoreMark and the FPU statement beyond the article are missing.
- **ESP32‑P4:** datasheet v0.7 is preliminary. Its external flash options are not listed here.
- **ESP32‑S3 and ESP32‑P4:** I did not extract the PSRAM sizes that typical modules carry. Only the datasheet limits and the P4's two in-package variants are above.
- **ESP32‑C2 and ESP32‑H2:** their "no FPU" rests on the article's table; I did not read their datasheets.
- **ESP32‑S31, ESP32‑H21, ESP32‑E22:** not covered by the article; not checked.
- **CoreMark figures** are Espressif's own and were not reproduced.

## How this was gathered

Public pages only, fetched once. The three PDFs were downloaded to a scratch directory and read as text:

```
B=https://www.espressif.com/sites/default/files/documentation
for f in esp32_datasheet_en esp32-s3_datasheet_en esp32-p4_datasheet_en; do
  curl -sSL -o $f.pdf $B/$f.pdf && pdftotext -layout $f.pdf $f.txt
done
grep -n -E 'Xtensa|RISC-V|MHz|SRAM|ROM|Wi-Fi|Bluetooth|FPU|RV32' *.txt
```

The H4 figures come from [Espressif's ESP32‑H4 product page](https://www.espressif.com/en/products/socs/esp32-h4). The HTML versions of the datasheets at `documentation.espressif.com` are script-rendered and return only a table of contents to a plain fetch, so the PDFs are the source.

## Sources

- [Floating-Point Units on Espressif SoCs](https://developer.espressif.com/blog/2025/10/cores_with_fpu/) (Espressif developer portal, October 2025)
- [ESP32 datasheet v5.3](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- [ESP32‑S3 datasheet v2.2](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)
- [ESP32‑P4 datasheet v0.7](https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf)
- [ESP32‑H4 product page](https://www.espressif.com/en/products/socs/esp32-h4)
- [ESP32‑C6 technical reference manual](https://www.espressif.com/sites/default/files/documentation/esp32-c6_technical_reference_manual_en.pdf)
- [ESP-IDF speed optimisation guide for the ESP32‑S3](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/performance/speed.html)
