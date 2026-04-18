// One-TU instantiation of the miniaudio implementation.
// Keep this file separate so the large #define MINIAUDIO_IMPLEMENTATION
// block compiles in isolation and doesn't slow other TUs.
//
// Codec / feature subset: SFX is WAV only (authored as IMA ADPCM inside a
// WAV container — dr_wav decodes that natively, same runtime path as linear
// PCM WAV, ~4× smaller on disk). MIDI goes through TSF as a custom data
// source, not miniaudio decoding. Every MA_NO_* below removes code we have
// no caller for. If a future asset format starts coming in, drop the
// corresponding flag.
#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_ENCODING          // we don't write audio files
#define MA_NO_FLAC              // no FLAC assets
#define MA_NO_MP3               // no MP3 assets
#define MA_NO_VORBIS            // no Ogg Vorbis assets (WAV-only SFX commitment)
#define MA_NO_GENERATION        // no ma_waveform / ma_noise callers
#include <miniaudio/miniaudio.h>
