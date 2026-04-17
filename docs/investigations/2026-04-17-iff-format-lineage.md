# Investigation: IFF format lineage — EA IFF 85, AIFF, RIFF, WorldFoundry IFF

**Date:** 2026-04-17

## The common ancestor: EA IFF 85

Electronic Arts published the Interchange File Format specification in 1985, designed for the Amiga. The core idea is simple and elegant:

```
+--------+--------+---- … ----+--?--+
| ID (4) | size(4)|  payload  | pad |
+--------+--------+---- … ----+--?--+
```

- **ID**: 4 ASCII bytes, big-endian source order
- **size**: 32-bit big-endian, payload bytes only (excludes the 8-byte header)
- **payload**: arbitrary bytes, or nested chunks
- **padding**: to 2-byte boundary; pad byte not counted in size

Container chunk types give the format its structure:

| Type | Meaning |
|------|---------|
| `FORM` | A single typed document; 4-char type follows the size |
| `LIST` | A sequence of `PROP`+`FORM` groups sharing property chunks |
| `CAT ` | A concatenation of unrelated documents |
| `PROP` | Shared properties for a `LIST`'s members |

The Amiga used IFF 85 for nearly everything: `ILBM` (images), `8SVX` (sampled audio), `SMUS` (music scores), `FTXT` (formatted text). It was the native document format of the platform.

---

## The three descendants

```
                    EA IFF 85  (1985, big-endian, 2-byte pad)
                    /          |           \
          AIFF (1988)    WorldFoundry     RIFF (1991)
          Apple/Mac        IFF (~1993)    Microsoft
          big-endian       little-endian  little-endian
          2-byte pad       4-byte pad     2-byte pad
          FORM preserved   no containers  RIFF replaces FORM
```

---

## AIFF (Apple, 1988)

Apple designed AIFF for the Macintosh as a standard audio interchange format, built directly on the IFF 85 FORM container.

**What Apple kept:**
- Big-endian byte order throughout (the Mac 68k was Motorola; this was natural)
- 2-byte chunk padding, size excludes pad byte
- `FORM AIFF` as top-level container — a fully valid IFF 85 FORM

**What Apple added or changed:**

*80-bit extended float for sample rate.* The `COMM` chunk stores sample rate as an IEEE 754 80-bit extended precision value — the native float type of the 68881 FPU coprocessor. Nothing in IFF 85 anticipates this; every AIFF reader needs a custom 80-bit → double converter.

*Intra-chunk structural fields (SSND).* The Sound Data chunk (`SSND`) prepends two 32-bit fields — `offset` and `blockSize` — before the raw PCM samples. These exist to support block-aligned hard disk streaming on the Mac: `offset` skips forward to the first aligned block; `blockSize` states the block size for read-ahead. IFF 85 treats chunk payload as opaque bytes; SSND puts navigational metadata inside the payload at a known position before the data, bending that convention.

*Application-specific chunk vocabulary.* `INST` (instrument: gain, MIDI note, loop points), `MARK` (named cue points), `MIDI` (embedded MIDI data), `APPL` (application-specific). These are valid IFF 85 extensions — the spec explicitly reserves 4-char IDs for application use.

*AIFF-C (1991).* Extended `COMM` with a compression type OSType and Pascal string name, to support non-PCM encodings. The compression type is a Mac OSType — 4 ASCII bytes, same encoding as IFF chunk IDs, but semantically part of the Mac type system.

---

## RIFF (Microsoft, 1991)

Microsoft co-developed RIFF with IBM for Windows 3.1 multimedia. It is IFF 85 with one structural change and one naming change — and that one change cascades everywhere.

**The single structural change: little-endian.**
Microsoft flipped all multi-byte integers to little-endian (Intel byte order). The chunk header becomes:

```
+--------+--------+---- … ----+--?--+
| ID (4) | size(4)|  payload  | pad |
+--------+--------+---- … ----+--?--+
  ASCII     LE u32               2-byte
```

IDs remain ASCII source order (so `RIFF` reads as `RIFF` on disk). Everything numeric — size, sample rate, bit depth — is little-endian.

**Container rename.** `FORM` becomes `RIFF`; `LIST` stays `LIST`; `CAT`/`PROP` are dropped. The top-level chunk of a RIFF file is a `RIFF` chunk with a 4-char type, exactly mirroring IFF 85's `FORM`.

**Chunk padding.** 2-byte boundary, same as IFF 85.

**Notable RIFF formats:**
- `RIFF WAVE` — WAV audio, still the dominant uncompressed audio format
- `RIFF AVI ` — Audio/Video Interleaved, dominant Windows video format through the 1990s
- `RIFF ACON` — animated cursors

RIFF is the reason WAV files are little-endian while AIFF files are big-endian, despite both descending from the same 1985 spec.

---

## WorldFoundry IFF (~1993–1995)

WF IFF shares the EA IFF 85 chunk concept — 4-byte ID, 32-bit size, padded payload — but was designed as a **platform binary blob**, not an interchange format. The design goal was fast direct load on the target hardware (MIPS R3000, later x86), not portability between machines.

