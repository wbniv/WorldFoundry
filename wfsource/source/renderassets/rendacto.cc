//============================================================================
// rendacto.cc: RenderActor: interface between game and renderer
// Copyright (c) 1997,1999,2000,2001,2002,2003 World Foundry Group.  
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

//============================================================================
// Original Author: Kevin T. Seghetti
//============================================================================


#include <math/matrix34.hp>
#include <math/vector3.hp>
#include <gfx/material.hp>
#include <gfx/rendmatt.hp>

#include <physics/physical.hp>
#include <asset/assslot.hp>
#include <oas/matte.ht>
#include <cpplib/libstrm.hp>
#include <map>

#include "rendacto.hp"
#include <renderassets/box_color.h>
                                     
//============================================================================

RenderActorNULL NULLRenderActor;

//============================================================================

RenderActor::RenderActor()
{
}

//=============================================================================

RenderActor::~RenderActor()
{
}

//============================================================================

void
RenderActor::Validate() const
{
#if DO_VALIDATION
#endif
}

//============================================================================

RenderActorNULL::~RenderActorNULL()
{
}

//============================================================================

#if DO_VALIDATION
void
RenderActorNULL::_Validate() const
{
	ValidatePtr(this);
}
#endif

//============================================================================

void
RenderActorNULL::Render(RenderCamera&, const PhysicalObject&, const Clock&)
{
}

//=============================================================================

void
RenderActorNULL::SetAnimationCycle(int )
{
}

//============================================================================

bool
RenderActorNULL::GetHandle(const HandleID, Vector3& ) const
{
	return false;
}

//============================================================================
// kts test data
// cube

