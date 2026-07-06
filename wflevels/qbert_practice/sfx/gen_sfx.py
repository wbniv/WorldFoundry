#!/usr/bin/env python3
"""gen_sfx.py — generate placeholder Q*bert SFX (hop, land, fall) as 16-bit
mono WAVs at 22050 Hz. Stdlib only (wave + struct + math). Deterministic
output. Run from any cwd; writes alongside this script.

Replaces with authentic ROM-extracted samples in a future plan.
"""
import math
import os
import struct
import wave

SR = 22050   # sample rate
HERE = os.path.dirname(os.path.abspath(__file__))


def write_wav(path, samples_f):
    """Clip + quantize float samples to int16, write mono PCM WAV."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        clamped = (max(-1.0, min(1.0, s)) for s in samples_f)
        ints = (int(s * 32767) for s in clamped)
        # struct.pack one frame at a time would be slow; build chunks of 4096.
        buf = bytearray()
        for i, v in enumerate(ints):
            buf += struct.pack("<h", v)
            if (i & 4095) == 4095:
                w.writeframes(bytes(buf))
                buf.clear()
        if buf:
            w.writeframes(bytes(buf))
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


def env_attack_decay(n, attack_frac=0.05, decay_frac=0.30):
    """Linear attack then exponential decay envelope, length n samples."""
    a = max(1, int(n * attack_frac))
    for i in range(n):
        if i < a:
            yield i / a
        else:
            t = (i - a) / max(1, n - a)
            yield math.exp(-t / decay_frac)


def hop_boing(duration_s=0.18):
    """Rising sine sweep 250 → 520 Hz, attack-decay envelope, faint 2nd harmonic."""
    n = int(duration_s * SR)
    f0, f1 = 250.0, 520.0
    phase = 0.0
    env = list(env_attack_decay(n, 0.04, 0.55))
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        phase += 2 * math.pi * f / SR
        s = 0.65 * math.sin(phase) + 0.18 * math.sin(2 * phase)
        yield 0.55 * env[i] * s


def land_thud(duration_s=0.22):
    """Low-frequency thump (~70 Hz pulse) + brief noise tail, sharp attack."""
    n = int(duration_s * SR)
    f = 70.0
    env = list(env_attack_decay(n, 0.005, 0.18))
    # Cheap deterministic 'noise' = sin product chain — reproducible without random.
    for i in range(n):
        thump = math.sin(2 * math.pi * f * i / SR) * 0.8
        # Noisy tail decays faster
        noise_env = math.exp(-i / (n * 0.10))
        noise = math.sin(i * 0.273) * math.sin(i * 1.119) * math.sin(i * 0.039)
        s = thump + 0.35 * noise * noise_env
        yield 0.50 * env[i] * s


def fall_scream(duration_s=0.55):
    """Falling tone 480 → 110 Hz, square-ish wave for cartoon harshness."""
    n = int(duration_s * SR)
    f0, f1 = 480.0, 110.0
    phase = 0.0
    env = list(env_attack_decay(n, 0.02, 0.85))
    for i in range(n):
        t = i / n
        f = f0 * math.exp(math.log(f1 / f0) * t)   # exponential glide sounds more natural
        phase += 2 * math.pi * f / SR
        # Square-ish: clip a sine for cartoon feel
        s = math.sin(phase)
        s = max(-0.55, min(0.55, s * 1.6)) / 0.55
        yield 0.45 * env[i] * s


if __name__ == "__main__":
    os.chdir(HERE)
    write_wav("qbert_hop.wav",  list(hop_boing()))
    write_wav("qbert_land.wav", list(land_thud()))
    write_wav("qbert_fall.wav", list(fall_scream()))
