//==============================================================================
// pooltest.cc
// Copyright ( c ) 2026 World Foundry Group.
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

//==============================================================================
// Description:
// Regression guard for the pool-array / compiler-array-cookie bug that blocked
// the first macOS (arm64) run — see
// docs/plans/2026-09-20-macos-phase0-green-baseline.md fix 6.
//
// `new (pool) T[n]` on a T with a non-trivial destructor makes the compiler
// reserve a hidden prefix in front of the block, so the pointer it returns is
// NOT the pointer the pool's Allocate() handed out. That prefix is 8 bytes
// under the generic Itanium C++ ABI (x86_64) and 16 bytes under the ARM C++ ABI
// (every AArch64 target). MEMORY_DELETE_ARRAY used to hardcode the 8-byte form
// and so freed 8 bytes into the block on arm64, which tripped DMalloc's
// allocation-header cookie assert inside ~Room.
//
// The invariant that makes the alloc/free pair ABI-independent is simply:
//   the pointer MEMORY_NEW_ARRAY returns IS the pool allocation base.
// That is checkable on any host, so this test fails on x86_64 too if anyone
// reintroduces `new (pool) T[n]` — it does not need an arm64 box to bite.
//
// Run via `wf_game --memory-test` (ctest target `memory_pool_arrays`).
//==============================================================================

#include <memory/memory.hp>
#include <memory/dmalloc.hp>
#include <memory/lmalloc.hp>
#include <cpplib/int16li.hp>
#include <cstdio>
#include <cstddef>

//==============================================================================

namespace {

// A DMalloc that remembers the pointer its last Allocate() handed out, so the
// test can compare it against what the array helper returns.
class SpyDMalloc : public DMalloc
{
public:
	SpyDMalloc(Memory& parent, size_t size)
		: DMalloc(parent, size MEMORY_NAMED( COMMA "PoolArrayTest" ))
		, _lastAllocation(NULL)
	{
	}

	virtual void* Allocate(size_t size ASSERTIONS( COMMA const char* file COMMA int line))
	{
		_lastAllocation = DMalloc::Allocate(size ASSERTIONS( COMMA file COMMA line));
		return _lastAllocation;
	}

	void* LastAllocation() const { return _lastAllocation; }

private:
	void* _lastAllocation;
};

// Its one notable property is a non-trivial destructor — that, and nothing else,
// is what makes the compiler emit an array cookie for `new T[n]`. Used to
// *measure* this ABI's cookie rather than assume it.
struct CookieProbe
{
	int32 _pad;
	CookieProbe() : _pad(0) {}
	~CookieProbe() {}
};

}	// anonymous namespace

//==============================================================================

int
TestPoolArrays()
{
	int failures = 0;

	// LMalloc requires a WF_POINTER_ALIGN-aligned base; static (not stack) so a
	// 64 KB buffer doesn't depend on the platform's stack budget.
	alignas(16) static char backing[64000];
	LMalloc host(backing, sizeof(backing) MEMORY_NAMED( COMMA "PoolArrayTestHost" ));
	SpyDMalloc pool(host, 32000);

	const int kEntries = 5;		// what snowgoons' rooms actually use

	// --- 0. measure THIS ABI's array cookie, don't assume it -----------------
	// `new (pool) T[n]` on a non-trivially-destructible T prefixes the block
	// with a cookie whose size is ABI-defined. Measuring it costs nothing, runs
	// in every build on every host, and puts the number in the log of every CI
	// run — so the x86_64-vs-arm64 divergence that caused the 2026-09-20 bug is
	// visible as data rather than as a claim in a comment. Freed through the
	// pool base the spy recorded, which is exact whatever the cookie turns out
	// to be.
	{
		CookieProbe* probe = new (pool) CookieProbe[kEntries];
		void*  probeBase   = pool.LastAllocation();
		size_t cookie      = (size_t)((char*)probe - (char*)probeBase);

		printf("memory pool-array test: this ABI's compiler array cookie = %u bytes "
		       "(8 = generic Itanium / x86_64, 16 = ARM C++ ABI / arm64)\n",
		       (unsigned)cookie);

		for (int index = 0; index < kEntries; ++index)
			probe[index].~CookieProbe();
		pool.Free(probeBase);
	}

	// --- 1. the array helper must hand back the pool allocation base ---------
	// This is the invariant that makes MEMORY_NEW_ARRAY / MEMORY_DELETE_ARRAY
	// ABI-independent: no hidden prefix at all, so DELETE frees exactly what NEW
	// returned. It fails on any host — including x86_64, where the pre-fix code
	// happened to work — the moment someone reintroduces `new (pool) T[n]`.
	Int16List* lists = MEMORY_NEW_ARRAY(pool, Int16List, kEntries);
	void* base = pool.LastAllocation();

	if ((void*)lists != base)
	{
		printf("FAIL: pool array has a %td-byte hidden compiler array cookie — "
		       "MEMORY_NEW_ARRAY returned %p but the pool allocated %p. "
		       "MEMORY_DELETE_ARRAY frees the pointer it is given, so the block "
		       "would be freed at the wrong offset (this is the arm64 crash).\n",
		       (ptrdiff_t)((char*)lists - (char*)base), (void*)lists, base);
		++failures;
	}

	// --- 2. every element must be default-constructed ------------------------
	for (int index = 0; index < kEntries; ++index)
	{
		if (lists[index].Size() != 0)
		{
			printf("FAIL: pool array element %d was not default-constructed "
			       "(Size() = %d)\n", index, (int)lists[index].Size());
			++failures;
		}
	}

	// --- 3. full round trip, exactly as Room::Construct / ~Room do it --------
	for (int index = 0; index < kEntries; ++index)
		lists[index].Construct(pool, 200 + index);
	lists[0].Add(7);
	lists[0].Add(9);

	MEMORY_DELETE_ARRAY(pool, lists, Int16List, kEntries);

	// --- 4. the free must have been exact: same shape reuses the same base ---
	Int16List* again = MEMORY_NEW_ARRAY(pool, Int16List, kEntries);
	if ((void*)again != base)
	{
		printf("FAIL: re-allocating the same array shape returned %p, expected "
		       "%p — the previous MEMORY_DELETE_ARRAY did not release the whole "
		       "block\n", (void*)again, base);
		++failures;
	}
	// ~Int16List asserts on its Memory back-pointer, so Construct before tearing
	// down — same contract Room::Construct honours.
	for (int index = 0; index < kEntries; ++index)
		again[index].Construct(pool, 16);
	MEMORY_DELETE_ARRAY(pool, again, Int16List, kEntries);

	printf("memory pool-array test: %d failure(s)\n", failures);
	fflush(stdout);		// caller uses std::_Exit, which does not flush stdio
	return failures;
}

//==============================================================================
