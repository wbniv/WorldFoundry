//=============================================================================
// gfx/glpipeline/static_mesh.cc: E3 phase 1 — static mesh buffers
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Bake each RenderObject3D once into a GPU buffer and, per frame, do only the
// part that depends on the camera: the back-face cull. Plan: finding-your-way
// docs/plans/2026-10-08-e3-static-vertex-buffers.md ("Phase 1").
//
// Parity by construction:
//  * Bake by recording. A recording RendererBackend is installed and the
//    object's normal per-face loop (StreamFaces) runs; the recorder keeps every
//    DrawTriangle call with the state current at that call. So the baked
//    triangles are exactly what the streaming path would send.
//  * Draw through the real batching. The static path makes the same state
//    calls per material run as StreamFaces, then hands the surviving triangle
//    numbers to DrawStaticTriangles, which joins the backend's own batch logic
//    (same flush boundaries, same uniforms, same submission order).
//  * Same cull. The decision comes from WfFaceIsBackfacing on the same floats
//    (gfx/backface_cull.hp), unless the measured `fast` form is selected.
//  * Translucent runs (opacity < 1) are not baked: they are streamed through
//    the compositing layer's sorted queue, in place, as before.
//
// What makes a bake stale, and what happens then:
//  * content: the primitives were rebuilt (ApplyMaterials bumps a version:
//    SetMaterialColor, the scarecrow flipbook), a material's flags, opacity or
//    palette changed, or the face/vertex/primitive/material arrays moved
//    -> re-bake; a second content invalidation demotes the object to
//    streaming for good (STATIC_CHURN), since re-baking per frame costs more
//    than streaming.
//  * environment: VRAM texture placement changed (StaticMeshAtlasChanged), or
//    the GL context was lost (StaticMeshLive) -> re-bake, not counted as churn.
//  * never baked: writable vertices were handed out (animation, fish, fins,
//    jelly, lion), runtime geometry (plants), copy-constructed objects that
//    share data (particles), or no opaque run at all.
//
// Memory: the engine's pools cannot hold the persistent part. HALLmalloc is an
// LMalloc, a stack: Free(p) releases p and everything allocated after it, so a
// block that must outlive later allocations (a bake made lazily mid-frame, and
// freed whenever its object dies) cannot live there; HALDmalloc, the one
// general-purpose pool, is 1000 bytes. So the persistent per-object
// bookkeeping (run table, plus one float per baked face only when the fast cull
// is selected) and the scratch list of surviving triangles come from the C++
// heap, and every byte is counted (StaticMeshCpuBytes, the static-cpu-bytes
// frame counter). The transient recording does use HALLmalloc, allocated and
// freed in strict LIFO order inside one call. No CPU copy of the packed
// vertices is kept (except in the self-check mode).
//============================================================================

#include <gfx/static_mesh.hp>
#include <gfx/rendobj3.hp>
#include <gfx/material.hp>
#include <gfx/renderer_backend.hp>
#include <gfx/backface_cull.hp>
#include <game/runtime_profile.hp>
#include <hal/halbase.h>
#include <memory/lmalloc.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>

extern RendererVariables globalRendererVariables;

//============================================================================
// Switch, cull selection, atlas generation, accounting

namespace
{
	int sSwitchOverride = -1;			// -1 = not given on the command line
	int sFastCullOverride = -1;
	int sSharedIndexOverride = -1;
	int sBakeBudgetOverride = -1;
	int32 sBakedFacesThisFrame = 0;
	unsigned sAtlasGeneration = 1;
	size_t sCpuBytes = 0;

	unsigned* sScratch = NULL;			// surviving triangle numbers of one run
	int sScratchCapacity = 0;

	bool
	EnvFlag(const char* name, bool fallback)
	{
		const char* e = getenv(name);
		return e ? atoi(e) != 0 : fallback;
	}

	bool
	FastCull()
	{
		static const bool fast = []() {
			if(sFastCullOverride >= 0)
				return sFastCullOverride != 0;
			const char* e = getenv("WF_STATIC_MESH_CULL");
			return e && strcmp(e, "fast") == 0;
		}();
		return fast;
	}