**What WF kept:**
- 4-byte ASCII chunk ID, source-order (same as IFF 85 and RIFF)
- 32-bit size field, payload only

**What WF changed:**

*Little-endian, native byte order.* Like RIFF, all numeric fields are little-endian (Intel/MIPS native). Unlike RIFF, this is explicit: the format is not intended to be read on a big-endian machine without a converter. The file is a memory image of the target platform.

*4-byte alignment instead of 2-byte.* Chunks pad to 4-byte boundaries. Reason: MIPS R3000 raises a bus error on unaligned 32-bit loads. 4-byte alignment lets the engine cast chunk payloads directly to structs without copying or fixups. AIFF and RIFF both use 2-byte alignment — insufficient for MIPS.

*No FORM/LIST/CAT/PROP container types.* Any 4-char ID can contain nested chunks. The nesting is syntactic (iffcomp source nests `{ }` blocks) rather than semantic (no special container IDs). There is no document-type field after the size in a container chunk; the ID itself is the type.

*Back-patching: `.offsetof()` / `.sizeof()`.* iffcomp resolves forward references after layout: `.offsetof('CHUNK')` emits the absolute file offset of a named chunk's payload; `.sizeof('CHUNK')` emits its payload size. These become 32-bit little-endian integers in the output. The game engine uses these to jump directly to a known chunk without scanning. AIFF achieves something similar with SSND's `offset` field for the one case of sample-data streaming; WF generalises it to any chunk.

*Fixed-point reals.* iffcomp supports fixed-point literals (e.g. `3.14` with a declared `(3.13)` fractional width) that compile to integer bit patterns. No floating-point values appear in the binary — consistent with the real-target fixed-point arithmetic convention.

*No 80-bit floats, no Mac OSTypes, no Pascal strings.* WF IFF is entirely C-native: NUL-terminated strings, integer scalars, packed structs.

---

## Side-by-side comparison

| Property | EA IFF 85 | AIFF | RIFF | WorldFoundry IFF |
|----------|-----------|------|------|-----------------|
| Year | 1985 | 1988 | 1991 | ~1993 |
| Byte order | Big-endian | Big-endian | **Little-endian** | **Little-endian** |
| Chunk alignment | 2-byte | 2-byte | 2-byte | **4-byte** |
| Container types | FORM/LIST/CAT/PROP | FORM (only) | RIFF/LIST | **None — any ID nests** |
| Size field | Payload only | Payload only | Payload only | Payload only |
| Intra-chunk nav fields | None | **SSND offset+blockSize** | None | **`.offsetof()`/`.sizeof()` (compile-time)** |
| Platform float type | None | **80-bit extended (68881)** | None | **Fixed-point integers only** |
| Intended use | Interchange | Interchange | Interchange | **Direct memory load** |
| Still in use | Legacy | Yes (macOS, Pro Tools) | Yes (WAV, AVI) | WF engine |

---

## The parallel between AIFF and WF IFF

The user observation that prompted this document: Apple and WorldFoundry independently made the same class of extension to IFF 85 — both added navigational metadata inside chunk payloads to support fast random access.

AIFF's approach is reactive: the `SSND` chunk has fixed-position `offset`/`blockSize` fields so that a streaming reader can seek directly to the first aligned block without scanning. It solves one specific access pattern (disk streaming) for one chunk type.

WF's approach is proactive and generalised: the iffcomp compiler resolves `.offsetof()` and `.sizeof()` references for any named chunk and bakes the results as integers anywhere in the file — jump tables, headers, cross-references. The engine doesn't scan; it reads a known-offset integer and seeks. This is the logical extension of what AIFF's SSND `offset` field does, applied uniformly across all chunk types.

Both were driven by the same constraint: the CPU is fast, but the storage medium (Mac hard disk, WF CD-ROM) is slow. Seeking beats scanning.

WF takes the media-awareness one step further: the `.align(N)` directive (with optional `.fillchar(byte)` for padding fill) aligns a chunk's payload to an arbitrary byte boundary — typically 2048 bytes, matching a CD-ROM sector. When large asset chunks (textures, geometry, audio) are sector-aligned, a single read-ahead fills the drive buffer with exactly the data needed; no read spans a sector boundary. AIFF's `blockSize` field communicates this alignment to the reader after the fact; WF's `.align()` bakes it into the file at author time, so the engine never needs to calculate or negotiate it.

---

## What each format optimises for

- **EA IFF 85**: Generic self-describing interchange. Any application on any Amiga can identify and skip unknown chunks.
- **AIFF**: Interchange with streaming. The Mac needs to play audio off a slow hard disk; SSND adds just enough navigational structure for that without breaking IFF compatibility.
- **RIFF**: Interchange on Intel hardware. Microsoft's only change was endianness — everything else is IFF 85.
- **WorldFoundry IFF**: Zero-copy direct load. The file is the data structure. 4-byte alignment, back-patched offsets, fixed-point integers, and little-endian layout all serve the goal of `mmap` + cast-to-struct with no post-processing.
