//=============================================================================
// RenderObject3D.cc: 3D renderable object
// Copyright ( c ) 1997,1998,1999,2000,2001,2002 World Foundry Group  
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

// ===========================================================================
// Description:
//
// Original Author: Kevin T. Seghetti
//============================================================================

#include <hal/hal.h>
#include <cstdio>
#include <gfx/rendobj3.hp>
#include <math/vector3.hp>
#include <iff/iffread.hp>
#include "handle.hp"
#include "material.hp"
#include "callbacks.hp"


	#include <gfx/glpipeline/rendobj3.cc>

#include <cstdlib>
#include <cstring>
#include <unordered_map>

//============================================================================
// Shared model geometry v1 (finding-your-way
// docs/plans/2026-10-17-texture-variant-mesh-sharing.md, "Exporter finding and
// the v1 format"). A GREF appearance's positions and faces live in a GEOM
// asset that several appearances name; each appearance keeps its own UVCL
// (u, v, colour per geometry vertex), MATL and optional OPAC/HNDL.
//
// What is shared, and why it cannot dangle:
//  - The record below holds the positions and the material-sorted TriFace
//    array, built once per geometry asset exactly as the MODL path builds
//    them. Every appearance still builds its own Vertex3D[] (shared position +
//    own UV/colour), materials and primitives from the Memory& it is given.
//  - That Memory& is the asset slot's arena (Actor::BindAssets is handed the
//    room slot's, or PERM's, GetSlotMemory()); AssetManager::FreeRoomSlot
//    releases it wholesale, refcounts or not. So the record is NOT allocated
//    there: it is a heap object owned by std::shared_ptr, one reference per
//    RenderObject3D (copies included) and nothing else, and it copies its
//    data out of the asset stream, so a room free/reload cannot leave it
//    pointing at freed slot memory. ActiveRooms unbinds a room's actors
//    (Actor::UnBindAssets runs ~RenderActor, hence ~RenderObject3D) before it
//    calls FreeRoomSlot, so the last user's release frees the record.
//  - The cache maps the geometry's packed asset id to a weak_ptr, so it never
//    keeps a record alive. Packed ids repeat across levels, and a holder that
//    is never destroyed (an emitter's template object leaks today) would keep
//    an old level's record alive: a hit is therefore reused only if its
//    counts, both CRCs and name equal this GREF's, i.e. it holds these bytes.
//  - The shared TriFace array is never written: GetWritableFaceList refuses a
//    shared model, and LRIG/DFRM (which write vertices or face normals in
//    place) make a GREF model invalid.
//
// Invalid data fails loudly with the model and geometry names, in every
// build: SharedGeometryFail is not compiled out with DO_ASSERTIONS=0.

struct UVColorOnDisk				// one UVCL record, 12 bytes
{
	fixed32 u,v;
	Color color;
};

static int sSharedGeometryLive = 0;

struct SharedModelGeometry
{
	SharedModelGeometry() { ++sSharedGeometryLive; }
	~SharedModelGeometry() { --sSharedGeometryLive; }
	int32 assetID = 0;
	GeometryReferenceOnDisk ref;
	int maxMaterialIndex = 0;
	std::vector<Vector3_PS> positions;
	std::vector<TriFace> faces;		// material-sorted, plus the dummy face (materialIndex -1)
};

int
RenderObject3D::SharedGeometryLiveCount()
{
	return sSharedGeometryLive;
}

[[noreturn]] static void
SharedGeometryFail(const char* model, const char* geometry, const char* reason)
{
	std::fprintf(stderr, "shared geometry: model %s -> geometry %s: %s\n", model, geometry, reason);
	std::fflush(stderr);
	_sys_assert(0, reason, __FILE__, __LINE__);
	std::abort();					// _sys_assert returns on the web
}

uint32
SharedGeometryCrc32(const void* data, size_t size)
{
	const uint8* bytes = static_cast<const uint8*>(data);
	uint32 crc = 0xFFFFFFFFu;
	for(size_t index=0;index<size;++index)
	{
		crc ^= bytes[index];
		for(int bit=0;bit<8;++bit)
			crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
	}
	return ~crc;
}