	int32
	BakeBudget()
	{
		static const int32 budget = []() {
			if(sBakeBudgetOverride >= 0)
				return int32(sBakeBudgetOverride);
			const char* e = getenv("WF_STATIC_MESH_BAKE_BUDGET");
			return e ? int32(atoi(e)) : int32(4000);
		}();
		return budget;
	}

	bool
	CheckMode()
	{
		static const bool check = EnvFlag("WF_STATIC_MESH_CHECK", false);
		return check;
	}

	// Transient, strictly LIFO (HALLmalloc is a stack allocator).
	void*
	TransientAllocate(size_t bytes)
	{
		return HALLmalloc.Allocate(bytes ASSERTIONS(COMMA __FILE__ COMMA __LINE__));
	}

	void
	TransientFree(void* block)
	{
		HALLmalloc.Free(block);
	}

	unsigned*
	Scratch(int count)
	{
		if(count > sScratchCapacity)
		{
			if(sScratch)
			{
				free(sScratch);
				sCpuBytes -= size_t(sScratchCapacity) * sizeof(unsigned);
			}
			sScratchCapacity = count < 1024 ? 1024 : count;
			sScratch = static_cast<unsigned*>(malloc(size_t(sScratchCapacity) * sizeof(unsigned)));
			assert(ValidPtr(sScratch));
			sCpuBytes += size_t(sScratchCapacity) * sizeof(unsigned);
		}
		return sScratch;
	}

	// Self-check totals (WF_STATIC_MESH_CHECK=1), printed once at exit.
	struct CheckTotals
	{
		unsigned long objectDraws, triangles, triangleMismatches;
		unsigned long cullFaces, cullExactMismatches;
		unsigned long fastFaces, fastMismatches, nonSimilarDraws;
		unsigned long atlasChanges, atlasRebakes, atlasRebakeChangedTriangles;
	unsigned long simulatedLosses, liveBakesAtExit;
	};
	long sLiveBakes = 0;
	CheckTotals sCheck = {};

	void
	PrintCheckTotals()
	{
		fprintf(stderr, "static-mesh-check: object-draws=%lu triangles=%lu triangle-mismatches=%lu "
		        "cull-faces=%lu cull-exact-mismatches=%lu fast-faces=%lu fast-mismatches=%lu "
		        "non-similar-draws=%lu atlas-changes=%lu atlas-rebakes=%lu atlas-rebake-changed-triangles=%lu "
		        "simulated-losses=%lu live-bakes=%ld cpu-bytes=%zu\n",
		        sCheck.objectDraws, sCheck.triangles, sCheck.triangleMismatches,
		        sCheck.cullFaces, sCheck.cullExactMismatches, sCheck.fastFaces, sCheck.fastMismatches,
		        sCheck.nonSimilarDraws, sCheck.atlasChanges, sCheck.atlasRebakes, sCheck.atlasRebakeChangedTriangles,
		        sCheck.simulatedLosses, sLiveBakes, sCpuBytes);
	}

	bool
	SameBits(float a, float b)
	{
		return memcmp(&a, &b, sizeof(float)) == 0;
	}

	bool
	SameTriangle(const RBStaticTriangle& a, const RBStaticTriangle& b)
	{
		for(int k = 0; k < 3; ++k)
		{
			const RBVertex& x = a.v[k];
			const RBVertex& y = b.v[k];
			if(!SameBits(x.x, y.x) || !SameBits(x.y, y.y) || !SameBits(x.z, y.z)
			   || !SameBits(x.r, y.r) || !SameBits(x.g, y.g) || !SameBits(x.b, y.b)
			   || !SameBits(x.u, y.u) || !SameBits(x.v, y.v))
				return false;
		}
		return SameBits(a.nx, b.nx) && SameBits(a.ny, b.ny) && SameBits(a.nz, b.nz)
		    && SameBits(a.opacity, b.opacity)
		    && a.paletteDark == b.paletteDark && a.paletteLight == b.paletteLight
		    && a.paletteEnabled == b.paletteEnabled;
	}
}

void
StaticMeshSetSwitch(bool on)
{
	sSwitchOverride = on ? 1 : 0;
}

