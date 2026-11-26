# Forth math words, part 2: exponentials, logarithms, rounding and the hardware

**Status: approved 2026‑11‑26; implemented 2026‑11‑26 (Phases 1, 2 and 4 done; Phase 0 and 3 done on the PC, in WebAssembly and, since 2026‑11‑26, on cast1 and cast2 through the [WF Native Tests route](2026-11-26-device-native-test-route.md); the Pixel rows wait for Will's go-ahead; verification 5 fails for `fma` on both Chromecasts, a bionic `fmaf` rounding bug awaiting Will's decision).** Will: "yes to all 3 math" (Q1–Q3 accepted at the recommendations), then "implement math plan". This plan follows the [trig words plan](2026-11-21-forth-trig-words.md): the same table, the same `libm` policy, the same loud refusals and the same three test layers. It grew out of the [lava lamp plan](2026-11-26-lava-lamp.md), which needs `exp`, `expm1`, `cbrt` and `floor`. Will's direction (2026‑11‑26):

> "we could add exp to the engine … we already added trig functions … exp, ln, log, etc would be natural next steps … consider other functions to add? what are the functions getting added?"

> "i want math words to have their own plan AND i want to consider which other mathematical functions should be added while we're there (mostly things that map to hardware-level opcodes these days ;-) ) … identify which functions are directly hardware-supported"

**The answer in one paragraph.** 27 new words, in three groups:

- **Exact (8):** `floor` `ceil` `trunc` `round` `roundeven` `fma` `copysign` `fmod`.
- **Integer bits (3):** `popcount` `clz` `ctz`.
- **`libm` (16):** `exp` `expm1` `exp2` `pow` `ln` `log1p` `log2` `log10` `cbrt` `hypot` `sinh` `cosh` `tanh` `asinh` `acosh` `atanh`.

The hardware matrix below marks which compile to a single instruction on each machine we run on. Three findings shape the plan:

- **Hardware support buys exactness and agreement, not speed.** IEEE 754 requires the operations CPUs implement in hardware to be exact, so they give the same bits everywhere. A Forth word's cost is the interpreter's dispatch either way.
- **Our builds ask for less than our chips can do.** Both Chromecasts have ARMv8 cores but run a 32-bit build targeted at ARMv7, so `floor` and `fma` are software there today.
- **Five level scripts hand-roll `floor`** with a loop that runs once per whole unit of its argument.

## What exists

- **Words (9).** `sin-rev` `cos-rev` `tan-rev` `asin-rev` `acos-rev` `atan-rev` `atan2-rev` `sincos-rev` `sqrt`: custom syscalls 73–81, in [`forth_math_zforth.hpp`](../../engine/stubs/forth_math_zforth.hpp). The reference is [`docs/forth-math-words.md`](../forth-math-words.md).
- **zForth primitives.** `+ - * / % & | ^ << >>` and comparisons. The bitwise ones cast to an integer first (`zforth.c:779`). `negate`, `abs`, `min`, `max` and `mod` are Forth definitions in the bridge's prelude (`scripting_zforth.cc:1588`).
- **Cells are 32-bit floats** (`engine/stubs/zfconf.h:24`). Integers are exact only up to 2²⁴ = 16,777,216. The maths runs in `Real`, which is `double` on desktops and Android and `float` on an ESP32 (`forth_math.hpp:21`); the result is rounded into the float cell.
- **Hand-rolled floors** (the house rule says real maths, never hand-rolled). [`minute_machine/forth.py:63`](../../wflevels/minute_machine/forth.py), [`tide_spike/spike.py:218`](../../wflevels/tide_spike/spike.py), [`cuckoo_village/forth.py`](../../wflevels/cuckoo_village/forth.py), [`anamorphic_shards/generate.py:128`](../../wflevels/anamorphic_shards/generate.py) and [`lava_lamp_digits/generate.py`](../../wflevels/lava_lamp_digits/generate.py) each define a `*-frac` that subtracts 1 until the value is below 1, then `*-floor` and sometimes `*-mod` on top. The loop runs once per whole unit of its argument, and the lava lamp copy is wrong for negative numbers.

## Where our code runs