const char*
ParseGeometryReference(const void* payload, int size, GeometryReferenceOnDisk& out)
{
	static_assert(sizeof(GeometryReferenceOnDisk) == 52, "GREF is 52 bytes on disk");
	if(size != int(sizeof(GeometryReferenceOnDisk)))
		return "GREF is not 52 bytes";
	std::memcpy(&out, payload, sizeof(out));
	if(out.version != 1)
		return "GREF version is not 1";
	const void* end = std::memchr(out.name, 0, sizeof(out.name));
	if(!end || end == out.name)
		return "GREF name is empty or longer than 31 characters";
	return NULL;
}

const char*
ReadSharedGeometry(binistream& geometry, const GeometryReferenceOnDisk& ref,
	std::vector<int32>& positions, std::vector<_TriFaceOnDisk>& faces)
{
	static_assert(sizeof(_TriFaceOnDisk) == 8, "FACE record is 8 bytes");
	positions.clear();
	faces.clear();
	IFFChunkIter geomIter(geometry);
	if(geomIter.GetChunkID().ID() != IFFTAG('G','E','O','M'))
		return "asset is not a GEOM";
	int posnChunks = 0, faceChunks = 0, otherChunks = 0;
	std::vector<uint8> posn, face;
	while(geomIter.BytesLeft() > 0)
	{
		IFFChunkIter* chunkIter = geomIter.GetChunkIter(HALScratchLmalloc);
		const uint32 id = chunkIter->GetChunkID().ID();
		std::vector<uint8>* target = NULL;
		if(id == IFFTAG('P','O','S','N')) { ++posnChunks; target = &posn; }
		else if(id == IFFTAG('F','A','C','E')) { ++faceChunks; target = &face; }
		else ++otherChunks;
		if(target)
		{
			target->resize(chunkIter->BytesLeft());
			if(!target->empty())
				chunkIter->ReadBytes(target->data(), int(target->size()));
		}
		MEMORY_DELETE(HALScratchLmalloc,chunkIter,IFFChunkIter);
	}
	if(posnChunks != 1 || faceChunks != 1 || otherChunks != 0)
		return "GEOM must hold exactly one POSN and one FACE";
	if(posn.size() % 12 || face.size() % sizeof(_TriFaceOnDisk))
		return "POSN or FACE is not a whole number of records";
	const size_t vertexCount = posn.size() / 12, faceCount = face.size() / sizeof(_TriFaceOnDisk);
	if(vertexCount == 0 || faceCount == 0 || vertexCount > 32767 || faceCount > 32767)
		return "vertex or face count is out of range";
	if(vertexCount != ref.vertexCount || faceCount != ref.faceCount)
		return "GREF counts do not match the geometry";
	if(SharedGeometryCrc32(posn.data(), posn.size()) != ref.posCrc32 ||
	   SharedGeometryCrc32(face.data(), face.size()) != ref.faceCrc32)
		return "GREF CRC does not match the geometry";
	positions.resize(vertexCount * 3);
	std::memcpy(positions.data(), posn.data(), posn.size());
	faces.resize(faceCount);
	std::memcpy(faces.data(), face.data(), face.size());
	for(const _TriFaceOnDisk& f : faces)
	{
		if(f.v1Index < 0 || f.v2Index < 0 || f.v3Index < 0 ||
		   size_t(f.v1Index) >= vertexCount || size_t(f.v2Index) >= vertexCount || size_t(f.v3Index) >= vertexCount)
			return "a face vertex index is out of range";
		if(f.materialIndex < 0)
			return "a face material index is negative";
	}
	return NULL;
}

static std::unordered_map<int32, std::weak_ptr<const SharedModelGeometry> >&
SharedGeometryCache()
{
	static std::unordered_map<int32, std::weak_ptr<const SharedModelGeometry> > cache;
	return cache;
}

static bool
SameReference(const GeometryReferenceOnDisk& a, const GeometryReferenceOnDisk& b)
{
	return a.vertexCount == b.vertexCount && a.faceCount == b.faceCount &&
		a.posCrc32 == b.posCrc32 && a.faceCrc32 == b.faceCrc32 &&
		std::strncmp(a.name, b.name, sizeof(a.name)) == 0;
}