bool
StaticMeshEnabled()
{
	static const bool enabled = []() {
		if(sSwitchOverride >= 0)
			return sSwitchOverride != 0;
		return EnvFlag("WF_STATIC_MESH", true);		// default ON (Will, 2026-10-08)
	}();
	return enabled;
}

bool StaticMeshFastCullEnabled() { return FastCull(); }
int StaticMeshBakeBudget() { return BakeBudget(); }

void
StaticMeshSetFastCull(bool fast)
{
	sFastCullOverride = fast ? 1 : 0;
}

void
StaticMeshSetSharedIndex(bool on)
{
	sSharedIndexOverride = on ? 1 : 0;
}

bool
StaticMeshSharedIndex()
{
	static const bool shared = sSharedIndexOverride >= 0
		? sSharedIndexOverride != 0 : EnvFlag("WF_STATIC_MESH_SHARED_INDEX", true);
	return shared;
}

void
StaticMeshAtlasChanged()
{
	++sAtlasGeneration;
	++sCheck.atlasChanges;
}

size_t
StaticMeshCpuBytes()
{
	return sCpuBytes;
}

void
StaticMeshSetBakeBudget(int faces)
{
	sBakeBudgetOverride = faces < 0 ? 0 : faces;
}

void
StaticMeshSampleGauges()
{
	size_t gpu = 0, staging = 0;
	RendererBackendGet().StaticMeshBytes(gpu, staging);
	wf_profile::count(wf_profile::StaticGpuBytes, gpu);
	wf_profile::count(wf_profile::StaticCpuBytes, sCpuBytes + staging);
}

bool
StaticMeshEndFrame()
{
	sBakedFacesThisFrame = 0;
	static const char* test = getenv("WF_STATIC_MESH_TEST");
	static unsigned long frame = 0;
	++frame;
	if(!test)
		return false;
	if(strncmp(test, "atlas:", 6) == 0)
	{
		const unsigned long every = strtoul(test + 6, NULL, 10);
		if(every && frame % every == 0)
			StaticMeshAtlasChanged();
	}
	else if(strncmp(test, "loss:", 5) == 0 && frame == strtoul(test + 5, NULL, 10))
	{
		++sCheck.simulatedLosses;
		return true;
	}
	return false;
}

//============================================================================
// The recorder: what the eight renderers submit for one object, with the
// backend state each triangle would have been packed under.

struct RecordedFace
{
	const PixelMap* texture;
	uint8 cullExempt, prelit, alphaCutout, modulate;
};

namespace
{
	class StaticMeshRecorder : public RendererBackend
	{
	public:
		StaticMeshRecorder(RendererBackend& real, RBStaticTriangle* triangles, RecordedFace* faces, int capacity)
			: _real(real), _triangles(triangles), _faces(faces), _capacity(capacity) {}

		int Count() const { return _count; }
		bool Overflowed() const { return _overflowed; }

		void SetProjection(float, float, float, float) override {}
		void SetModelView(const Matrix34&) override {}
		void ResetModelView() override {}
		void SetAmbient(float, float, float) override {}
		void SetDirLight(int, float, float, float, float, float, float) override {}
		void SetLightingEnabled(bool) override {}
		void SetFog(float, float, float, float, float) override {}
		void SetFogEnabled(bool) override {}
		void SetAlphaCutout(bool enabled) override { _alphaCutout = enabled; }
		void SetTextureModulation(bool enabled) override { _modulate = enabled; }
		void SetTexturePalette(bool enabled, unsigned dark, unsigned light) override
		{ _paletteEnabled = enabled; _paletteDark = dark; _paletteLight = light; }
		void SetOpacity(float opacity) override { _opacity = opacity; }
		void EndFrame() override {}
		RBTextureHandle CreateTexture(int w, int h, RBTextureFormat f, const void* p) override
		{ return _real.CreateTexture(w, h, f, p); }
		void DestroyTexture(RBTextureHandle handle) override { _real.DestroyTexture(handle); }