| Machine | CPU | Instruction set our build targets | Source |
|---|---|---|---|
| This PC and the Linux container | Intel Core i7‑1185G7 (Tiger Lake): SSE4.1, FMA3, AVX2, AVX‑512, POPCNT, LZCNT, BMI1 | **x86‑64 baseline (SSE2)**: CMake passes no `-march` | `lscpu`; `CMakeLists.txt` |
| Chromecast HD (cast1, "boreal") | Amlogic S805X2 (`ro.soc.model` AMLS805X2), 4 × Cortex‑A35 (CPU part `0xd04`, ARMv8‑A), 1.8 GHz. A 32-bit process sees Features `half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt lpae evtstrm aes pmull sha1 sha2 crc32` | **`armeabi-v7a`**: ARMv7, VFPv3‑D16 + NEON. The device reports only 32-bit ABIs | `/proc/cpuinfo` and `ro.soc.*` read on the device (WF Native Tests, J‑35fecef59c35); [CNX Software](https://www.cnx-software.com/2022/09/23/chromecast-with-google-tv-hd-amlogic-s805x2-cpu-av1-video/); [NDK Neon guide](https://developer.android.com/ndk/guides/cpu-arm-neon) |
| Chromecast 4K (cast2, "sabrina") | Amlogic S905D3 (`ro.soc.model` AMLS905D3), 4 × Cortex‑A55 (CPU part `0xd05`, ARMv8.2‑A), 1.908 GHz. Features as cast1, `vfpv4` included | **`armeabi-v7a`**, as above | `/proc/cpuinfo` and `ro.soc.*` read on the device (WF Native Tests, J‑1fa92c283b27) |
| Pixel 8 Pro, Lenovo Tab P11 Pro | ARMv8 and ARMv9 cores | **`arm64-v8a`**: ARMv8.0 | coordinator; `android/*/build.gradle.kts` |
| iOS (Metal build) | Apple A-series | **arm64**: ARMv8 | |
| Browser (`wf_game`, `wf-edit`) | any | **WebAssembly** (Emscripten) | `Taskfile.yml` |
| ESP32 (prospective; trig plan D9) | Xtensa with a single-precision FPU | not chosen | [Espressif](https://developer.espressif.com/blog/2025/10/cores_with_fpu/) |

## Which functions the hardware does

Legend:

- **✓** one instruction at the baseline our build targets.
- **2** or **3**: that many instructions.
- **◐** the chip has the instruction but our baseline does not let the compiler use it. On the PC, glibc's run-time dispatch (IFUNC) reaches it through a function call: `objdump -T` on this PC's glibc 2.43 shows `floorf`, `ceilf`, `truncf`, `rintf` and `fmaf` as IFUNC symbols, and `roundf` is not.
- **✗** a software routine.

| Word | x86‑64 PC (as built) | AArch64: Pixel, tablet, iOS | Chromecasts (`armeabi-v7a`, as built) | Chromecasts if built for ARMv8 32-bit | WebAssembly |
|---|---|---|---|---|---|
| `sqrt` *(exists)* | ✓ `sqrtss` | ✓ `fsqrt` | ✓ `vsqrt` | ✓ | ✓ `f32.sqrt` |
| `min` `max` *(exist, Forth)* | ✓ `minss` `maxss` | ✓ `fminnm` `fmaxnm` | ✓ `vmin` `vmax` (NEON) | ✓ | ✓ `f32.min` `f32.max` |
| `abs` `negate` *(exist, Forth)* | ✓ a mask | ✓ `fabs` `fneg` | ✓ `vabs` `vneg` | ✓ | ✓ `f32.abs` `f32.neg` |
| **`copysign`** | 3 (masks) | 2 (`bit` with a mask) | 2 | 2 | ✓ `f32.copysign` |
| **`floor` `ceil` `trunc`** | ◐ `roundss` (SSE4.1) via IFUNC | ✓ `frintm` `frintp` `frintz` | ✗ software | ✓ `vrintm` `vrintp` `vrintz` | ✓ `f32.floor` `ceil` `trunc` |
| **`roundeven`** (ties to even) | ◐ `roundss` via `rintf` IFUNC | ✓ `frintn` | ✗ | ✓ `vrintn` | ✓ `f32.nearest` |
| **`round`** (ties away from zero) | ✗ a short sequence; `roundf` has no hardware path | ✓ `frinta` | ✗ | ✓ `vrinta` | ✗ a sequence |
| **`fma`** (a·b + c, one rounding) | ◐ `vfmadd` (FMA3) via IFUNC | ✓ `fmadd` | ✗ software: correct, slow | ✓ `vfma` (VFPv4) | ✗ software; only relaxed SIMD has it |
| **`fmod`** | ✗ | ✗ | ✗ | ✗ | ✗ |
| **`popcount`** | ◐ `popcnt` (x86‑64‑v2); a sequence at baseline | 3 (`cnt` + `addv`, NEON) | 2–3 (`vcnt` + `vpaddl`) | 2–3 | ✓ `i32.popcnt` |
| **`clz`** | ◐ `lzcnt` (v3); 2 at baseline (`bsr`) | ✓ `clz` | ✓ `clz` | ✓ | ✓ `i32.clz` |
| **`ctz`** | ◐ `tzcnt` (v3); 2 at baseline (`bsf`) | 2 (`rbit` + `clz`) | 2 (`rbit` + `clz`) | 2 | ✓ `i32.ctz` |
| **`exp` … `atanh`**, and the trig words | ✗ `libm` (glibc picks FMA-tuned versions of `expf`, `logf`, `exp2f` and `sinf`: IFUNC, still software) | ✗ `libm` (bionic) | ✗ | ✗ | ✗ `libm` (Emscripten) |

Sources: [Arm A64 and A32 ISA](https://developer.arm.com/documentation/ddi0602/latest), [WebAssembly 3.0 instructions](https://webassembly.github.io/spec/core/syntax/instructions.html), [x86‑64 microarchitecture levels](https://en.opensuse.org/X86-64_microarchitecture_levels) (v2 adds SSE4.1 and POPCNT; v3 adds FMA, LZCNT and BMI1), and LLVM's [ARM rounding test](https://llvm.googlesource.com/llvm/+/master/test/CodeGen/ARM/arm32-rounding.ll) (with `+fp-armv8`, floor, ceil and trunc become `vrintm`, `vrintp` and `vrintz`). On GPUs, `exp2`, `log2`, reciprocal square root, `sin` and `cos` *are* hardware: approximate special-function units (PTX `ex2.approx`, `lg2.approx`). That is why shading languages treat them as cheap, but it doesn't help a CPU-side Forth.

**ESP32, unconfirmed.** Espressif documents a single-precision FPU. A QEMU commit and the forum confirm `madd.s` and hardware divide and square-root steps. Rounding, `abs` and `neg` opcodes appear in Xtensa material we could not verify ([QEMU commit](https://git.cs.tu-dortmund.de/SYS-OSS/FRET-qemu/commit/f8c613701637ebfbf75570153715af3ac7aeca9d), [forum](https://esp32.com/viewtopic.php?p=35764)). Fill this column in from the Xtensa ISA manual when a chip is chosen.

### Why it matters: exact versus recommended

IEEE 754 **requires** square root, fused multiply-add, remainder, minimum, maximum, rounding to integer, and the sign operations (`abs`, `negate`, `copySign`), and requires them to be exact ([Wikipedia, IEEE 754 required operations](https://en.wikipedia.org/wiki/IEEE_754#Required_operations)). Those are precisely what CPUs build into silicon. Any conforming machine, instruction or library gives **the same bits**: `floor` on the PC, the Pixel, the Chromecast and in the browser agree exactly, whether the answer comes from `frintm` or from bionic's software.

`exp`, `log`, `pow`, `hypot`, the trig and hyperbolic functions are only **recommended** (clause 9) ([Wikipedia, recommended operations](https://en.wikipedia.org/wiki/IEEE_754#Recommended_operations)). glibc, bionic, Emscripten and Apple are not all correctly rounded, so a result may differ in its last bit between machines. The trig plan therefore checks "within one float ulp". Because `Real` is `double` and the cell is `float`, those differences should almost never survive the rounding into the cell. Phase 0 checks that claim on every target rather than assuming it.

**Speed** hardly matters inside Forth. Every word costs a VM dispatch, a syscall switch and a table lookup. A one-instruction `floor` and a 20-instruction `exp` should cost about the same per call, and Phase 0 measures this. Where the hardware matters for speed is the engine's C++ (Jolt, the deformers), which is Q2's subject, not this plan's.

```mermaid
flowchart TD
    F["a function we might add"] --> R{"IEEE 754 required<br/>(exact)?"}
    R -->|yes| H{"one instruction on<br/>most of our targets?"}
    H -->|yes| A["Group A, exact:<br/>floor ceil trunc roundeven round fma copysign"]
    H -->|no| A2["Group A, exact anyway:<br/>fmod"]
    R -->|no| I{"integer bit<br/>operation?"}
    I -->|"yes, result fits 2^24"| B["Group B:<br/>popcount clz ctz"]
    I -->|"yes, result can exceed 2^24"| X1["not added:<br/>rotates, byte swap"]
    I -->|no| U{"a use in a level<br/>or the near plans?"}
    U -->|yes| C["Group C, libm:<br/>exp ln pow cbrt hypot tanh ..."]
    U -->|no| X2["not added:<br/>erf, gamma, Bessel, exp10 ..."]
```

## The words

All 27 follow the trig words' rules (D3 below):

- computed in `Real` with `libm`, then rounded into the float cell;
- a non-finite argument, or a non-finite result, is **refused**: the word and the argument go to the log and the script's frame aborts, never papered over;
- a domain error refuses the same way.

Custom syscalls **82–108** (sys 210–236), straight after the trig set. 0–55 and 72 are taken, and 82 onward is free.

| # | Word | Stack effect | Refuses | Uses |
|---|---|---|---|---|
| | **A · Exact** | | | |
| 82 | `floor` | `( x -- ⌊x⌋ )` | non-finite | replaces the five hand-rolled loops; digits of the time |
| 83 | `ceil` | `( x -- ⌈x⌉ )` | non-finite | counts that round up |
| 84 | `trunc` | `( x -- r )` toward zero | non-finite | the integer part of a signed value |
| 85 | `round` | `( x -- r )` ties away from zero | non-finite | the school rule; C `round` |
| 86 | `roundeven` | `( x -- r )` ties to even | non-finite | the hardware's own rounding: no bias over many values (C23 name; WebAssembly calls it `nearest`) |
| 87 | `fma` | `( a b c -- a·b+c )` one rounding | a non-finite result | polynomials and `lerp` without the second rounding |
| 88 | `copysign` | `( x y -- \|x\| with y's sign )` | non-finite | signs without branches |
| 89 | `fmod` | `( x y -- r )` x − n·y, n truncated, takes x's sign | y = 0 | wrapping angles, phases and time; the existing `mod` is an integer `%` |
| | **B · Integer bits** (argument an integer, 0 ≤ n ≤ 2²⁴) | | | |
| 90 | `popcount` | `( n -- bits set )` | a non-integer or out of range | neighbour masks in tile maps, flag counts |
| 91 | `clz` | `( n -- leading zeros in 32 bits )`, `clz 0` = 32 | as above | integer log2: `31 swap clz -` |
| 92 | `ctz` | `( n -- trailing zeros )`, `ctz 0` = 32 | as above | the lowest set flag |
| | **C · libm** | | | |
| 93 | `exp` | `( x -- eˣ )` | non-finite result | the lava lamp's hot layer; growth, decay |
| 94 | `expm1` | `( x -- eˣ − 1 )` | non-finite result | `1 − e^(−k·dt)` for tiny k·dt keeps its digits |
| 95 | `exp2` | `( x -- 2ˣ )` | non-finite result | octaves, doubling |
| 96 | `pow` | `( x y -- xʸ )` | x < 0 with non-integer y; 0 with y < 0 | easing curves, falloff |
| 97 | `ln` | `( x -- ln x )` | x ≤ 0 | inverse of `exp`; half-lives |
| 98 | `log1p` | `( x -- ln(1+x) )` | x ≤ −1 | inverse of `expm1` |
| 99 | `log2` | `( x -- r )` | x ≤ 0 | octaves, mip levels |
| 100 | `log10` | `( x -- r )` | x ≤ 0 | decibels, decades |
| 101 | `cbrt` | `( x -- ∛x )` | non-finite | radius from volume: merging wax keeps its volume |
| 102 | `hypot` | `( x y -- √(x²+y²) )` | non-finite | distances without overflow |
| 103 | `sinh` | `( x -- r )` | non-finite result | catenaries (cables, chains) |
| 104 | `cosh` | `( x -- r )` | non-finite result | as above |
| 105 | `tanh` | `( x -- r )` | non-finite | a soft limit for speeds and easing, −1 to 1 |
| 106 | `asinh` | `( x -- r )` | non-finite | inverse |
| 107 | `acosh` | `( x -- r )` | x < 1 | inverse |
| 108 | `atanh` | `( x -- r )` | \|x\| ≥ 1 | inverse |

**Names (D5).** Cells are reals, so we drop ANS Forth's `F` prefix, as `sqrt` already does: `FEXP`, `FLN`, `FEXPM1` and `FLNP1` become `exp`, `ln`, `expm1` and `log1p`. ANS `FLOG` is base 10. "log" means natural log to some readers and base 10 to others, so we spell it `log10` and define **no `log`**. `F**` becomes `pow`. Like the trig words, these take and return reals; the integer-bit words take reals that must be whole numbers.

**Considered and not added:**

| Candidate | Why not |
|---|---|
| Reciprocal and reciprocal-square-root *estimates* (`rcpss`, `rsqrtss`, `frecpe`, `frsqrte`) | Hardware, but approximations of 8 to 14 bits. The house rule is real maths, never approximations. Exact `1/x` and `1/√x` are two words already: `1 swap /` and `sqrt 1 swap /` |
| `rotl`, `rotr`, byte swap, 32-bit hashes | Hardware everywhere, but a float cell holds integers exactly only to 2²⁴. A 32-bit rotate's result would silently lose bits. Revisit if cells change (the trig plan's D9) |
| `fmin`, `fmax`, `fabs` | `min`, `max` and `abs` exist. NaNs cannot reach Forth (they are refused at the boundary), so IEEE's NaN rules for min and max never apply |
| `isnan`, `isinf`, `isfinite`, `signbit` | For the same reason, every value in Forth is finite |
| `ldexp`, `frexp`, `scalbn`, `logb`, `nextafter` | IEEE-required and cheap, but no use in sight |
| `remainder` (IEEE, quotient ties to even) | `fmod` covers wrapping; the IEEE variant is rarely what a script wants |
| `exp10`, `rootn`, `pown`, `compound`, `sinpi` and the other clause 9 extras | `pow` and the revolution-based trig words cover them |
| `erf`, `tgamma`, `lgamma`, Bessel functions | No use |
| `clamp`, `lerp`, `smoothstep`, `sign` | Short Forth definitions a level writes itself; no syscall needed (`lerp` can use `fma`) |
| The x87 transcendentals (`fsin`, `f2xm1`, `fyl2x`) | Historically "hardware", but slow, with known argument-reduction errors, and unused by 64-bit code |

## How a word runs

```mermaid
sequenceDiagram
    participant L as Level script
    participant V as zForth VM
    participant B as Bridge (scripting_zforth.cc)
    participant T as forth_math_zforth.hpp
    participant M as forth_math.hpp
    L->>V: 2.7 floor
    V->>B: sys 210 (custom 82)
    B->>T: HandleSyscall(ctx, 82)
    T->>T: pop x, check it is finite
    T->>M: Floor(x) in Real
    M-->>T: Result ok, value 2.0 (frintm, roundss or software)
    T->>V: push 2.0 as a float cell
    Note over T,V: domain error or non-finite: name the word and argument in the log, zf_abort, the frame ends
```

## Decisions

| # | Question | Recommendation | Alternatives |
|---|---|---|---|
| D1 | A plan of its own | **Yes** (Will, 2026‑11‑26). The lava lamp plan points here | Keep it inside the lava lamp plan |
| D2 | Which words | **The 27 above**: everything with a use or an IEEE guarantee, nothing speculative | The lava lamp's four (`exp`, `expm1`, `cbrt`, `floor`); groups A and C only (no bit words) |
| D3 | Implementation | **The trig plan's D3 option B**: plain `libm` (`std::floor`, `std::fma`, `std::exp` …) in `Real`, so the compiler emits the instruction wherever the baseline allows and glibc dispatches on the PC; no hand-written instructions, no promise at special points beyond IEEE's | Intrinsics per architecture (faster nowhere that matters, because the VM dominates); our own polynomials (forbidden) |
| D4 | Compile baselines | **Unchanged in this plan.** Group A is exact everywhere, so raising the baseline would change speed, never results. Q2 asks whether to measure an ARMv8 32-bit Chromecast build separately | Raise them here: x86‑64‑v3 on the PC (excludes pre-2013 CPUs), `-march=armv8-a -mfpu=neon-fp-armv8` for 32-bit Android (every 32-bit device we own is ARMv8; true ARMv7 phones would stop working) |
| D5 | Names | **No `F` prefix; `ln`, `log10` and no `log`; `roundeven` and `round`; `fmod` beside the existing integer `mod`** | ANS names with `F` (out of step with `sqrt` and `sin-rev`) |
| D6 | Integer-bit domain | **Whole numbers 0 to 2²⁴, refused otherwise.** That is the range a float cell holds exactly, and `clz` and `ctz` count in 32 bits (`clz 0` = `ctz 0` = 32, as in C++20 and WebAssembly) | Count in 24 bits (unusual); accept any real and truncate (hides mistakes) |
| D7 | The hand-rolled floors | **Replace all five in this plan's last phase** with `floor` and `fmod`, each level's reference test unchanged. The lava lamp copy goes away with the lava lamp plan anyway | Leave them (they work for their ranges, but break the house rule and loop per unit) |
| D8 | `fma` where there is no hardware FMA | **Our own exact `ExactFmaf`** (Will, 2026‑11‑26: "yes" to option 1): exact `double` product, error-free two-sum, round to odd, one conversion to float; `std::fma` kept where the compiler reports an FMA instruction (`__ARM_FEATURE_FMA`, `__FMA__`, `__FP_FAST_FMAF`) | The ARMv8 32-bit build (`vfma`) as the only fix; accept one ulp in halfway cases on `armeabi-v7a` |

**D8, why we leave plain `libm` for one word.** D3 says plain `libm`, on the grounds that IEEE 754 makes `fma` exact, so every library gives the same bits. On the Chromecasts it does not: their `armeabi-v7a` code has no FMA instruction, `std::fma(float…)` is bionic's software `fmaf`, and that returns `0x3f801001` for `(1 + 2⁻¹²)² − 10⁻²⁴` where the correctly rounded answer (glibc, WebAssembly, the exact oracle) is `0x3f801000`. The [WF Native Tests probe](2026-11-26-device-native-test-route.md#findings) showed on both devices that the rounding mode does change in our process and that the same algorithm written out returns the right answer, so the fault is in the compiled library routine. Will chose to compute it ourselves (2026‑11‑26, "yes" to option 1 of three). `ExactFmaf` is exact arithmetic, not an approximation, so it keeps the house rule's intent (real maths, the true value); it changes no rounding mode, and where the target has an FMA instruction `std::fma` is still that instruction. The host test checks `ExactFmaf` against glibc's `fmaf` bit for bit (edge cases and 400,000 random cases, `task test-forth-math`).

### Questions for Will

| # | Question | My recommendation |
|---|---|---|
| Q1 | Add group B (`popcount`, `clz`, `ctz`) now, with no level needing them yet? | ~~**Yes**: three table rows, and the hardware does them in one instruction almost everywhere~~ **Accepted.** |
| Q2 | Open a separate TODO to measure the Chromecasts on an ARMv8 32-bit build (`vrint`, `vfma`, and whatever else the compiler finds in Jolt and the deformers)? | ~~**Yes**, as a T4 measurement~~ **Accepted**: TODO item added. |
| Q3 | Run the agreement check (verification 5) on the devices too, not only in the container? | ~~**Yes**~~ **Accepted**: verification 5 runs on the Pixel, cast1 and cast2. |

## Phases

```mermaid
flowchart LR
    P0["Phase 0<br/>VM cost per word<br/>cpuinfo on cast2<br/>libm agreement of the 9 trig words"] --> P1["Phase 1<br/>27 words: maths, table,<br/>vectors, unit and VM tests"]
    P1 --> P2["Phase 2<br/>engine dispatcher,<br/>docs/forth-math-words.md"]
    P2 --> P3["Phase 3<br/>agreement on PC, WASM,<br/>Pixel, cast1, cast2"]
    P2 --> P4["Phase 4<br/>replace the hand-rolled floors<br/>in four levels"]
```

- **Phase 0, measure.**
  - ~~Time 10,000 calls of `sqrt`, `atan2-rev` and a dummy syscall in the VM on the PC~~ and on cast1 (`profile-begin` / `profile-end`) to test "the VM dominates". **PC done** with `tests/forth_math_vm_cost.py` (the real VM and word table, `-O2`, in the container; each word's cost over the bare `do … loop`, best of 31). **The VM dominates:** one iteration of an empty `do 2 drop loop` costs 274 ns; on top of that a trivial syscall costs 33 ns, `sqrt` 32, `floor` 45, `exp` 55, `fma` 67, `pow` 87 and `atan2-rev` 89. A one-instruction word and a `libm` word differ by about 20 ns, a tenth of the interpreter's own cost per step. The machine was shared (load average 6), and repeated runs moved each number by up to 2×, never the ordering against the loop. **cast1 done** (2026‑11‑26, WF Native Tests): the bare loop step costs 1,062 ns, a trivial syscall 168, `floor` 256, `exp` 314 and `atan2-rev` 446; the VM dominates there too. Verification 4 has the table.
  - ~~Read cast2's `/proc/cpuinfo` (Features, CPU part) to confirm its core.~~ **Done** 2026‑11‑26 through WF Native Tests: Cortex‑A55 (part `0xd05`) in an Amlogic S905D3 at 1.908 GHz; cast1 is Cortex‑A35 (`0xd04`), S805X2, 1.8 GHz. Both report `vfpv4` (so `vfma`) to 32-bit code, which our VFPv3 build does not use. The machine table has the rows.
  - ~~Run the existing nine words' vector file on every target~~, as the baseline for Phase 3. **PC and WebAssembly done** (folded into Phase 3's run, which covers all 36 words); devices pending.
- ~~**Phase 1, the words.**~~ **Done 2026‑11‑26** (commit `a6ed5868e`).
  - `forth_math.hpp`: the maths and its `Result`.
  - `forth_math_zforth.hpp`: the table and dispatch, extending `kLastCustom` to 108.
  - The prelude line in `scripting_zforth.cc`.
  - `tests/gen_forth_math_vectors.py`: special values, each domain edge and random arguments against a `long double` reference.
  - `tests/forth_math_test.cpp` in both precisions.
  - `tests/test_forth_math_vm.py`: every word through the real VM, stacks left empty, refusals that abort and leave the VM usable.
- ~~**Phase 2, engine and docs.**~~ **Done 2026‑11‑26** (commits `a6ed5868e`, `5dda162e2`). The engine test now reads the mailboxes through the Director: with the test script in its place nothing holds the Player up, and once it falls out of the room (about 30 s in) the bridge stops reporting through it.
  - `tests/verify_forth_math_engine.py` through the engine's own dispatcher.
  - `docs/forth-math-words.md` gains the 27 rows, the names rule and the hardware matrix, and `tests/test_forth_math_docs.py` keeps it equal to the table.
- **Phase 3, agreement.** A new `tests/forth_math_agreement.py` runs the vectors on the PC (glibc), in WebAssembly (Emscripten, under Node), on the Pixel (bionic, arm64) and on cast1 and cast2 (bionic, `armeabi-v7a`). It reports, per word, whether group A is bit-identical everywhere (it must be) and the worst ulp spread for groups C and trig.
  - ~~PC and WebAssembly~~ **done** (commit `7ecfe5a17`): `tests/forth_math_dump.cpp` prints the float bits of all 36 words on the 2,990 shared vectors and 2,000 portable random arguments each (74,990 results, 615 of them refusals). glibc in the container and Emscripten 6.0.4 under its Node 22.16 agree on **every bit of every result**, groups C and trig included (0 differ, 0 ulp). The repo pins emsdk 6.0.0 (`task setup-emsdk`), which is not installed and would not fit the disk's 13 GB headroom, so this run used the emsdk 6.0.4 already on the machine via `EMCC_DIR`.
  - **Devices: pending, no route.** The chromecast coordinator's workflows install, launch, profile and capture APKs; none runs a native binary or a shell command, or returns a file from the device. Running the vectors on cast1 and cast2 needs either such a workflow or an APK with a vector-dump mode whose output a workflow returns. The Pixel is never used for this.
- ~~**Phase 4, the hand-rolled floors.**~~ **Done 2026‑11‑26** (commits `dabc51dc8`, `f1a57fb91`, `8708716d0`, `86f07fdae`).
  - ~~Replace the `*-frac` / `*-floor` / `*-mod` definitions in Minute Machine, Tide spike, Cuckoo Village and Anamorphic Shards with `floor` and `fmod`.~~ Each `*-frac` is now `dup floor -`, each `*-floor` is gone (its uses call `floor`), and each `*-mod` is `over over / floor * -`. **Not `fmod`:** the old `*-mod` is a floored modulo whose result takes the divisor's sign, and `fmod` truncates and takes the dividend's, so they differ for negative operands; the floored form keeps every result identical. Dutch Cuckoo Village shares Cuckoo Village's library and called `cv-floor` itself, so it changed and was rebuilt too.
  - ~~Rebuild each level, and check each against its reference.~~ Each level rebuilt in the Blender container; each `.lev` diff is exactly the changed definitions (Dutch also gained two cell definitions its committed build predated). Tide spike's outputs are gitignored: variants a and d were rebuilt, and d ran 40 s in the Debug engine with no zforth error.
  - Found and left alone (not in this plan's list): the same loop in `aquarium_sea_stars/sea_star_player.fth`, `aquarium_blue_shrimp/shrimp.fth`, `aquarium_tanks/controller.fth` and `moon_lantern/generate.py`.

No visible surface: these are engine words and a reference document, so this plan has no mockups.

## Verification

1. The unit test passes in both precisions. Every new word is within one float ulp of a `long double` reference on 100,000 random arguments; groups A and B are exact; every domain edge refuses:

    ```bash
    task test-forth-math
    ```

    ```
    task: [test-forth-math] python3 tests/gen_forth_math_vectors.py --check
    vectors up to date
    task: [test-forth-math] docker run --rm --ulimit core=0 -v "$PWD":/src:ro wf-linux-test:local bash -c 'set -euo pipefail; for mode in "" "-DWF_FORTH_MATH_FLOAT"; do g++ -std=c++17 -O1 -Wall -Wextra $mode -I/src/engine/stubs -I/src/tests /src/tests/forth_math_test.cpp -o /tmp/forth_math_test && /tmp/forth_math_test; done'

    forth_math_test (double Real): OK, 7446 checks, 2990 shared vectors across 36 words
    forth_math_test (float Real): OK, 7446 checks, 2990 shared vectors across 36 words
    rc=0
    ```

    **PASS.** 2,990 shared vectors across 36 words in both `Real` modes, the exact words compared bit for bit, and 100,000 random arguments of every new word against `long double`: groups A and B exact, group C within one float ulp with no absolute floor in `double`. The `float` (single-FPU) build needs two ulps for group C (251 of its random results sit at two ulps with float `libm`, measured with the bar at one), so the test and `docs/forth-math-words.md` say two there.

2. The bridge registers exactly the 36 words (9 + 27) with the stack effects in the table, and the reference document lists the same:

    ```bash
    python3 tests/verify_forth_math.py
    scripts/in-linux-container.sh python3 -m pytest tests/test_forth_math_docs.py tests/test_forth_math_vm.py -q
    ```

    ```
    155 checks across 36 words in the real zForth VM: PASS
    ......                                                                   [100%]
    6 passed in 7.80s
    rc=0
    ```

    **PASS.**

3. Every word works through the engine's own dispatcher, and a refusal names the word in the engine log and leaves the engine running:

    ```bash
    scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
    WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh bash -c 'timeout 400 xvfb-run -a -s "-screen 0 1280x720x24" python3 tests/verify_forth_math_engine.py'
    ```

    ```
    [140/140] Linking CXX executable /build/wf-game-dev/src/engine/wf_game
    -rwxr-xr-x 1 root root 231290272 Nov 26 04:09 /build/wf-game-dev/src/engine/wf_game
    EXIT 0
    51 engine checks: PASS
    ```

    **PASS.** The Debug ASan engine: all 36 words through the bridge's own dispatcher, the `asin-rev` refusal and a two-argument `pow` refusal named in the engine log (`zforth: pow: negative base with a non-integer exponent (arguments -8 0.5)`), the engine still running, and recovered by a good script each time. The first run failed two checks after the `pow` refusal; the cause was the test reading the mailboxes through the Player, which falls out of the room about 30 s in with the test script in the Director's place, not the words. It now reads them through the Director.

4. The VM cost per word is recorded for the PC and cast1, for `floor`, `exp` and a dummy syscall (Phase 0's measurement, repeated on the finished words).

    ```
    $ scripts/in-linux-container.sh python3 tests/forth_math_vm_cost.py --repeats 31
    10000 calls per run, best of 31, VM compiled -O2; loop overhead 274.2 ns per iteration
    word                          ns per call  vs nop-sys
    nop-sys (trivial syscall)            33.3       1.00x
    sqrt                                 32.3       0.97x
    atan2-rev                            88.9       2.67x
    floor                                44.5       1.34x
    exp                                  54.6       1.64x
    pow                                  87.1       2.62x
    fma                                  67.3       2.02x
    ```

    ```
    $ python3 scripts/device_native_tests.py run --device chromecast-test-01
    ...
    J-35fecef59c35: completed; verified 16 artifacts -> /home/will/WorldFoundry-wbniv/build/device-native-tests/chromecast-test-01/J-35fecef59c35
    collect: cpuinfo rc=0 1 ms · forth-math-dump rc=0 208 ms · forth-math-vm-cost rc=0 4,159 ms · fmaf-probe rc=0 0 ms
    $ python3 tests/forth_math_vm_cost.py --device chromecast-test-01
    chromecast-test-01: 10000 calls per run, best of 31, VM compiled -O2; loop overhead 1062.4 ns per iteration
    word                          ns per call  vs nop-sys
    nop-sys (trivial syscall)           167.6       1.00x
    sqrt                                244.9       1.46x
    atan2-rev                           445.5       2.66x
    floor                               256.2       1.53x
    exp                                 313.5       1.87x
    pow                                 576.4       3.44x
    fma                                 385.4       2.30x
    rc=0
    $ python3 tests/forth_math_vm_cost.py --device chromecast-test-02
    chromecast-test-02: 10000 calls per run, best of 31, VM compiled -O2; loop overhead 735.2 ns per iteration
    word                          ns per call  vs nop-sys
    nop-sys (trivial syscall)           137.7       1.00x
    sqrt                                186.5       1.35x
    atan2-rev                           308.4       2.24x
    floor                               171.8       1.25x
    exp                                 196.1       1.42x
    pow                                 368.1       2.67x
    fma                                 262.2       1.90x
    rc=0
    ```

    **PC: PASS** (recorded; "the VM dominates" holds: the loop step alone is 274 ns, and `floor` and `exp` differ by 10 ns). **cast1: PASS** (recorded 2026‑11‑26 through the [WF Native Tests route](2026-11-26-device-native-test-route.md): the same host, request script and VM, compiled `-O2` by the NDK for `armeabi-v7a`, run inside a coordinator `check`). The VM dominates on cast1 as well: the loop step alone is 1,062 ns, and `floor` and `exp` differ by 57 ns. cast2 (Cortex‑A55) is recorded too, about 30 % faster throughout. An earlier cast1 run (J‑308101d5f422) gave the same picture within 10 %.

5. Agreement across machines. Group A and group B are bit-identical on the PC, WebAssembly, the Pixel, cast1 and cast2; groups C and trig are within one float ulp, with the spread recorded per word:

    ```bash
    python3 tests/forth_math_agreement.py --target pc --target wasm --target phone-pixel-8-pro --target chromecast-test-01 --target chromecast-test-02
    ```

    ```
    $ EMCC_DIR=/home/will/bsnes-jg-player/emsdk/upstream/emscripten python3 tests/forth_math_agreement.py --target pc --target wasm
    wasm: emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 6.0.4 (fe5be6afdff43ad58860d821fcc8572a23f92d19); node v22.16.0
    74990 results per target; reference pc
    word         group                    wasm
    acos-rev     trig      0 differ, max 0 ulp
    ...          (all 36 words: 0 differ, max 0 ulp)
    tanh         C         0 differ, max 0 ulp
    PASS
    ```

    Re-run 2026‑11‑26 with the device targets, after `python3 scripts/device_native_tests.py run --device chromecast-test-01` and `--device chromecast-test-02` collected their dumps:

    ```
    $ EMCC_DIR=/home/will/bsnes-jg-player/emsdk/upstream/emscripten python3 tests/forth_math_agreement.py --target pc --target wasm --target phone-pixel-8-pro --target chromecast-test-01 --target chromecast-test-02
    wasm: emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 6.0.4 (fe5be6afdff43ad58860d821fcc8572a23f92d19); node v22.16.0
    phone-pixel-8-pro: NOT RUN: Will's daily phone; never run here
    chromecast-test-01: WF Native Tests v2, armeabi-v7a, NDK clang and bionic libm; collected from /home/will/WorldFoundry-wbniv/build/device-native-tests/chromecast-test-01/J-35fecef59c35/wf.log
    chromecast-test-02: WF Native Tests v2, armeabi-v7a, NDK clang and bionic libm; collected from /home/will/WorldFoundry-wbniv/build/device-native-tests/chromecast-test-02/J-1fa92c283b27/wf.log
    74990 results per target; reference pc
    word         group                    wasm     chromecast-test-01     chromecast-test-02
    acos-rev     trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    asin-rev     trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    atan-rev     trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    atan2-rev    trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    cos-rev      trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    sin-rev      trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    sincos-rev   trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    sqrt         trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    tan-rev      trig      0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    ceil         A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    clz          A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    copysign     A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    ctz          A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    floor        A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    fma          A/B       0 differ, max 0 ulp FAIL 1 differ, max 1 ulp FAIL 1 differ, max 1 ulp
    fmod         A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    popcount     A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    round        A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    roundeven    A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    trunc        A/B       0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    acosh        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    asinh        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    atanh        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    cbrt         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    cosh         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    exp          C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    exp2         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    expm1        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    hypot        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    ln           C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    log10        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    log1p        C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    log2         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    pow          C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    sinh         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    tanh         C         0 differ, max 0 ulp    0 differ, max 0 ulp    0 differ, max 0 ulp
    FAIL: fma on chromecast-test-01, fma on chromecast-test-02
    rc=1
    ```

    **PC and WebAssembly: PASS**, bit-identical for all 36 words. **`phone-pixel-8-pro`: NOT RUN:** Will's daily phone; it waits for his go-ahead. **`chromecast-test-01`, `chromecast-test-02`: FAIL, for `fma` only.** The other 35 words are bit-identical with the PC on both Chromecasts, groups C and trig included (0 ulp, no refusal differs). `fma` differs in one case, the plan's own double-rounding vector `1.000244140625 1.000244140625 -1e-24`: the devices give `0x3f801001`, one ulp above the correctly rounded `0x3f801000` that glibc, WebAssembly and the oracle give. The cause is bionic's `fmaf`, not our code: our `armeabi-v7a` build is VFPv3, so `std::fma(float…)` calls bionic's software `fmaf`, and the route's `fmaf-probe` shows on both devices that the rounding mode does change in this process and that the same msun algorithm written out with volatile operands returns `0x3f801000`, while the library's `fmaf` returns `0x3f801001` (details in the route plan's Findings). How to fix it is Will's decision; the three options, with a recommendation, are in the [route plan's Findings](2026-11-26-device-native-test-route.md#findings).

6. The four levels whose hand-rolled floors were replaced still match their references:

    ```bash
    python3 tests/verify_minute_machine_forth.py
    scripts/in-linux-container.sh python3 -m pytest tests -q -k "cuckoo or anamorphic or tide"
    ```

    ```
    125 frames; worst position 0.0015 mm, rotation 0.0008 deg, scale 0.000006
    PASS
    ...
    =========================== short test summary info ============================
    ERROR tests/test_aquarium_thai_reef.py
    ERROR tests/test_minute_machine_channels.py - AttributeError: module 'timelin...
    ERROR tests/test_minute_machine_parts.py - AttributeError: module 'timeline' ...
    ERROR tests/test_pipe_hop.py - RuntimeError: could not connect to 127.0.0.1:7...
    ERROR tests/test_thai_reef_placement.py
    !!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!!
    3 skipped, 1582 deselected, 5 errors in 29.75s
    rc=2
    ```

    **Minute Machine: PASS** (0.0015 mm, as before the change; the engine `--compare` also gives the trig plan's 0.015 mm at all eight times). **The pytest command as written: FAIL**, interrupted by five collection errors in modules this change does not touch (`timeline` and `config` module-name collisions between levels, a missing `aquarium_sea_stars` constant, a test that connects to a server at import). Run per level in the container instead, after the rebuilds:
    ```
    83 Cuckoo Village, Dutch Cuckoo Village and Anamorphic Shards tests: 81 passed, 2 failed
      test_cuckoo_village_settings_effect: passes alone (5 passed); fails only after test_dutch_cuckoo_village
        has imported Dutch's own `forth` module (the same collision)
      test_cuckoo_village_settings::test_the_oad_is_what_the_tool_makes_from_the_oas: oas2oad exits 1 (the tool, not a script)
    verify_cuckoo_village_forth.py: 1100 days x 3 times x 3 settings = 9900 frames, 0 failures; flames 0; flowers 0
    Minute Machine forth, timeline, channels, parts: 21 passed
    ```
    The tide tests in the selection are Tide Harbour's (its own director, not Tide spike's); their four failures and twelve errors are in files this change does not touch. Tide spike has no reference test: variants a and d rebuilt and d ran in the engine without a zforth error.

7. Nothing else moved: the existing Forth tests still pass:

    ```bash
    task test-forth-source
    ```

    ```
    task: [test-forth-source] python3 tests/verify_forth_source.py
    PASS: 10105 checks, including 10000 repeated calls
    rc=0
    ```

    **PASS.**
