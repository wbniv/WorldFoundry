// The four-lane static cull kernel (gfx/backface_cull_neon.hp) against the
// scalar test, on the lanes model: every run length 0-24 (so every tail 0-3
// after whole groups of four, and tails 0-7 of the plan), random matrices,
// faces moved edge-on, NaN, and denormal inputs and products. The model runs
// the kernel's lane, compaction and tail code with scalar arithmetic; the real
// NEON lanes run only on 32-bit ARM, under --static-mesh-check on the device.
#include <gfx/backface_cull_neon.hp>
#include <cstdio>

int main()
{
	WfCullSelfTest r = {};
	WfCullKernelSelfTest<WfLanes4Model>(r);
	std::printf("backface_cull_kernel: lanes=model runs=%lu faces=%lu mismatches=%lu edge-runs=%lu edge-mismatches=%lu "
	            "nan-runs=%lu nan-mismatches=%lu denormal-runs=%lu denormal-mismatches=%lu\n",
	            r.runs, r.faces, r.mismatches, r.edgeRuns, r.edgeMismatches,
	            r.nanRuns, r.nanMismatches, r.denormalRuns, r.denormalMismatches);
	const bool ok = r.runs && r.edgeRuns > 1000 && r.nanRuns && r.denormalRuns
		&& !r.mismatches && !r.edgeMismatches && !r.nanMismatches && !r.denormalMismatches;
	std::puts(ok ? "backface_cull_kernel: PASS" : "backface_cull_kernel: FAIL");
	return ok ? 0 : 1;
}