		void DrawTriangle(const RBVertex& v0, const RBVertex& v1, const RBVertex& v2,
		                  float nx, float ny, float nz, const PixelMap* texture,
		                  bool cullExempt, bool prelit) override
		{
			if(_count >= _capacity)
			{
				_overflowed = true;
				return;
			}
			RBStaticTriangle& t = _triangles[_count];
			t.v[0] = v0; t.v[1] = v1; t.v[2] = v2;
			t.nx = nx; t.ny = ny; t.nz = nz;
			// What the GL backend packs: the compositing layer hands opaque
			// triangles on with opacity 1 (translucent runs are never baked).
			t.opacity = _opacity;
			t.paletteDark = _paletteDark;
			t.paletteLight = _paletteLight;
			t.paletteEnabled = _paletteEnabled ? 1 : 0;
			RecordedFace& f = _faces[_count];
			f.texture = texture;
			f.cullExempt = cullExempt;
			f.prelit = prelit;
			f.alphaCutout = _alphaCutout;
			f.modulate = _modulate;
			++_count;
		}

	private:
		RendererBackend& _real;
		RBStaticTriangle* _triangles;
		RecordedFace* _faces;
		int _capacity;
		int _count = 0;
		bool _overflowed = false;
		float _opacity = 1.0f;
		bool _alphaCutout = false, _modulate = false, _paletteEnabled = false;
		unsigned _paletteDark = 0, _paletteLight = 0xffffff;
	};
}

//============================================================================
// The bake

struct StaticMeshGroup
{
	int32 firstFace, endFace;			// faces [firstFace, endFace) of the face list
	int32 firstTriangle;				// its first triangle in the static mesh; -1 = streamed
	int32 materialIndex;
	int32 materialFlags;				// snapshot, compared at every draw
	float opacity;
	uint32 paletteDark, paletteLight;
	const PixelMap* texture;
	uint8 prelit, cullExempt, paletteEnabled;
};

struct StaticMeshBake
{
	RBStaticMeshHandle mesh;
	const TriFace* faceList;
	const Vertex3D* vertexList;
	const Primitive* primList;
	const Material* materialList;
	int32 faceCount;
	int32 groupCount;
	int32 triangleCount;
	int32 largestGroup;
	uint32 atlasGeneration;
	uint16 version;
	StaticMeshGroup* groups;			// same allocation, after this struct
	float* planeD;						// per baked triangle; fast cull or check mode only
	RBStaticTriangle* check;			// check mode only: the recording, kept
	size_t bytes;						// main RAM held (all of the above)
};

namespace
{
	enum { STALE_NONE = 0, STALE_CONTENT, STALE_ENVIRONMENT };

	bool
	RecordObject(RenderObject3D& object, void (RenderObject3D::*stream)(int,int), int faceCount,
	             RBStaticTriangle* triangles, RecordedFace* faces)
	{
		StaticMeshRecorder recorder(RendererBackendGet(), triangles, faces, faceCount);
		RendererBackendSetRecorder(&recorder);
		(object.*stream)(0, faceCount);
		RendererBackendSetRecorder(NULL);
		// Every face makes exactly one DrawTriangle call (each renderer ends in
		// one); anything else means a renderer we do not understand.
		return !recorder.Overflowed() && recorder.Count() == faceCount;
	}
}

bool
RenderObject3D::BakeStatic()
{
	assert(_staticBake == NULL);
	const double started = wf_profile::cpu_ms();
	const int32 faceCount = _faceCount;

	// Transient recording (LIFO: triangles, then faces; freed in reverse at
	// the single exit below).
	RBStaticTriangle* triangles = static_cast<RBStaticTriangle*>(TransientAllocate(size_t(faceCount) * sizeof(RBStaticTriangle)));
	RecordedFace* faces = static_cast<RecordedFace*>(TransientAllocate(size_t(faceCount) * sizeof(RecordedFace)));
	assert(ValidPtr(triangles) && ValidPtr(faces));		// LMalloc is fatal when exhausted
	StaticMeshBake* bake = BakeFromRecording(triangles, faces);
	TransientFree(faces);
	TransientFree(triangles);
	if(!bake)
		return false;

	bake->faceList = _faceList;
	bake->vertexList = _vertexList;
	bake->primList = _primList[0];
	bake->materialList = _materialList;
	bake->faceCount = _faceCount;
	bake->atlasGeneration = sAtlasGeneration;
	bake->version = _staticVersion;
	_staticBake = bake;
	sCpuBytes += bake->bytes;
	++sLiveBakes;

	wf_profile::count(wf_profile::StaticBakes);
	wf_profile::count(wf_profile::StaticBakeUs, (unsigned long)((wf_profile::cpu_ms() - started) * 1000.0 + 0.5));
	return true;
}

