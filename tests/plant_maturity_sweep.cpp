// Maturity sweep for the Planted Tank screensaver (docs/plans/2026-10-21-planted-tank-screensaver.md, Phase 0e).
// T(seed, water) = max over every vertex of every chunk of (birth + duration): the age at which the tank is fully grown.
// planted::tick clamps age at 240 s, so any T above that would never finish. Exits non-zero in that case.
#include <game/plant_growth.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>
namespace {
constexpr float kClamp = 240.f, kWarn = 200.f;
constexpr uint32_t kSeeds = 200, kDeterminismSeed = 713;
struct Result { float t; size_t vertices; };
Result measure(uint32_t seed, bool salt) {
 auto shoots = plantgrowth::colonies(seed, salt);
 auto chunks = plantgrowth::meshes(seed, salt, shoots);
 Result r{0.f, 0};
 for (const auto& c : chunks) for (const auto& v : c.vertices) { r.t = std::max(r.t, v.birth + v.duration); ++r.vertices; }
 return r;
}
float percentile(std::vector<float> s, double p) { std::sort(s.begin(), s.end()); size_t i = (size_t)std::ceil(p * s.size()); return s[i ? i - 1 : 0]; }
}
int main() {
 int rc = 0;
 std::printf("%-10s %7s %7s %7s %7s %6s %9s %9s %9s\n", "water", "min", "median", "p95", "max", "worst", "vtx_min", "vtx_max", ">200/>240");
 for (bool salt : {false, true}) {
  std::vector<float> ts; size_t vmin = SIZE_MAX, vmax = 0; uint32_t worst = 0; int over200 = 0, over240 = 0;
  for (uint32_t seed = 0; seed < kSeeds; ++seed) {
   Result r = measure(seed, salt); ts.push_back(r.t);
   vmin = std::min(vmin, r.vertices); vmax = std::max(vmax, r.vertices);
   if (r.t > ts[worst]) worst = seed;
   if (r.t > kWarn) ++over200;
   if (r.t > kClamp) { ++over240; std::printf("FAIL: seed %u %s T=%.2f exceeds the %.0f s growth clamp\n", seed, salt ? "saltwater" : "freshwater", r.t, kClamp); }
  }
  if (over240) rc = 1;
  std::printf("%-10s %7.2f %7.2f %7.2f %7.2f %6u %9zu %9zu %5d/%-3d\n", salt ? "saltwater" : "freshwater",
   percentile(ts, 0), percentile(ts, .5), percentile(ts, .95), percentile(ts, 1), worst, vmin, vmax, over200, over240);
  Result a = measure(kDeterminismSeed, salt), b = measure(kDeterminismSeed, salt);
  bool same = a.t == b.t && a.vertices == b.vertices;
  std::printf("  determinism seed %u: T=%.4f vertices=%zu, repeat T=%.4f vertices=%zu -> %s\n", kDeterminismSeed, a.t, a.vertices, b.t, b.vertices, same ? "identical" : "MISMATCH");
  if (!same) rc = 1;
 }
 std::printf(rc ? "RESULT: FAIL\n" : "RESULT: PASS (all T <= %.0f s)\n", kClamp);
 return rc;
}
