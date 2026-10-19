// Decoder-init equivalence harness for tests/test_android_size_trim.py.
//
// SoundBuffer::play() (wfsource/source/audio/linux/buffer.cc) initialises its
// decoder with encodingFormat = ma_encoding_format_wav instead of the generic
// trial-and-error init. This compiles the game's own miniaudio_impl.cc (the
// same MA_NO_* subset) and, for each file on the command line, decodes it
// both ways and prints one line:
//
//   <file> generic=<rc>:<frames>:<fnv1a of the PCM> wav=<rc>:<frames>:<fnv1a>
//
// The test requires the two halves of every line to match.
#include "../wfsource/source/audio/linux/miniaudio_impl.cc"

#include <cstdio>
#include <cstdint>
#include <vector>

static void decode(const std::vector<unsigned char>& bytes, bool wav, char* out, size_t n)
{
    ma_decoder_config cfg = ma_decoder_config_init(ma_format_s16, 0, 0);
    if (wav) cfg.encodingFormat = ma_encoding_format_wav;
    ma_decoder dec;
    ma_result rc = ma_decoder_init_memory(bytes.data(), bytes.size(), &cfg, &dec);
    if (rc != MA_SUCCESS) { std::snprintf(out, n, "%d:0:0", (int)rc); return; }
    uint64_t hash = 1469598103934665603ull, frames = 0;
    int16_t buf[4096];
    const ma_uint32 ch = dec.outputChannels ? dec.outputChannels : 1;
    for (;;) {
        ma_uint64 got = 0;
        ma_decoder_read_pcm_frames(&dec, buf, 4096 / ch, &got);
        if (got == 0) break;
        frames += got;
        const unsigned char* p = reinterpret_cast<const unsigned char*>(buf);
        for (size_t i = 0; i < got * ch * sizeof(int16_t); ++i) { hash ^= p[i]; hash *= 1099511628211ull; }
    }
    ma_decoder_uninit(&dec);
    std::snprintf(out, n, "0:%llu:%016llx", (unsigned long long)frames, (unsigned long long)hash);
}

int main(int argc, char** argv)
{
    for (int i = 1; i < argc; ++i) {
        FILE* f = std::fopen(argv[i], "rb");
        if (!f) { std::printf("%s unreadable\n", argv[i]); return 2; }
        std::vector<unsigned char> bytes;
        unsigned char chunk[65536];
        size_t r;
        while ((r = std::fread(chunk, 1, sizeof chunk, f)) > 0) bytes.insert(bytes.end(), chunk, chunk + r);
        std::fclose(f);
        char g[64], w[64];
        decode(bytes, false, g, sizeof g);
        decode(bytes, true, w, sizeof w);
        std::printf("%s generic=%s wav=%s\n", argv[i], g, w);
    }
    return 0;
}
