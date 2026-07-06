#define TSF_IMPLEMENTATION
#define TML_IMPLEMENTATION
#include <tsf.h>
#include <tml.h>

#include <audio/music.hp>
#include <audio/linux/audio_internal.hp>
#include <hal/asset_accessor.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

MusicPlayer* gMusicPlayer = nullptr;

// Soundfont path. Resolved through HALGetAssetAccessor (POSIX cwd on
// desktop, AAssetManager on Android) so the same code path works on both
// platforms — we switched away from tsf_load_filename / tml_load_filename
// since Android assets live inside the APK, not on the filesystem.
#ifndef WF_MIDI_SOUNDFONT
#  define WF_MIDI_SOUNDFONT "florestan-subset.sf2"
#endif

// Default to a soft background volume. Can be overridden with setVolume.
static constexpr float kDefaultMusicVolume = 0.20f;

struct MusicPlayer::Impl {
	ma_data_source_base dsBase;         // must be first — ds_read casts pDs to Impl*
	tsf*          synth    = nullptr;
	tml_message*  midi     = nullptr;   // loaded MIDI sequence (heap, tml owns)
	tml_message*  cursor   = nullptr;   // current playback position
	double        msElapsed = 0.0;      // milliseconds into current playback
	ma_sound      sound;                // wraps the custom data source
	bool          soundInit = false;
	float         volume    = kDefaultMusicVolume;
	std::vector<uint8_t> midiBytes;     // tml_load_memory doesn't copy; keep alive.
};

// Load an asset into a byte vector via the platform AssetAccessor.
// Returns empty on failure.
static std::vector<uint8_t> loadAssetBytes(const char* path)
{
	std::vector<uint8_t> out;
	AssetAccessor& a = HALGetAssetAccessor();
	AssetHandle* h = a.OpenForRead(path);
	if (!h) return out;
	const int64_t size = a.Size(h);
	if (size > 0) {
		out.resize(static_cast<size_t>(size));
		const int64_t n = a.Read(h, out.data(), size);
		if (n != size) out.clear();
	}
	a.Close(h);
	return out;
}

// ── miniaudio custom data source callbacks ────────────────────────────────

static ma_result ds_read(ma_data_source* pDs, void* buf, ma_uint64 frameCount,
                          ma_uint64* pFramesRead)
{
	MusicPlayer::Impl* impl = (MusicPlayer::Impl*)pDs;
	if (!impl->synth || !impl->cursor) {
		memset(buf, 0, frameCount * 2 * sizeof(float));
		if (pFramesRead) *pFramesRead = frameCount;
		return MA_SUCCESS;
	}

	const int SAMPLE_RATE = 44100;
	const int CHANNELS    = 2;
	float* out = (float*)buf;

	ma_uint64 done = 0;
	while (done < frameCount) {
		// Advance MIDI events up to the current sample time
		double msPerFrame = 1000.0 / SAMPLE_RATE;
		while (impl->cursor && impl->cursor->time <= impl->msElapsed) {
			tml_message* msg = impl->cursor;
			switch (msg->type) {
				case TML_NOTE_ON:
					tsf_channel_note_on(impl->synth, msg->channel,
					                    msg->key, msg->velocity / 127.0f);
					break;
				case TML_NOTE_OFF:
					tsf_channel_note_off(impl->synth, msg->channel, msg->key);
					break;
				case TML_PITCH_BEND:
					tsf_channel_set_pitchwheel(impl->synth, msg->channel, msg->pitch_bend);
					break;
				case TML_CONTROL_CHANGE:
					tsf_channel_midi_control(impl->synth, msg->channel,
					                         msg->control, msg->control_value);
					break;
				case TML_PROGRAM_CHANGE:
					tsf_channel_set_presetnumber(impl->synth, msg->channel,
					                             msg->program, msg->channel == 9);
					break;
			}
			impl->cursor = msg->next;
		}

		// Render one frame
		tsf_render_float(impl->synth, out + done * CHANNELS, 1, 0);
		impl->msElapsed += msPerFrame;
		done++;

		// Loop when MIDI ends: reset voices but keep channel presets
		if (!impl->cursor) {
			impl->cursor    = impl->midi;
			impl->msElapsed = 0.0;
			tsf_reset(impl->synth);
			for (int ch = 0; ch < 16; ch++)
				tsf_channel_set_presetnumber(impl->synth, ch, 0, ch == 9);
		}
	}

	// Apply volume
	if (impl->volume < 0.999f) {
		ma_uint64 total = frameCount * CHANNELS;
		for (ma_uint64 i = 0; i < total; i++) out[i] *= impl->volume;
	}

	if (pFramesRead) *pFramesRead = frameCount;
	return MA_SUCCESS;
}