//============================================================================
// Builds the bake from one recording; NULL (with _staticState set) when the
// object cannot be baked. Owns no transient memory.

StaticMeshBake*
RenderObject3D::BakeFromRecording(RBStaticTriangle* triangles, RecordedFace* faces)
{
	const int32 faceCount = _faceCount;
	if(!RecordObject(*this, &RenderObject3D::StreamFaces, faceCount, triangles, faces))
	{
		_staticState = STATIC_UNBAKEABLE;
		return NULL;
	}

	// Material runs, exactly as StreamFaces walks them.
	int32 groupCount = 0;
	for(int32 f = 0; f < faceCount; ++f)
		if(f == 0 || _faceList[f].materialIndex != _faceList[f-1].materialIndex)
			++groupCount;

	const size_t bakeBytes = sizeof(StaticMeshBake) + size_t(groupCount) * sizeof(StaticMeshGroup);
	StaticMeshBake* bake = static_cast<StaticMeshBake*>(malloc(bakeBytes));
	if(!bake)
	{
		_staticState = STATIC_UNBAKEABLE;
		return NULL;
	}
	memset(bake, 0, bakeBytes);
	bake->groups = reinterpret_cast<StaticMeshGroup*>(bake + 1);
	bake->groupCount = groupCount;
	bake->bytes = bakeBytes;

	// Fill the runs, check that the state is constant inside each (it is set
	// per material run; a renderer that varied it per face could not be
	// drawn as one run), and pack the opaque runs' triangles to the front,
	// in face order.
	bool consistent = true;
	int32 out = 0, group = -1;
	for(int32 f = 0; f < faceCount && consistent; ++f)
	{
		if(f == 0 || _faceList[f].materialIndex != _faceList[f-1].materialIndex)
		{
			StaticMeshGroup& g = bake->groups[++group];
			const Material& mat = _materialList[_faceList[f].materialIndex];
			g.firstFace = f;
			g.endFace = f;
			g.materialIndex = _faceList[f].materialIndex;
			g.materialFlags = mat.GetMaterialFlags();
			g.opacity = triangles[f].opacity;
			g.paletteDark = triangles[f].paletteDark;
			g.paletteLight = triangles[f].paletteLight;
			g.texture = faces[f].texture;
			g.prelit = faces[f].prelit;
			g.cullExempt = faces[f].cullExempt;
			g.paletteEnabled = uint8(triangles[f].paletteEnabled);
			// Opaque exactly when the compositing layer would pass it straight on.
			g.firstTriangle = (g.opacity >= 1) ? out : -1;
			// The recorded state must be the material's (what the snapshot checks).
			consistent = g.opacity == mat.GetOpacity()
				&& g.paletteDark == mat.PaletteDark() && g.paletteLight == mat.PaletteLight();
		}
		StaticMeshGroup& g = bake->groups[group];
		const RecordedFace& first = faces[g.firstFace];
		const RecordedFace& face = faces[f];
		consistent = consistent && face.texture == first.texture && face.prelit == first.prelit
			&& face.cullExempt == first.cullExempt && face.alphaCutout == first.alphaCutout
			&& face.modulate == first.modulate
			&& SameBits(triangles[f].opacity, g.opacity)
			&& triangles[f].paletteDark == g.paletteDark && triangles[f].paletteLight == g.paletteLight
			&& triangles[f].paletteEnabled == g.paletteEnabled;
		g.endFace = f + 1;
		if(g.firstTriangle >= 0)
		{
			if(out != f)
				triangles[out] = triangles[f];
			++out;
		}
	}
	if(consistent)
		for(int32 i = 0; i < groupCount; ++i)
		{
			const int32 size = bake->groups[i].endFace - bake->groups[i].firstFace;
			if(bake->groups[i].firstTriangle >= 0 && size > bake->largestGroup)
				bake->largestGroup = size;
		}

	if(!consistent || out == 0)
	{
		free(bake);
		_staticState = consistent ? STATIC_NO_OPAQUE : STATIC_UNBAKEABLE;
		return NULL;
	}
	bake->triangleCount = out;

	if(FastCull() || CheckMode())
	{
		bake->planeD = static_cast<float*>(malloc(size_t(out) * sizeof(float)));
		assert(ValidPtr(bake->planeD));
		for(int32 t = 0; t < out; ++t)
		{
			const RBStaticTriangle& tri = triangles[t];
			bake->planeD[t] = WfFacePlaneD(tri.nx, tri.ny, tri.nz,
				tri.v[0].x, tri.v[0].y, tri.v[0].z, tri.v[1].x, tri.v[1].y, tri.v[1].z,
				tri.v[2].x, tri.v[2].y, tri.v[2].z);
		}
		bake->bytes += size_t(out) * sizeof(float);
	}

	bake->mesh = RendererBackendGet().CreateStaticMesh(triangles, out);
	if(!bake->mesh)
	{
		free(bake->planeD);
		free(bake);
		_staticState = STATIC_UNBAKEABLE;
		return NULL;
	}

	if(CheckMode())
	{
		// Debug only: keep the recording to compare against at every draw.
		bake->check = static_cast<RBStaticTriangle*>(malloc(size_t(out) * sizeof(RBStaticTriangle)));
		assert(ValidPtr(bake->check));
		memcpy(bake->check, triangles, size_t(out) * sizeof(RBStaticTriangle));
		bake->bytes += size_t(out) * sizeof(RBStaticTriangle);
	}
	return bake;
}