// First user reads, validates and builds; later users of the same asset reuse it.
static std::shared_ptr<const SharedModelGeometry>
AcquireSharedGeometry(int32 assetID, const GeometryReferenceOnDisk& ref, const GfxCallbacks& callbacks, const char* model)
{
	auto& cache = SharedGeometryCache();
	for(auto it = cache.begin(); it != cache.end(); )
		it = it->second.expired() ? cache.erase(it) : std::next(it);
	auto found = cache.find(assetID);
	if(found != cache.end())
	{
		std::shared_ptr<const SharedModelGeometry> record = found->second.lock();
		if(record && SameReference(record->ref, ref))
			return record;
		// else: a live record of another level's asset with this id; leave it to its holders
	}

	binistream stream = callbacks.GetGeometryStream(assetID);
	std::vector<int32> posn;
	std::vector<_TriFaceOnDisk> diskFaces;
	if(const char* why = ReadSharedGeometry(stream, ref, posn, diskFaces))
		SharedGeometryFail(model, ref.name, why);

	auto record = std::make_shared<SharedModelGeometry>();
	record->assetID = assetID;
	record->ref = ref;
	const int vertexCount = int(ref.vertexCount), faceCount = int(ref.faceCount);
	record->positions.reserve(vertexCount);
	for(int index=0;index<vertexCount;++index)
		record->positions.push_back(Vector3_PS(Scalar::FromFixed32(posn[index*3]),Scalar::FromFixed32(posn[index*3+1]),Scalar::FromFixed32(posn[index*3+2])));

	// Normals and the material sort exactly as the MODL FACE case below.
	std::vector<TriFace> tempFaceList(faceCount);
	for(int index=0;index < faceCount; ++index)
	{
		std::memcpy(&tempFaceList[index], &diskFaces[index], sizeof(_TriFaceOnDisk));	// TriFaceOnDisk is a prefix of TriFace
		Vector3 v0( PSToVector3(record->positions[tempFaceList[index].v1Index]));
		Vector3 v1( PSToVector3(record->positions[tempFaceList[index].v2Index]));
		Vector3 v2( PSToVector3(record->positions[tempFaceList[index].v3Index]));
		tempFaceList[index].normal = Vector3ToPS12(CalculateNormal(v0,v1,v2));
		if(tempFaceList[index].materialIndex > record->maxMaterialIndex)
			record->maxMaterialIndex = tempFaceList[index].materialIndex;
	}
	record->faces.resize(faceCount+1);	// plus one dummy face
	const int MATERIAL_CLEARED = -1;
	int materialIndex = MATERIAL_CLEARED-1;
	int nextFreeFace=0;
	while(materialIndex != MATERIAL_CLEARED)
	{
		materialIndex = MATERIAL_CLEARED;
		for(int faceIndex=0;faceIndex < faceCount&&materialIndex == MATERIAL_CLEARED;++faceIndex)
			materialIndex = tempFaceList[faceIndex].materialIndex;
		if(materialIndex != MATERIAL_CLEARED)
		{
			for(int index=0;index< faceCount;++index)
			{
				if(tempFaceList[index].materialIndex == materialIndex)
				{
					record->faces[nextFreeFace] = tempFaceList[index];
					tempFaceList[index].materialIndex = MATERIAL_CLEARED;
					++nextFreeFace;
				}
			}
		}
	}
	if(nextFreeFace != faceCount)
		SharedGeometryFail(model, ref.name, "material sort lost a face");
	record->faces[faceCount].materialIndex = -1;  // as the MODL path's dummy face
	cache[assetID] = record;
	return record;
}

//============================================================================

TriFace*
RenderObject3D::GetWritableFaceList()
{
	if(_sharedGeometry)
		SharedGeometryFail("?", _sharedGeometry->ref.name, "GetWritableFaceList on a shared-geometry model (its faces are shared)");
	_staticState = STATIC_DEFORMED;
	return _faceList;
}

//============================================================================
// keeps pointers to facelist and vertexlist

RenderObject3D::RenderObject3D( Memory& memory, int vertexCount,Vertex3D* vertexList, int faceCount, TriFace* faceList, Material* materialList )
{
	_handleCount = 0;
	_materialCount = 0;	// caller path; materialCount unknown — SetMaterialColor will reject out-of-range writes via the (idx >= _materialCount) check
	Construct(memory, vertexCount,vertexList,faceCount,faceList,materialList);
}

