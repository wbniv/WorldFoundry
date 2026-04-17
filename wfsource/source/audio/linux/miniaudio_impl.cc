// One-TU instantiation of the miniaudio implementation.
// Keep this file separate so the large #define MINIAUDIO_IMPLEMENTATION
// block compiles in isolation and doesn't slow other TUs.
#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_ENCODING          // we don't write audio files
#define MA_NO_FLAC              // WAV + Ogg Vorbis only
#include <miniaudio/miniaudio.h>