//============================================================================

void
RenderObject3D::StaticMeshDiscard()
{
	StaticMeshBake* bake = _staticBake;
	if(!bake)
		return;
	_staticBake = NULL;
	RendererBackendGet().DestroyStaticMesh(bake->mesh);
	sCpuBytes -= bake->bytes;
	--sLiveBakes;
	free(bake->planeD);
	free(bake->check);
	free(bake);
}

//============================================================================

int
RenderObject3D::StaticBakeStale() const
{
	const StaticMeshBake& bake = *_staticBake;
	if(bake.version != _staticVersion || bake.faceList != _faceList || bake.vertexList != _vertexList
	   || bake.primList != _primList[0] || bake.materialList != _materialList || bake.faceCount != _faceCount)
		return STALE_CONTENT;
	for(int32 i = 0; i < bake.groupCount; ++i)
	{
		const StaticMeshGroup& g = bake.groups[i];
		const Material& mat = _materialList[g.materialIndex];
		if(mat.GetMaterialFlags() != g.materialFlags || mat.GetOpacity() != g.opacity
		   || mat.PaletteDark() != g.paletteDark || mat.PaletteLight() != g.paletteLight)
			return STALE_CONTENT;
	}
	if(bake.atlasGeneration != sAtlasGeneration)
		return STALE_ENVIRONMENT;
	if(!RendererBackendGet().StaticMeshLive(bake.mesh))
		return STALE_ENVIRONMENT;
	return STALE_NONE;
}

//============================================================================