//=============================================================================

void
RenderObject3D::_InitPrimList( Memory& memory )
{
	_primList[0] = new (memory) Primitive[ORDER_TABLES*_faceCount];
	assert(ValidPtr(_primList[0]));
	for(int index=1;index<ORDER_TABLES;++index)
	{
		_primList[index] = _primList[0] + (_faceCount*index);			// kts to reduce # of allocations
	}
}

//=============================================================================

RenderObject3D::RenderObject3D( Memory& memory, const RenderObject3D& obj3d )
{
#pragma message( __FILE__ ": use reference counting" )

    _lionRig=obj3d._lionRig;
	_dfrm=obj3d._dfrm;
	_materialList = obj3d._materialList;
	_materialCount = obj3d._materialCount;

	_handleCount = obj3d._handleCount;
	_handleList = obj3d._handleList;
	// Shares vertices, faces and (usually) materials with obj3d, so a change
	// made through either would not be seen by the other's bake. Particles
	// are the user; they are short-lived, so a bake each would churn anyway.
	_staticState = STATIC_SHARED_COPY;
	_vertexCount = obj3d._vertexCount;
	_vertexList = obj3d._vertexList;
    if(!_lionRig.empty()) {
        _vertexList=new(memory) Vertex3D[_vertexCount];
        for(int i=0;i<_vertexCount;i++) _vertexList[i]=obj3d._vertexList[i];
        _materialList=new(memory) Material[_materialCount];
        for(int i=0;i<_materialCount;i++) _materialList[i]=obj3d._materialList[i];
    }
	_faceCount = obj3d._faceCount;
	_faceList = obj3d._faceList;
	_sharedGeometry = obj3d._sharedGeometry;	// a shared _faceList outlives obj3d through this reference
	if(_dfrm) {
		// DFRM writes positions and face normals: each copy needs its own.
		_vertexList=new(memory) Vertex3D[_vertexCount];
		for(int i=0;i<_vertexCount;i++) _vertexList[i]=obj3d._vertexList[i];
		_faceList=new(memory) TriFace[_faceCount+1];
		for(int i=0;i<=_faceCount;i++) _faceList[i]=obj3d._faceList[i];
	}

#if defined(USE_ORDER_TABLES)
	_InitPrimList( memory );
#endif
	ApplyMaterials(_materialList);
	Validate();				// make sure we built a good one
}

//=============================================================================

void
RenderObject3D::Construct( Memory& memory, int vertexCount,Vertex3D* vertexList, int faceCount, TriFace* faceList, Material* materialList )
{
	assert(vertexCount > 0);
	assert(faceCount > 0);

	_vertexCount = vertexCount;
	_vertexList = vertexList;

	_faceCount = faceCount;
	_faceList = faceList;

#if DO_ASSERTIONS
	for(int debugIndex = 0;debugIndex < _faceCount;++debugIndex)
	{
		assert(_faceList[debugIndex].v1Index < _vertexCount);
		assert(_faceList[debugIndex].v2Index < _vertexCount);
		assert(_faceList[debugIndex].v3Index < _vertexCount);
	}
#endif
	_InitPrimList( memory );
	ApplyMaterials(materialList);
	Validate();				// make sure we built a good one
}

//============================================================================

RenderObject3D::~RenderObject3D()
{
	StaticMeshDiscard();	// frees the GPU buffers and bookkeeping of a bake
}

//============================================================================

void
RenderObject3D::ApplyMaterials(Material* materialList )
{
	++_staticVersion;		// primitives (colours, texture pages) are rebuilt: a bake is stale
	_materialList = materialList;
	for(int page=0;page<ORDER_TABLES;++page)
		for(int index=0;index<_faceCount;++index)
		{
			const TriFace& face = _faceList[index];
			const Material* pMaterial = &( materialList[face.materialIndex] );
			assert( pMaterial );
			assert(ValidPtr(&_primList[page][index]));
			pMaterial->InitPrimitive(_primList[page][index],
				_vertexList[face.v1Index],
				_vertexList[face.v2Index],
				_vertexList[face.v3Index] );
		}

}


//============================================================================
// construct to load from disk