static Vertex3D cubeVertexList[8] =
{
	Vertex3D( Scalar::zero,Scalar::zero,Color(128,128,128), Vector3_PS( PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT( 5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(200,200,50), Vector3_PS( PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT( 5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(128,0,0), Vector3_PS( PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT(-5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(0,128,0), Vector3_PS( PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT(-5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(0,128,0), Vector3_PS( PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT( 5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(0,0,0), Vector3_PS( PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT( 5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(0,0,128), Vector3_PS( PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT(-5)) ),
	Vertex3D( Scalar::zero,Scalar::zero,Color(128,128,0), Vector3_PS( PS_SCALAR_CONSTANT(-5),PS_SCALAR_CONSTANT( 5),PS_SCALAR_CONSTANT(-5)) )
};


#if 0
Material cubeMaterialList[] =
{
	Material(Color( 40, 40,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// blue
	Material(Color( 40,168, 40),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// green
	Material(Color( 40,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// cyan
	Material(Color(168, 40, 40),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// red
   Material(Color(168, 40,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// pink
	Material(Color(168,168, 40),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// yellow
	Material(Color(168,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL)			// white
};
#else
Material cubeMaterialList[] =
{
	Material(Color( 40, 40,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// blue
	Material(Color( 40,168, 40),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// green
	Material(Color( 40,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// cyan
//	Material(Color( 40,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// cyan
	Material(Color(168, 40, 40),Material::GOURAUD_SHADED|Material::TEXTURE_MAPPED,emptyTexture,NULL),			// red
	Material(Color(128,128,128),Material::FLAT_SHADED|Material::TEXTURE_MAPPED,emptyTexture,NULL),			// yellow
    Material(Color(168, 40,168),Material::GOURAUD_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// pink
	Material(Color(168,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// white
//	Material(Color(168,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL),			// white
//	Material(Color(168,168,168),Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL)			// white
};
#endif

//#define FaceEntry(v0,v1,v2,matIndex) { v0,v1,v2,matIndex,V32ToV16(CalculateNormal(cubeVertexList[v0].position,cubeVertexList[v1].position,cubeVertexList[v2].position)) }

static TriFace cubeFaceList[12] =
{
	TriFace(4,5,1,3,cubeVertexList),	   		// top(back)
	TriFace(4,1,0,3,cubeVertexList),
	TriFace(5,4,6,5,cubeVertexList),			// back(bottom)
	TriFace(4,7,6,5,cubeVertexList),
	TriFace(0,1,2,0,cubeVertexList),			// front(top)
	TriFace(1,3,2,0,cubeVertexList),
	TriFace(4,0,2,1,cubeVertexList),			// left side
	TriFace(2,7,4,1,cubeVertexList),
	TriFace(1,5,6,2,cubeVertexList),			// right side
	TriFace(3,1,6,2,cubeVertexList),
	TriFace(2,3,6,4,cubeVertexList),			// bottom(front)
	TriFace(6,7,2,4,cubeVertexList)
};

//============================================================================

RenderActor3D::RenderActor3D(Memory& memory) : _object(memory,8,cubeVertexList,12,cubeFaceList,cubeMaterialList)
{
}

//=============================================================================

RenderActor3D::RenderActor3D(Memory& memory, int vertexCount,Vertex3D* vertexList,int faceCount, TriFace* faceList, Material*  materials)
: _object(memory,vertexCount,vertexList, faceCount, faceList, materials)
{

}

//=============================================================================

RenderActor3D::RenderActor3D(Memory& memory, binistream& input,int32 userData, const GfxCallbacks& callbacks)
: _object(memory, input,userData, callbacks)
{
}

void RenderActor3D::SetJellyDeformation(float contraction, float phase, float pitchLag, float rollLag)
{
    if (!std::isfinite(contraction) || !std::isfinite(phase) || !std::isfinite(pitchLag) || !std::isfinite(rollLag)) return;
    Vertex3D* vertices=_object.GetWrittableVertexList();
    const int count=_object.GetVertexCount();
    if (!vertices || count<=0 || !_fishWeights.empty() || !_finWeights.empty() || !_swimWeights.empty()) return;
    if (_jellyWeights.empty()) {
        _jellyWeights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vector3& p=vertices[i].position;
            _jellyWeights.push_back(wf_render::JellyWeight::make(p.X().AsFloat(),p.Y().AsFloat(),p.Z().AsFloat()));
        }
    }
    contraction=std::max(0.f,std::min(1.f,contraction));
    phase=std::fmod(phase,1.f);
    pitchLag=std::max(-.025f,std::min(.025f,pitchLag));
    rollLag=std::max(-.025f,std::min(.025f,rollLag));
    for(int i=0;i<count;i++) {
        float x,y,z; _jellyWeights[i].deform(contraction,phase,pitchLag,rollLag,x,y,z);
        vertices[i].position=Vector3(Scalar(x),Scalar(y),Scalar(z));
    }
}

void RenderActor3D::SetSwimDeformation(float phase, float amplitude, float bend,
    float finPhase, float finAmplitude, float minX, float maxX)
{
    if (!std::isfinite(phase) || !std::isfinite(amplitude) || !std::isfinite(bend) ||
        !std::isfinite(finPhase) || !std::isfinite(finAmplitude) ||
        !std::isfinite(minX) || !std::isfinite(maxX) || maxX-minX<.001f) return;
    Vertex3D* vertices=_object.GetWrittableVertexList();
    const int count=_object.GetVertexCount();
    if (!vertices || count<=0 || !_fishWeights.empty() || !_finWeights.empty() || !_jellyWeights.empty()) return;
    if (_swimWeights.empty()) {
        _swimMinX=minX; _swimMaxX=maxX; _swimWeights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vertex3D& v=vertices[i];
            _swimWeights.push_back(wf_render::SwimWaveWeight::make(v.position.X().AsFloat(),
                v.position.Y().AsFloat(),minX,maxX,v.u.AsFloat(),v.v.AsFloat()));
        }
    }
    // Reference span is model metadata, not an animation channel.
    if (minX!=_swimMinX || maxX!=_swimMaxX) return;
    const float angle=std::fmod(phase,1.f)*6.283185307f;
    const float finAngle=std::fmod(finPhase,1.f)*6.283185307f;
    const float sine=std::sin(angle),cosine=std::cos(angle);
    const float finSine=std::sin(finAngle),finCosine=std::cos(finAngle);
    amplitude=std::max(0.f,std::min(.12f*(maxX-minX),amplitude));
    bend=std::max(-.4f,std::min(.4f,bend));
    finAmplitude=std::max(0.f,std::min(.15f,finAmplitude));
    for(int i=0;i<count;i++) vertices[i].position.SetY(Scalar(_swimWeights[i].deform(
        sine,cosine,amplitude,bend,finSine,finCosine,finAmplitude)));
}

void RenderActor3D::SetFishDeformation(float phase, float amplitude)
{
    if (!std::isfinite(phase) || !std::isfinite(amplitude)) return;
    Vertex3D* vertices=_object.GetWrittableVertexList();
    const int count=_object.GetVertexCount();
    if (!vertices || count<=0 || !_finWeights.empty() || !_swimWeights.empty() || !_jellyWeights.empty()) return;
    if (_fishWeights.empty()) {
        float minX=vertices[0].position.X().AsFloat(),maxX=minX;
        for(int i=1;i<count;i++){ float x=vertices[i].position.X().AsFloat(); minX=std::min(minX,x); maxX=std::max(maxX,x); }
        _fishLength=maxX-minX; _fishWeights.reserve(count);
        for(int i=0;i<count;i++) _fishWeights.push_back(wf_render::FishWaveWeight::make(vertices[i].position.X().AsFloat(),vertices[i].position.Y().AsFloat(),minX,maxX));
    }
    const float angle=phase*6.283185307f,sine=std::sin(angle),cosine=std::cos(angle);
    amplitude=std::max(0.f,std::min(.12f,amplitude))*_fishLength;
    for(int i=0;i<count;i++) vertices[i].position.SetY(Scalar(_fishWeights[i].deform(sine,cosine,amplitude)));
}

//=============================================================================

RenderActor3D::~RenderActor3D()
{
}

void RenderActor3D::SetFinDeformation(float phase, float amplitude, float sweep, float spread)
{
    if (!std::isfinite(phase) || !std::isfinite(amplitude) || !std::isfinite(sweep) || !std::isfinite(spread)) return;
    Vertex3D* vertices=_object.GetWrittableVertexList();
    const int count=_object.GetVertexCount();
    if (!vertices || count<=0 || !_fishWeights.empty() || !_swimWeights.empty() || !_jellyWeights.empty()) return;
    if (_finWeights.empty()) {
        std::map<int,std::pair<float,float>> roots;
        // Root rows are authored explicitly, including every across-fin coordinate.
        // This one-time scan is shared by all rendering backends.
        for(int i=0;i<count;i++) {
            if(vertices[i].v.AsFloat()<=.00001f)
                roots[int(std::lround(vertices[i].u.AsFloat()*65536.f))]=
                    {vertices[i].position.X().AsFloat(),vertices[i].position.Z().AsFloat()};
        }
        _finWeights.reserve(count);
        for(int i=0;i<count;i++) {
            const Vertex3D& v=vertices[i];
            _finWeights.push_back(wf_render::FinWaveWeight::make(v.position.X().AsFloat(),
                v.position.Y().AsFloat(),v.position.Z().AsFloat(),v.u.AsFloat(),v.v.AsFloat()));
            const auto root=roots.find(int(std::lround(v.u.AsFloat()*65536.f)));
            if(root!=roots.end()) {
                _finWeights.back().rootX=root->second.first;_finWeights.back().rootZ=root->second.second;
            }
        }
    }
    const float angle=std::fmod(phase,1.f)*6.283185307f;
    const float sine=std::sin(angle),cosine=std::cos(angle);
    amplitude=std::max(0.f,std::min(.25f,amplitude));
    sweep=std::max(-.15f,std::min(.15f,sweep));
    spread=std::max(.55f,std::min(1.1f,spread));
    for(int i=0;i<count;i++) {
        vertices[i].position.SetX(Scalar(_finWeights[i].sweptX(sweep,spread)));
        vertices[i].position.SetY(Scalar(_finWeights[i].bentY(sine,cosine,amplitude)));
        vertices[i].position.SetZ(Scalar(_finWeights[i].bentZ(sine,cosine,amplitude,spread)));
    }
}

//=============================================================================

#if DO_VALIDATION
void
RenderActor3D::_Validate() const
{
	ValidatePtr(this);
	_object.Validate();
}
#endif

//============================================================================

void
RenderActor3D::SetAnimationCycle(int /*cycle*/)
{
}

//=============================================================================

bool
RenderActor3D::GetHandle(const HandleID thisHandle, Vector3& position) const
{
	return _object.GetHandle(thisHandle, position);
}

//=============================================================================

Vertex3D*
MakeCube(Memory& memory, const Vector3& min, const Vector3& max)
{
	Vertex3D* vertexList = new (memory) Vertex3D[8];
	assert(ValidPtr(vertexList));

	memcpy(vertexList,cubeVertexList,sizeof(Vertex3D)*8);

	vertexList[0].position = Vector3ToPS(Vector3(min.X(),min.Y(),max.Z()));
	vertexList[1].position = Vector3ToPS(Vector3(max.X(),min.Y(),max.Z()));
	vertexList[2].position = Vector3ToPS(Vector3(min.X(),min.Y(),min.Z()));
	vertexList[3].position = Vector3ToPS(Vector3(max.X(),min.Y(),min.Z()));
	vertexList[4].position = Vector3ToPS(Vector3(min.X(),max.Y(),max.Z()));
	vertexList[5].position = Vector3ToPS(Vector3(max.X(),max.Y(),max.Z()));
	vertexList[6].position = Vector3ToPS(Vector3(max.X(),max.Y(),min.Z()));
	vertexList[7].position = Vector3ToPS(Vector3(min.X(),max.Y(),min.Z()));

	return(vertexList);
}


Material*
MakeBoxMaterialList(Memory& memory, int count)
{
	assert(count > 0);
#pragma message ("KTS: yet another memory leak brought to you by the cool guys at KevCo")
	Material* materialList = new (memory) Material[count];
	assert(ValidPtr(materialList));
   // Preserve the old three libc draws per box so existing gameplay random
   // sequences do not shift; only the visual color uses the portable stream.
   for (int i = 0; i < 3; ++i) (void)rand();
   static wf_render::BoxColorSequence colors;
   const auto rgb = colors.NextColor();
   const Color tempColor(rgb.red, rgb.green, rgb.blue);
	for(int index=0;index < count; ++index)
	{
		materialList[index] = Material(tempColor,Material::FLAT_SHADED|Material::SOLID_COLOR,emptyTexture,NULL);
	}
	return(materialList);
}

//=============================================================================

RenderActorMatte::RenderActorMatte(Memory& /*memory*/, const _Mesh& mesh, int32 userData, AssetManager& assetManager, GfxCallbacks& gfxCallbacks)
:  _bgMatte(NULL),
   _userData(userData),
   _mesh(mesh)
{
	Validate();

	if(_bgMatte == NULL)
	{
		if ( _mesh.MatteType == 2 )
		{
			packedAssetID matteID(_mesh.Tiles);
			const char* textureName = assetManager.LookupAssetName(matteID);
         LookupTextureStruct lts = assetManager.LookupTexture(textureName,matteID.ID());
			_bgMatte = new (HALLmalloc) ScrollingMatte(textureName, lts.texture,_userData,gfxCallbacks,_mesh.GetDistance().WholePart());
			assert(ValidPtr(_bgMatte));

         packedAssetID mapID(_mesh.Map);
         _map = static_cast<const TileMap*>(assetManager.LookupAssetMemory(mapID));
         assert(ValidPtr(_map));
		}
		else
			_bgMatte = NULL;
	}
}

//=============================================================================

RenderActorMatte::~RenderActorMatte()
{
}

//=============================================================================

#if DO_VALIDATION
void
RenderActorMatte::_Validate() const
{
	ValidatePtr(this);
   assert(_userData);
//	_bgMatte.Validate();
}
#endif

//=============================================================================

void
RenderActorMatte::SetAnimationCycle(int /*cycle*/)
{
}

//=============================================================================

bool
RenderActorMatte::GetHandle(const HandleID /*thisHandle*/, Vector3& /*position*/) const
{
	return false;
}

//============================================================================

void
RenderActorMatte::Render(RenderCamera& renderCamera, const PhysicalObject& /*physicalObject*/, const Clock& /*currentTime*/)
{

//	DBSTREAM2(cgfx << "RenderActor3D::Render: RenderObject" << std::endl; )
//	Matrix34 matrix(physicalObject.GetPhysicalAttributes().orientation(),physicalObject.GetPhysicalAttributes().Position());

//	Matrix34 inverseMatrix(matrix);
//	inverseMatrix[3] = Vector3::zero;
//	renderCamera.RenderObject(_object,matrix,inverseMatrix);
//	DBSTREAM2(cgfx << "RenderActor3D::Render: done" << std::endl; )

	if ( _mesh.MatteType == 2 )
	{
		ValidatePtr(_bgMatte);

//		Scalar xSize(map->xSize*ScrollingMatte::TILE_SIZE,0);
//		Scalar ySize(map->ySize*ScrollingMatte::TILE_SIZE,0);

		const Scalar xMult(_mesh.GetXRotationScale());
		const Scalar yMult(_mesh.GetYRotationScale());
//		const Euler& camEuler = _camera->GetPhysicalAttributes().orientation();
//#pragma message ("KTS " __FILE__ ": temp until I write new camera code")
//		const Euler camEuler;
//		xOffset = (xMult * xSize * camEuler.GetC().AsScalar()).WholePart();
//		yOffset = -(yMult * ySize * camEuler.GetB().AsScalar()).WholePart();

//		FntPrint("xMult = %xl\n",_bgMatte->XRotationScale); FntPrint("yMult = %xl\n",_bgMatte->YRotationScale);
//		FntPrint("xMult = %d\n",xMult.AsLong()); 	   	   FntPrint("yMult = %d\n",yMult.AsLong());
//		FntPrint("eulera = %x\n",camEuler.GetA().AsScalar().AsLong());
//		FntPrint("eulerb = %x\n",camEuler.GetB().AsScalar().AsLong());
//		FntPrint("eulerc = %x\n",camEuler.GetC().AsScalar().AsLong());
//		FntPrint("xSize = %d\n",map->xSize); FntPrint("ySize = %d\n",map->ySize);
//		FntPrint("xOffset = %d\n",xOffset);  FntPrint("yOffset = %d\n",yOffset);

//		xOffset--;
//		yOffset++;
		renderCamera.RenderMatte(*_bgMatte, *_map, xMult, yMult);
//		_bgMatte->Render(_viewPort,*map,xOffset,yOffset);
	}
}

//=============================================================================

RenderActor3DAnimates::RenderActor3DAnimates(Memory& memory, binistream& input,int32 userData, const GfxCallbacks& callbacks)
: RenderActor3D(memory, input, userData,callbacks), _cycles(memory, input, _object)
{
	_cycles.Validate();
//	assert(input.getFilelen()>input.tellg());
	Validate();
}

//=============================================================================

RenderActor3DAnimates::~RenderActor3DAnimates()  // so that the animation class gets deleted
{
}

//=============================================================================

#if DO_VALIDATION
void
RenderActor3DAnimates::_Validate() const
{
	ValidatePtr(this);
	this->RenderActor3D::_Validate();
	_cycles.Validate();
}
#endif

//============================================================================

void
RenderActor3DAnimates::SetAnimationCycle(int cycle)
{
	assert(cycle < AnimationManager::MAX_ANIMATION_CYCLES);
	DBSTREAM3( cgfx << "SetAnimationCycle:" << cycle << std::endl; )
	_cycles.SetCycle(cycle);
}

//=============================================================================

void
RenderActor3DAnimates::Render(RenderCamera& renderCamera, const PhysicalObject& physicalObject, const Clock& currentTime)
{
	DBSTREAM2(cgfx << "RenderActor3D::Render: animate" << std::endl; )
#pragma message ("KTS: find a way to construct a RenderActor3D instead of a RenderActor3DAnimates if there is no animation")
	_cycles.Animate(currentTime.Current(),_object);
	RenderActor3D::Render(renderCamera, physicalObject, currentTime);
}

//=============================================================================

#include <cstddef>

RenderActor3DBox::RenderActor3DBox(Memory& memory, const Vector3 min, const Vector3 max)
: RenderActor3D(memory, 8,MakeCube(memory,min,max),12,cubeFaceList,MakeBoxMaterialList(memory,6))
{
//	std::cout << "RenderActor3DBox::sizeof( TriFace ) = " << sizeof( TriFace ) << std::endl;

//	std::cout << "offsetof( v1Index ) = " << offsetof( TriFace, v1Index ) << std::endl;
//	std::cout << "offsetof( v2Index ) = " << offsetof( TriFace, v2Index ) << std::endl;
//	std::cout << "offsetof( v3Index ) = " << offsetof( TriFace, v3Index ) << std::endl;
//	std::cout << "offsetof( materialIndex ) = " << offsetof( TriFace, materialIndex ) << std::endl;
//	std::cout << "offsetof( normal ) = " << offsetof( TriFace, normal ) << std::endl;

//	std::cout << "offsetof( v1Index ) = " << offsetof( TriFace, v1Index ) << std::endl;
//	std::cout << "offsetof( v1Index ) = " << offsetof( TriFace, v1Index ) << std::endl;
	Validate();
}

//=============================================================================

RenderActor3DBox::~RenderActor3DBox()
{
	// since LMalloc'ed, they will go away for us

//	DELETE_CLASS(_vertexList);
//	DELETE_CLASS(_materialList);
}

//=============================================================================

#if DO_VALIDATION
void
RenderActor3DBox::_Validate() const
{
	ValidatePtr(this);
	RenderActor3D::_Validate();
	//_vertexList->Validate();
//    if ( _materialList )
//    {
//       ValidatePtr(_materialList);
//       _materialList->Validate();
//    }
}
#endif

//=============================================================================

void
RenderActor3D::Render(RenderCamera& renderCamera, const PhysicalObject& physicalObject, const Clock& /*currentTime*/)
{
#pragma message ("KTS: optimize: should cache the matrix34 of non-moving objects")
	DBSTREAM2(cgfx << "RenderActor3D::Render:" << std::endl; )
	DBSTREAM2(cgfx << "RenderActor3D::Render: animate" << std::endl; )

	DBSTREAM2(cgfx << "RenderActor3D::Render: RenderObject" << std::endl; )
   Matrix34 matrix = physicalObject.GetPhysicalAttributes().Matrix();

//	Matrix34 inverseMatrix(matrix);
//	inverseMatrix[3] = Vector3::zero;
//#pragma message ("KTS " __FILE__ ": lights are currently incorrect, need to invert position matrix")
// inverse is not currently working, I need to step through it
//	inverseMatrix.InverseDetOne(matrix);			// rotate lights into local coordinate space

//	ciff << "position = " << physicalObject.GetPhysicalAttributes().Position() << std::endl;
//	ciff << "RenderActor3d::Render: renderCamera matrix = " << renderCamera.GetPosition() << std::endl;

	// Per-actor non-uniform scale: scale each rotation row by the matching
	// component so the actor's local +X / +Y / +Z basis vectors stretch by
	// _scale.X / Y / Z. Default _scale is (1,1,1) — no-op for actors that
	// never write a scale mailbox. (qbert stretch-and-squash, 2026-05-10.)
	matrix[0] *= _scale.X();
	matrix[1] *= _scale.Y();
	matrix[2] *= _scale.Z();

	DBSTREAM3(cgfx << "RenderActor3D::Render: matrix = " << std::endl << matrix << std::endl; )
	renderCamera.RenderObject(_object,matrix);
	DBSTREAM2(cgfx << "RenderActor3D::Render: done" << std::endl; )
}

//============================================================================

RenderActorEmitter::RenderActorEmitter( Memory& memory, const _Mesh& mesh, Emitter::EmitterParameters& ep, Emitter::ParticleParameters& pp, const Clock& currentTime ) :
	_emitter( memory, mesh, ep, pp, currentTime )
{
	Validate();
}


RenderActorEmitter::~RenderActorEmitter()
{
	Validate();
}


void
RenderActorEmitter::Render( RenderCamera& camera, const PhysicalObject& /*physicalObject*/, const Clock& currentTime )
{
	_emitter.Update( currentTime );
	_emitter.Render( camera );
}


void
RenderActorEmitter::SetAnimationCycle( int /*cycle*/ )
{
	// nothing to do
}


bool
RenderActorEmitter::GetHandle( const HandleID, Vector3& /*position*/ ) const
{
	return false;
}


#if DO_VALIDATION
void
RenderActorEmitter::_Validate() const
{
	//_emitter.Validate();
}
#endif

//============================================================================

void RenderActor3D::SetPlantGeometry(const plantgrowth::Chunk& chunk,float age,float phase,unsigned generation,bool sway,bool publish,bool textured)
{
 if(chunk.vertices.size()>=32000)return;
 bool fresh=_plantGeneration!=generation;
 if(fresh){_plantMaxBirth=0;for(const auto& f:chunk.faces)_plantMaxBirth=std::max(_plantMaxBirth,f.birth);}
 const int bucket=std::min(int(age*2),int(_plantMaxBirth*2)+1);
 if(!fresh&&age==_plantLastAge&&(!sway||phase==_plantLastPhase)&&bucket==_plantBucket)return;
 if(fresh){_plantVertices.resize(std::max(size_t(1),chunk.vertices.size()));
  if(chunk.vertices.empty())_plantVertices[0]=Vertex3D(Scalar::zero,Scalar::zero,Color(0,0,0),Vector3::zero);for(size_t i=0;i<chunk.vertices.size();i++){uint32_t c=textured?chunk.vertices[i].textureColor:chunk.vertices[i].color;_plantVertices[i]=Vertex3D(Scalar(chunk.vertices[i].u),Scalar(chunk.vertices[i].v),Color((c>>16)&255,(c>>8)&255,c&255),Vector3::zero);}_plantBucket=-1;}
 plantgrowth::Point lastRoot={1e20f,0,0};float wave=0,secondWave=0;
 for(size_t i=0;i<chunk.vertices.size();i++){const auto& v=chunk.vertices[i];if(v.root.x!=lastRoot.x||v.root.y!=lastRoot.y){lastRoot=v.root;wave=std::sin(phase*2*plantgrowth::pi/7.f+v.root.x*.10f+v.root.y*.15f);secondWave=std::sin(phase*2*plantgrowth::pi/9.f+.4f+v.root.x*.10f);}auto p=plantgrowth::deformedWave(v,age,wave,secondWave,sway);_plantVertices[i].position=Vector3(Scalar(p.x),Scalar(p.y),Scalar(p.z));}
 if(fresh||(publish&&bucket!=_plantBucket)){
  _plantFaces.clear();_plantVisibleVertices=1;_plantFaces.reserve(chunk.faces.size()+1);
  for(const auto& f:chunk.faces)if(age>=f.birth){
   TriFace face(f.a,f.b,f.c,0);const auto& a=chunk.vertices[f.a].rest;const auto& b=chunk.vertices[f.b].rest;const auto& c=chunk.vertices[f.c].rest;
   auto ab=plantgrowth::sub(b,a),ac=plantgrowth::sub(c,a);float x=ab.y*ac.z-ab.z*ac.y,y=ab.z*ac.x-ab.x*ac.z,z=ab.x*ac.y-ab.y*ac.x;float n=std::sqrt(x*x+y*y+z*z);if(n<1e-7f)continue;
   face.normal=Vector3(Scalar(x/n),Scalar(y/n),Scalar(z/n));_plantFaces.push_back(face);_plantVisibleVertices=std::max(_plantVisibleVertices,1+int(std::max(f.a,std::max(f.b,f.c))));
  }
  if(_plantFaces.empty()){TriFace face(0,0,0,0);face.normal=Vector3(Scalar::zero,Scalar::zero,Scalar::one);_plantFaces.push_back(face);}
  if(_object.SetRuntimeGeometry(_plantVisibleVertices,_plantVertices.data(),int(_plantFaces.size()),_plantFaces.data(),textured)){_plantGeneration=generation;_plantBucket=bucket;}
 }
 _plantLastAge=age;_plantLastPhase=phase;
}
