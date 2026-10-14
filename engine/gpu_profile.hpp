#pragma once

// Android GPU timing is opt-in. Other platforms and normal launches do no work.
namespace wf_gpu {
#if defined(__ANDROID__)
void enable();
bool enabled();
void beginFrame();
void beginGpu(int width, int height);
void endGpu();
void swapSample(double ms);
void endFrame();
void reset(bool contextLost = false);
double wallMs();
#else
inline void enable() {}
inline bool enabled() { return false; }
inline void beginFrame() {}
inline void beginGpu(int, int) {}
inline void endGpu() {}
inline void swapSample(double) {}
inline void endFrame() {}
inline void reset(bool = false) {}
inline double wallMs() { return 0; }
#endif
}