RenderObject3D::RenderObject3D(Memory& memory, binistream& input,int32 userData, const GfxCallbacks& callbacks )
{
    IFFChunkIter meshIter(input);
	assert(meshIter.GetChunkID().ID() == IFFTAG('M','O','D','L'));
	// create RenderObject3D from model on disk data
	int vertexCount = 0;
	Vertex3D* vertexList = NULL;
	Material* materials = NULL;
	int materialCount = 0;
	TriFace* faceList = NULL;
	int faceCount = 0;
	_handleCount = 0;
	_handleList = NULL;
	// Shared model geometry (GREF appearance). Chunk order is not significant:
	// everything is collected here and resolved after the loop.
	GeometryReferenceOnDisk gref;
	int grefChunks = 0, uvclChunks = 0;
	const char* grefError = NULL;
	bool sawLionRig = false, sawDeform = false;
	std::vector<UVColorOnDisk> uvcl;

//#pragma message ("KTS: memory leak, these news are never freed")
// now tracked with LMalloc
	while(meshIter.BytesLeft() > 0)
	{
		IFFChunkIter* chunkIter = meshIter.GetChunkIter(HALScratchLmalloc);
//		ciffread << "chunkid = " << chunkIter->GetChunkID() << std::endl;
		switch(chunkIter->GetChunkID().ID())
		{
			case IFFTAG('V','R','T','X'):
			{
				assert(vertexList == NULL);  // if this fires, there is more than one VRTX chunk
//				ciffread << "VRTX: ";
				vertexCount = chunkIter->Size()/sizeof(Vertex3DOnDisk );
//				ciffread << "Count = " << vertexCount << std::endl;
				assert(chunkIter->Size()%sizeof(Vertex3DOnDisk) == 0);
				assert(vertexCount);
				vertexList = new (memory) Vertex3D[vertexCount];
				assert(ValidPtr(vertexList));
				Vertex3DOnDisk tempVertex;
				for(int count=0;count<vertexCount;++count)
				{
					chunkIter->ReadBytes(&tempVertex,sizeof(Vertex3DOnDisk));

					vertexList[count].u = Scalar::FromFixed32(tempVertex.u);
					vertexList[count].v = Scalar::FromFixed32(tempVertex.v);
					vertexList[count].color = tempVertex.color;
					vertexList[count].position = Vector3_PS(Scalar::FromFixed32(tempVertex.x),Scalar::FromFixed32(tempVertex.y),Scalar::FromFixed32(tempVertex.z));
				}
				assert(chunkIter->BytesLeft() == 0);
				break;
			}
#pragma message ("KTS: figure out how to share common resources between multiple models (or at least more than instance of the same model)")
			case IFFTAG('M','A','T','L'):
			{
				assert(materials == NULL);  // if this fires, there is more than one MATL chunk
				materialCount = chunkIter->Size()/sizeof(_MaterialOnDisk);
				assert(chunkIter->Size()%sizeof(_MaterialOnDisk) == 0);
//				ciffread << "materialCount = " << materialCount << std::endl;
				materials = new (memory) Material[materialCount];
				assert(ValidPtr(materials));
				for(int index=0;index < materialCount; ++index)
				{
#pragma message ("KTS: this causes two memory copies, is there a better way?")
					_MaterialOnDisk mod;
					chunkIter->ReadBytes(&mod,sizeof(_MaterialOnDisk));
//					ciffread << "Read material, bytes left = " << chunkIter->BytesLeft() << std::endl;

					const Texture* texture = &emptyTexture;
                    const PixelMap* texturePixelMap = NULL;
					if(mod._materialFlags & Material::TEXTURE_MAPPED)
					{
						AssertMsg(strlen(mod.textureName),"invalid texture name in material");
						LookupTextureStruct lts = callbacks.LookupTexture(mod.textureName,userData);
                        texture = &lts.texture;
                        texturePixelMap = &lts.texturePixelMap;
					}
					new (&materials[index]) Material(mod,*texture,texturePixelMap);
					materials[index].Validate();
				}
				assert(chunkIter->BytesLeft() == 0);
				break;
			}
			case IFFTAG('G','R','E','F'):
			{
				std::vector<uint8> bytes(chunkIter->BytesLeft());
				if(!bytes.empty()) chunkIter->ReadBytes(bytes.data(),int(bytes.size()));
				if(++grefChunks == 1)
					grefError = ParseGeometryReference(bytes.data(),int(bytes.size()),gref);
				break;
			}
			case IFFTAG('U','V','C','L'):
			{
				static_assert(sizeof(UVColorOnDisk) == 12, "UVCL record is 12 bytes");
				++uvclChunks;
				if(chunkIter->BytesLeft() % int(sizeof(UVColorOnDisk)) != 0)
				{
					uvcl.clear();		// size checked against the geometry below
					break;
				}
				uvcl.resize(chunkIter->BytesLeft() / sizeof(UVColorOnDisk));
				if(!uvcl.empty()) chunkIter->ReadBytes(uvcl.data(),int(uvcl.size()*sizeof(UVColorOnDisk)));
				break;
			}
            case IFFTAG('L','R','I','G'):
            {
                sawLionRig = true;
                // v1: version/count followed by region, weight and pivot XYZ (16.16).
                // Invalid optional metadata is discarded, never partially applied.
                uint32 version=0,count=0;
                if(chunkIter->BytesLeft()<8) break;
                chunkIter->ReadBytes(&version,4); chunkIter->ReadBytes(&count,4);
                if(version!=1 || count!=uint32(vertexCount) || count>32767 ||
                    chunkIter->BytesLeft()!=count*20 || !_lionRig.empty()) break;
                std::vector<wf_render::LionRig> rig; rig.reserve(count); bool valid=true;
                for(uint32 i=0;i<count;i++) {
                    int32 v[5]; chunkIter->ReadBytes(v,sizeof(v));
                    if(v[0]<0 || v[0]>=wf_render::LionRegionCount || v[1]<0 || v[1]>65536) valid=false;
                    rig.push_back({unsigned(v[0]),v[1]/65536.f,v[2]/65536.f,v[3]/65536.f,v[4]/65536.f});
                }
                if(valid) _lionRig.swap(rig);
                break;
            }
            case IFFTAG('D','F','R','M'):
            {
                // DFRM v1 (renderassets/dfrm_deform.h). Same rule as LRIG: invalid
                // optional metadata is discarded, never partially applied.
                sawDeform = true;
                std::vector<uint8> bytes(chunkIter->BytesLeft());
                if(!bytes.empty()) chunkIter->ReadBytes(bytes.data(),int(bytes.size()));
                auto data=std::make_shared<wf_render::DfrmData>();
                const char* reason="";
                if(!_dfrm && wf_render::ParseDfrm(bytes.data(),bytes.size(),vertexCount,*data,reason)) _dfrm=data;
                else std::fprintf(stderr,"DFRM: chunk dropped, mesh keeps its rest pose (%s)\n",_dfrm?"duplicate chunk":reason);
                break;
            }
            case IFFTAG('O','P','A','C'):
            {
                uint32 version, count;
                assert(materials != NULL);
                chunkIter->ReadBytes(&version, sizeof(version));
                chunkIter->ReadBytes(&count, sizeof(count));
                assert(version == 1 && count == uint32(materialCount));
                assert(chunkIter->BytesLeft() == count * sizeof(uint32));
                for (uint32 index = 0; index < count; ++index) {
                    uint32 opacity;
                    chunkIter->ReadBytes(&opacity, sizeof(opacity));
                    assert(opacity <= 65536);
                    materials[index].SetOpacity(float(opacity) / 65536.0f);
                }
                break;
            }
			case IFFTAG('F','A','C','E'):
			{
				assert(ValidPtr(vertexList));  			// need vertex list so we can calc normals
				assert(faceList == NULL);  // if this fires, there is more than one FACE chunk
				assert(ValidPtr(materials));  // for debugging purposes, we want to know how many materials there are (so we can validate the material indecies)

				faceCount = chunkIter->Size()/sizeof(_TriFaceOnDisk);
				assert(faceCount);
				assert(chunkIter->Size() % sizeof(_TriFaceOnDisk) == 0);
				faceList = new(memory) TriFace[faceCount+1];  // plus one dummy face
				assert(ValidPtr(faceList));
				TriFace* tempFaceList = new(memory) TriFace[faceCount];
				assert(ValidPtr(tempFaceList));
				for(int index=0;index < faceCount; ++index)
				{
#pragma message ("KTS: this causes two memory copies, is there a better way?")
					// kts since TriFaceOnDisk is a sub-set of triface, this works
					chunkIter->ReadBytes(&tempFaceList[index],sizeof(_TriFaceOnDisk));
					Vector3 v0( PSToVector3(vertexList[tempFaceList[index].v1Index].position));
					Vector3 v1( PSToVector3(vertexList[tempFaceList[index].v2Index].position));
					Vector3 v2( PSToVector3(vertexList[tempFaceList[index].v3Index].position));
					tempFaceList[index].normal = Vector3ToPS12(CalculateNormal(v0,v1,v2));
					AssertMsg(tempFaceList[index].materialIndex < materialCount,"Object ??? tried to refernce material index " << tempFaceList[index].materialIndex  << " when there are only " << materialCount << " materials");
					RangeCheck(0,tempFaceList[index].materialIndex,materialCount);
				}
				assert(chunkIter->BytesLeft() == 0);
				const int MATERIAL_CLEARED = -1;
				int materialIndex = MATERIAL_CLEARED-1;

				// sort faces by material index
				int nextFreeFace=0;
				while(materialIndex != MATERIAL_CLEARED)
				{
					// find next unused material index
					materialIndex = MATERIAL_CLEARED;
					for(int faceIndex=0;faceIndex < faceCount&&materialIndex == MATERIAL_CLEARED;++faceIndex)
						materialIndex = tempFaceList[faceIndex].materialIndex;

					if(materialIndex != MATERIAL_CLEARED)
					{
						// now copy all of the faces which use this material to the facelist
						for(int index=0;index< faceCount;++index)
						{
							if(tempFaceList[index].materialIndex == materialIndex)
							{
								faceList[nextFreeFace] = tempFaceList[index];
								tempFaceList[index].materialIndex = MATERIAL_CLEARED;
								++nextFreeFace;
							}
						}
					}
				}
				AssertMsg(nextFreeFace == faceCount,"nextFreeFace = " << nextFreeFace << ", faceCount+1 = " << faceCount+1);
				faceList[faceCount].materialIndex = -1;  // kts 3/27/98 9:45AM
				memory.Free(tempFaceList,sizeof(TriFace)*faceCount);
				break;
			}

			case IFFTAG('H','N','D','L'):
			{
				assert(_handleList == NULL);  // if this fires, there is more than one HNDL chunk
				_handleCount = chunkIter->Size() / sizeof(Handle);
				assert(chunkIter->Size()%sizeof(Handle) == 0);
				assert(_handleCount);
				_handleList = new(memory) Handle[_handleCount];
				assert(ValidPtr(_handleList));
				chunkIter->ReadBytes(_handleList,chunkIter->Size());
				assert(chunkIter->BytesLeft() == 0);
				break;
			}

			default:
//				ciffread << "ignoring chunk with ID of " << chunkIter->GetChunkID() << std::endl;
				break;
		}
		MEMORY_DELETE(HALScratchLmalloc,chunkIter,IFFChunkIter);
		//delete chunkIter;
//		meshIter.NextChunk();
//		ciffread << "meshIter bytes left = " << meshIter.BytesLeft() << std::endl;
	}
	assert( meshIter.BytesLeft() == 0 );
	if(grefChunks)
	{
		char model[80];
		const char* modelName = callbacks.LookupAssetName(userData);
		std::snprintf(model,sizeof(model),"%s (asset %08x)",modelName && modelName[0] ? modelName : "?",unsigned(userData));
		const char* geometryName = grefError ? "?" : gref.name;
		if(grefError) SharedGeometryFail(model,geometryName,grefError);
		if(grefChunks != 1) SharedGeometryFail(model,geometryName,"more than one GREF chunk");
		if(vertexList || faceList) SharedGeometryFail(model,geometryName,"a GREF model must not carry VRTX or FACE");
		if(sawLionRig || sawDeform) SharedGeometryFail(model,geometryName,"a GREF model must not carry LRIG or DFRM (they write vertices or normals in place)");
		if(!materials || materialCount < 1) SharedGeometryFail(model,geometryName,"a GREF model needs a MATL chunk");
		if(uvclChunks != 1) SharedGeometryFail(model,geometryName,"a GREF model needs exactly one UVCL chunk");
		if(uvcl.size() != gref.vertexCount) SharedGeometryFail(model,geometryName,"UVCL does not hold one record per GREF vertex");

		const int32 geometryID = callbacks.LookupGeometry(gref.name,userData);
		if(geometryID == 0) SharedGeometryFail(model,geometryName,"no asset of that name in the model's room");
		_sharedGeometry = AcquireSharedGeometry(geometryID,gref,callbacks,model);
		if(_sharedGeometry->maxMaterialIndex >= materialCount) SharedGeometryFail(model,geometryName,"a face material index is out of range for this model's MATL");

		// Own vertex array: shared position + this appearance's UV and colour,
		// in the geometry's vertex order (as the VRTX case builds it).
		vertexCount = int(gref.vertexCount);
		vertexList = new (memory) Vertex3D[vertexCount];
		assert(ValidPtr(vertexList));
		for(int index=0;index<vertexCount;++index)
		{
			vertexList[index].u = Scalar::FromFixed32(uvcl[index].u);
			vertexList[index].v = Scalar::FromFixed32(uvcl[index].v);
			vertexList[index].color = uvcl[index].color;
			vertexList[index].position = _sharedGeometry->positions[index];
		}
		faceCount = int(gref.faceCount);
		// Shared and immutable: nothing writes through _faceList for this object
		// (GetWritableFaceList refuses it, and LRIG/DFRM are rejected above).
		faceList = const_cast<TriFace*>(_sharedGeometry->faces.data());
	}
	assert(vertexCount > 0);
	assert(faceCount > 0);
	_materialCount = materialCount;	// captured for SetMaterialColor() range checks
	Construct(memory,vertexCount,vertexList,faceCount,faceList, materials);
}