bool
RenderObject3D::RenderStatic(const Matrix34& position)
{
	if(!StaticMeshEnabled())
		return false;
	if(_staticState != STATIC_BAKEABLE)
	{
		if(_staticBake)
			StaticMeshDiscard();
		wf_profile::count(wf_profile::StaticExcludedObjects);
		return false;
	}
	RendererBackend& backend = RendererBackendGet();
	if(!backend.StaticMeshSupported())
		return false;

	if(_staticBake)
	{
		const int stale = StaticBakeStale();
		if(stale != STALE_NONE)
		{
			if(CheckMode() && stale == STALE_ENVIRONMENT && _staticBake->atlasGeneration != sAtlasGeneration)
			{
				// Was this rebake needed? Record now and count the baked
				// triangles a room change actually altered (e.g. UVs).
				RBStaticTriangle* now = static_cast<RBStaticTriangle*>(TransientAllocate(size_t(_faceCount) * sizeof(RBStaticTriangle)));
				RecordedFace* faces = static_cast<RecordedFace*>(TransientAllocate(size_t(_faceCount) * sizeof(RecordedFace)));
				const bool recorded = RecordObject(*this, &RenderObject3D::StreamFaces, _faceCount, now, faces);
				const StaticMeshBake& old = *_staticBake;
				++sCheck.atlasRebakes;
				for(int32 i = 0; i < old.groupCount; ++i)
					for(int32 f = old.groups[i].firstFace; old.groups[i].firstTriangle >= 0 && f < old.groups[i].endFace; ++f)
						if(!recorded || !SameTriangle(now[f], old.check[old.groups[i].firstTriangle + (f - old.groups[i].firstFace)]))
							++sCheck.atlasRebakeChangedTriangles;
				TransientFree(faces);		// LIFO
				TransientFree(now);
			}
			StaticMeshDiscard();
			if(stale == STALE_CONTENT && ++_staticInvalidations >= 2)
			{
				_staticState = STATIC_CHURN;
				wf_profile::count(wf_profile::StaticExcludedObjects);
				return false;
			}
		}
	}
	if(!_staticBake)
	{
		const int32 budget = BakeBudget();
		if(budget > 0 && sBakedFacesThisFrame > 0 && sBakedFacesThisFrame + _faceCount > budget)
		{
			wf_profile::count(wf_profile::StaticDeferredObjects);
			return false;				// stream this frame, bake on a later one
		}
		sBakedFacesThisFrame += _faceCount;
		if(!BakeStatic())
		{
			wf_profile::count(wf_profile::StaticExcludedObjects);
			return false;
		}
	}
	const StaticMeshBake& bake = *_staticBake;

	float mv[16];
	WfMatrix34ToGL(position, mv);
	const bool cull = WfBackfaceCullEnabled();
	WfCullFrame frame;
	WfCullFramePrepare(mv, frame);
	const bool fast = cull && FastCull() && frame.similarity;

	if(CheckMode())
	{
		// Re-record now, under this frame's matrix and globals, and compare
		// with the bake: the triangles, the static path's cull input (the
		// resident vertices) against DrawTriangle's (the recorded ones), and
		// the fast form against the exact one.
		RBStaticTriangle* now = static_cast<RBStaticTriangle*>(TransientAllocate(size_t(_faceCount) * sizeof(RBStaticTriangle)));
		RecordedFace* faces = static_cast<RecordedFace*>(TransientAllocate(size_t(_faceCount) * sizeof(RecordedFace)));
		assert(ValidPtr(now) && ValidPtr(faces));
		const bool recorded = RecordObject(*this, &RenderObject3D::StreamFaces, _faceCount, now, faces);
		static const bool registered = (atexit(PrintCheckTotals) == 0);
		(void)registered;
		++sCheck.objectDraws;
		if(!frame.similarity)
			++sCheck.nonSimilarDraws;
		for(int32 i = 0; i < bake.groupCount; ++i)
		{
			const StaticMeshGroup& g = bake.groups[i];
			if(g.firstTriangle < 0)
				continue;
			for(int32 f = g.firstFace; f < g.endFace; ++f)
			{
				const int32 t = g.firstTriangle + (f - g.firstFace);
				++sCheck.triangles;
				if(!recorded || !SameTriangle(now[f], bake.check[t]))
					++sCheck.triangleMismatches;
				if(g.cullExempt || !recorded)
					continue;
				const TriFace& face = _faceList[f];
				const Vector3& p0 = _vertexList[face.v1Index].position;
				const Vector3& p1 = _vertexList[face.v2Index].position;
				const Vector3& p2 = _vertexList[face.v3Index].position;
				const bool mine = WfFaceIsBackfacing(mv, face.normal.X().AsFloat(), face.normal.Y().AsFloat(), face.normal.Z().AsFloat(),
					p0.X().AsFloat(), p0.Y().AsFloat(), p0.Z().AsFloat(), p1.X().AsFloat(), p1.Y().AsFloat(), p1.Z().AsFloat(),
					p2.X().AsFloat(), p2.Y().AsFloat(), p2.Z().AsFloat());
				const RBStaticTriangle& r = now[f];
				const bool streaming = WfFaceIsBackfacing(mv, r.nx, r.ny, r.nz,
					r.v[0].x, r.v[0].y, r.v[0].z, r.v[1].x, r.v[1].y, r.v[1].z, r.v[2].x, r.v[2].y, r.v[2].z);
				++sCheck.cullFaces;
				if(mine != streaming)
					++sCheck.cullExactMismatches;
				if(frame.similarity)
				{
					++sCheck.fastFaces;
					if(WfFaceIsBackfacingFast(frame, r.nx, r.ny, r.nz, bake.planeD[t]) != streaming)
						++sCheck.fastMismatches;
				}
			}
		}
		TransientFree(faces);		// LIFO
		TransientFree(now);
	}

	unsigned* surviving = Scratch(bake.largestGroup);
	for(int32 i = 0; i < bake.groupCount; ++i)
	{
		const StaticMeshGroup& g = bake.groups[i];
		if(g.firstTriangle < 0)
		{
			// Translucent run: stream it in place, through the sorted queue.
			StreamFaces(g.firstFace, g.endFace);
			continue;
		}
		// The state calls StreamFaces makes at the start of a material run.
		const Material& mat = _materialList[g.materialIndex];
		mat.Validate();
		backend.SetAlphaCutout(mat.IsAlphaCutout());
		backend.SetTextureModulation((mat.GetMaterialFlags() & Material::TEXTURE_MODULATE) != 0);
		backend.SetTexturePalette((mat.GetMaterialFlags() & Material::TEXTURE_PALETTE) != 0, mat.PaletteDark(), mat.PaletteLight());
		// The renderers set this before every triangle; one call per run leaves
		// the compositing layer in the same state.
		backend.SetOpacity(g.opacity);

		int32 count = 0, culled = 0;
		const TriFace* face = _faceList + g.firstFace;
		unsigned triangle = unsigned(g.firstTriangle);
		if(!cull || g.cullExempt)
		{
			for(int32 f = g.firstFace; f < g.endFace; ++f)
				surviving[count++] = triangle++;
		}
		else if(fast)
		{
			const float* planeD = bake.planeD;
			for(int32 f = g.firstFace; f < g.endFace; ++f, ++face, ++triangle)
			{
				if(WfFaceIsBackfacingFast(frame, face->normal.X().AsFloat(), face->normal.Y().AsFloat(),
				                          face->normal.Z().AsFloat(), planeD[triangle]))
					++culled;
				else
					surviving[count++] = triangle;
			}
		}
		else
		{
			for(int32 f = g.firstFace; f < g.endFace; ++f, ++face, ++triangle)
			{
				const Vector3& p0 = _vertexList[face->v1Index].position;
				const Vector3& p1 = _vertexList[face->v2Index].position;
				const Vector3& p2 = _vertexList[face->v3Index].position;
				if(WfFaceIsBackfacing(mv, face->normal.X().AsFloat(), face->normal.Y().AsFloat(), face->normal.Z().AsFloat(),
				                      p0.X().AsFloat(), p0.Y().AsFloat(), p0.Z().AsFloat(),
				                      p1.X().AsFloat(), p1.Y().AsFloat(), p1.Z().AsFloat(),
				                      p2.X().AsFloat(), p2.Y().AsFloat(), p2.Z().AsFloat()))
					++culled;
				else
					surviving[count++] = triangle;
			}
		}
		wf_profile::count(wf_profile::FacesSubmitted, (unsigned long)(g.endFace - g.firstFace));
		wf_profile::count(wf_profile::FacesCulled, (unsigned long)culled);
		wf_profile::count(wf_profile::StaticFacesCulled, (unsigned long)culled);
		backend.DrawStaticTriangles(bake.mesh, surviving, count, g.texture, g.prelit != 0);
	}
	wf_profile::count(wf_profile::StaticObjects);
	return true;
}

//============================================================================