static ma_result ds_seek(ma_data_source*, ma_uint64) { return MA_NOT_IMPLEMENTED; }
// miniaudio's vtable uses size_t for the channel-map-size parameter; on
// Linux x86_64 the older ma_uint32 in this slot happens to work, but the
// NDK toolchain rejects the type mismatch. Use size_t everywhere.
static ma_result ds_get_format(ma_data_source*, ma_format* fmt, ma_uint32* ch,
                                ma_uint32* sr, ma_channel*, size_t)
{
	if (fmt) *fmt = ma_format_f32;
	if (ch)  *ch  = 2;
	if (sr)  *sr  = 44100;
	return MA_SUCCESS;
}
static ma_result ds_get_cursor(ma_data_source*, ma_uint64* c) { *c = 0; return MA_SUCCESS; }
static ma_result ds_get_length(ma_data_source*, ma_uint64* l) { *l = 0; return MA_NOT_IMPLEMENTED; }

static ma_data_source_vtable s_dsVtable = {
	ds_read, ds_seek, ds_get_format, ds_get_cursor, ds_get_length,
	nullptr, 0
};

// ── MusicPlayer ──────────────────────────────────────────────────────────

MusicPlayer::MusicPlayer() : _playing(false), _impl(nullptr)
{
	_impl = new Impl();
}

MusicPlayer::~MusicPlayer()
{
	stop();
	delete _impl;
}

bool MusicPlayer::play(const char* midiPath)
{
	stop();

	ma_engine* eng = ma_engine_get();
	if (!eng) return false;

	// Load soundfont (cached: reload only on first call)
	if (!_impl->synth) {
		auto sf = loadAssetBytes(WF_MIDI_SOUNDFONT);
		if (sf.empty()) {
			fprintf(stderr, "audio: MusicPlayer — soundfont not found: %s\n",
			        WF_MIDI_SOUNDFONT);
			return false;
		}
		_impl->synth = tsf_load_memory(sf.data(), static_cast<int>(sf.size()));
		if (!_impl->synth) {
			fprintf(stderr, "audio: MusicPlayer — soundfont parse failed: %s\n",
			        WF_MIDI_SOUNDFONT);
			return false;
		}
		tsf_set_output(_impl->synth, TSF_STEREO_INTERLEAVED, 44100, 0.0f);
		fprintf(stderr, "audio: MusicPlayer — soundfont loaded (%s, %zu B)\n",
		        WF_MIDI_SOUNDFONT, sf.size());
	}

	// GM default: pre-init all 16 channels so note-ons work without a
	// preceding program-change event (many simple MIDI files omit them).
	tsf_reset(_impl->synth);
	for (int ch = 0; ch < 16; ch++)
		tsf_channel_set_presetnumber(_impl->synth, ch, 0, ch == 9);

	// Load MIDI via AssetAccessor. tml_load_memory parses in-place without
	// copying; keep the byte buffer alive for the playback's lifetime in
	// _impl->midiBytes.
	_impl->midiBytes = loadAssetBytes(midiPath);
	if (_impl->midiBytes.empty()) {
		fprintf(stderr, "audio: MusicPlayer — MIDI not found: %s\n", midiPath);
		return false;
	}
	_impl->midi = tml_load_memory(_impl->midiBytes.data(),
	                              static_cast<int>(_impl->midiBytes.size()));
	if (!_impl->midi) {
		fprintf(stderr, "audio: MusicPlayer — MIDI parse failed: %s\n", midiPath);
		_impl->midiBytes.clear();
		return false;
	}
	_impl->cursor     = _impl->midi;
	_impl->msElapsed  = 0.0;

	// Init custom data source
	ma_data_source_config dsCfg = ma_data_source_config_init();
	dsCfg.vtable = &s_dsVtable;
	ma_data_source_init(&dsCfg, &_impl->dsBase);

	// Init and start sound using custom data source
	ma_uint32 flags = MA_SOUND_FLAG_NO_PITCH | MA_SOUND_FLAG_NO_SPATIALIZATION;
	ma_result r = ma_sound_init_from_data_source(eng, &_impl->dsBase, flags,
	                  ma_sfx_group_get(), &_impl->sound);
	if (r != MA_SUCCESS) {
		fprintf(stderr, "audio: MusicPlayer — sound init failed (%d)\n", r);
		tml_free(_impl->midi);
		_impl->midi = nullptr;
		return false;
	}
	ma_sound_set_volume(&_impl->sound, _impl->volume);
	ma_sound_start(&_impl->sound);
	_impl->soundInit = true;
	_playing = true;

	fprintf(stderr, "audio: MusicPlayer — playing %s\n", midiPath);
	return true;
}

void MusicPlayer::stop()
{
	if (_impl->soundInit) {
		ma_sound_stop(&_impl->sound);
		ma_sound_uninit(&_impl->sound);
		_impl->soundInit = false;
	}
	if (_impl->midi) {
		tml_free(_impl->midi);
		_impl->midi   = nullptr;
		_impl->cursor = nullptr;
	}
	_impl->midiBytes.clear();
	_impl->midiBytes.shrink_to_fit();
	if (_impl->synth) {
		tsf_reset(_impl->synth);
	}
	_impl->msElapsed = 0.0;
	_playing = false;
}

void MusicPlayer::setVolume(float v)
{
	_impl->volume = v;
	if (_impl->soundInit)
		ma_sound_set_volume(&_impl->sound, v);
}