//============================================================================

void
RenderObject3D::SetMaterialColor(int idx, const Color& color)
{
	if (idx < 0 || idx >= _materialCount) return;	// silently ignore out-of-range
	if (!ValidPtr(_materialList)) return;
	if (_materialList[idx].GetColor() == color) return;	// no-op shortcut
	_materialList[idx].SetColor(color);
	// Re-bake the prim list so the next Render() picks up the new color.
	// SetColor() already updated Material._cdColor; this re-runs InitPrimitive
	// for every face × ORDER_TABLES, which writes the new RGB into each Primitive.
	ApplyMaterials(_materialList);
}

//============================================================================

// Level-owned runtime buffers; publication happens between scene renders.
bool RenderObject3D::SetRuntimeGeometry(int vertices, Vertex3D* vertexList, int faces, TriFace* faceList, bool textured)
{
 if(vertices<1||vertices>=32000||faces<1||faces>=32000||!vertexList||!faceList)return false;
 for(int i=0;i<faces;i++)if(faceList[i].v1Index<0||faceList[i].v2Index<0||faceList[i].v3Index<0||faceList[i].v1Index>=vertices||faceList[i].v2Index>=vertices||faceList[i].v3Index>=vertices||faceList[i].materialIndex!=0)return false;
 _staticState=STATIC_RUNTIME_GEOMETRY;	// its vertices are rewritten in place each frame
 _runtimePrimitives.resize(size_t(faces)*ORDER_TABLES);
 _vertexCount=vertices;_vertexList=vertexList;_faceCount=faces;_faceList=faceList;
 for(int page=0;page<ORDER_TABLES;page++)_primList[page]=_runtimePrimitives.data()+size_t(page)*faces;
 // Preserve the exported texture binding when replacing runtime geometry.
 _materialList[0].SetMaterialFlags(Material::GOURAUD_SHADED|(textured?Material::TEXTURE_MODULATE:0)|(textured?(_materialList[0].GetMaterialFlags()&Material::TEXTURE_MAPPED):0)|Material::LIGHTING_PRELIT);
 ApplyMaterials(_materialList);return true;
}

void RenderObject3D::SetLionPalette(unsigned dark,unsigned light)
{
    for(int i=0;i<_materialCount;i++) if(_materialList[i].GetMaterialFlags() & Material::TEXTURE_PALETTE)
        _materialList[i].SetTexturePalette(dark,light);
}
