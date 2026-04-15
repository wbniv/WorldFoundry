//=============================================================================
// Camera.cc:
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

#include <gfx/camera.hp>
#include <hal/halbase.h>
#include <hal/platform.h>
#include <gfx/rendmatt.hp>
#include <cpplib/libstrm.hp>

#if   defined(__LINUX__)
#define scratchPadMemory _HALLmalloc
#endif
        
        

//============================================================================

#if DO_ASSERTIONS
bool RenderCamera::_renderInProgress = false;	// there can be only one (camera rendering at a time)
#endif

//============================================================================

RenderCamera::RenderCamera(ViewPort& viewPort ) : _viewPort(viewPort)
#if defined(DO_STEREOGRAM)
	,_eyeAngle(Angle::Degree(SCALAR_CONSTANT(2.5)))
	,_eyeDistance(SCALAR_CONSTANT(0.025))
#endif
{
	_viewPort.Validate();
}

//============================================================================

RenderCamera::~RenderCamera()
{
	assert(!_renderInProgress);
}

//============================================================================
#if defined(DO_STEREOGRAM)

void
RenderCamera::SetStereogram(Scalar eyeDistance, Angle eyeAngle)
{
	_eyeDistance = eyeDistance;
	_eyeAngle = eyeAngle;
}
#endif

//============================================================================

Matrix34 viewToScreen = Matrix34(
   Vector3(SCALAR_CONSTANT(2.163085),SCALAR_CONSTANT(0),SCALAR_CONSTANT(0)),
   Vector3(SCALAR_CONSTANT(0),SCALAR_CONSTANT(2.163085),SCALAR_CONSTANT(0)),
   Vector3(SCALAR_CONSTANT(0),SCALAR_CONSTANT(0),SCALAR_CONSTANT(1.001953)),
   Vector3(SCALAR_CONSTANT(0),SCALAR_CONSTANT(0),SCALAR_CONSTANT(0.200164))
   );

//============================================================================


//=============================================================================


//============================================================================

#if defined(DO_STEREOGRAM)

void
FntPrintScalar(Scalar q)
{
	Scalar temp;
	if (q < Scalar::zero)
	{
		Scalar foo((long)((~q.AsLong())+1));
		temp = foo;
		FntPrint("-");
	}
	else
		temp = q;

	// dump out the top 16 bits (whole part)
	FntPrint("%d",temp.WholePart());

	// get the bottom 16 bits (fractional part)
	Scalar frac = Scalar((long)temp.AsUnsignedFraction());					// mask off whole part
	if( frac != Scalar::zero )
	{
		FntPrint(".");

		assert(frac.WholePart() == 0);

		int digits = 0;
		const int max_scalar_fractional_digits = 6;
		while( frac.AsLong() && digits < max_scalar_fractional_digits )
		{
			frac *= SCALAR_CONSTANT(10);
			int digit = frac.WholePart();
			FntPrint("%d",digit);

			frac = Scalar((long)frac.AsUnsignedFraction());
			assert(frac.WholePart() == 0);

			++digits;
		}
	}
}

void
AdjustStereoCameraParameters(Angle& eyeAngle, Scalar& eyeDistance)
{

	// distance from screen
//      if (padd & PADR1)       vec.vz += 8;
//      if (padd & PADR2)       vec.vz -= 8;

}
#endif

//============================================================================


inline void 
ConvertToGLColor(const Color& in, GLfloat* out)
{
   out[0] = float(in.Red())/256.0;
   out[1] = float(in.Green())/256.0;
   out[2] = float(in.Blue())/256.0;
   out[3] = 1.0;
}


//==============================================================================

GLenum GLLightTable[] = 
{
   GL_LIGHT0,
   GL_LIGHT1,
   GL_LIGHT2
};

//==============================================================================

void
RenderCamera::RenderBegin()
{
    DBSTREAM1( cgfx<< "RenderCamera::RenderBegin" << std::endl; )
	assert(!_renderInProgress);
#if DO_ASSERTIONS
	_renderInProgress = true;
#endif
	_viewPort.RenderBegin();

	assert(ValidPtr(scratchPadMemory));
//	_scratchMemory = (RendererScratchVariablesStruct*)scratchPadMemory->Allocate(sizeof(RendererScratchVariablesStruct));
	_scratchMemory = new (*scratchPadMemory) RendererScratchVariablesStruct;
	assert(ValidPtr(_scratchMemory));

#if defined(DO_STEREOGRAM)
	Matrix34 tempPosition = _position;
	AdjustStereoCameraParameters(_eyeAngle,_eyeDistance);

	if(_viewPort.GetConstructionOrderTableIndex() & 1)
	{
		// kts: right eye, two inches apart
//		cscreen << "\n\n\neyedist = " << _eyeDistance << std::endl;
		Vector3 offset = Vector3(_eyeDistance, Scalar::zero, Scalar::zero) * tempPosition;
		Matrix34 rotation( Euler( Angle::zero, Angle::zero, _eyeAngle ), Vector3::zero );		// euler rotation matrix
		tempPosition[3] = Vector3::zero;
		tempPosition *= rotation;
		tempPosition[3] = offset;
	}
	else
	{
		// kts: left eye, two inches apart
		Scalar negEyeDistance = Scalar::zero - _eyeDistance;
//		cscreen << "\n\nneg: " << negEyeDistance << std::endl;
		Vector3 offset = Vector3(negEyeDistance, Scalar::zero, Scalar::zero) * tempPosition;
		Matrix34 rotation( Euler( Angle::zero, Angle::zero, -_eyeAngle ), Vector3::zero );		// euler rotation matrix
		tempPosition[3] = Vector3::zero;
		tempPosition *= rotation;
		tempPosition[3] = offset;
	}
#define _position tempPosition
#endif

#if DO_ASSERTIONS
	Scalar dtm =
#endif
	_invertedPosition.Inverse(_position);
	assertNe(dtm,Scalar::zero);		// if zero, matrix could not be inverted


   GLfloat lightBlack[] = {
       0.0, 0.0, 0.0, 1.0
   };

   GLfloat lightColor[4];

   ConvertToGLColor(_ambientColor, lightColor);
   glLightModelfv(GL_LIGHT_MODEL_AMBIENT,lightColor);

#if MAX_LIGHTS > GL_MAX_LIGHTS
#error This GL implemenation does not provide enough lights
#endif

//#if GL_LIGHT1 != (GL_LIGHT0+1) || GL_LIGHT2 != (GL_LIGHT1+1)
//#error GL light assumption violated
//#endif

   glMatrixMode(GL_MODELVIEW);               // so that lights don't get rotated
   LoadGLMatrixFromMatrix34(_invertedPosition);

    for(int index=0;index < MAX_LIGHTS;index++)
    {
        GLfloat lightDirection[4];
        lightDirection[3] = 0.0;
        
        // negate because we store the direction the light travels, where GL stores the lights position
        lightDirection[0] = -_dirLightDirections[index].X().AsFloat();
        lightDirection[1] = -_dirLightDirections[index].Y().AsFloat();
        lightDirection[2] = -_dirLightDirections[index].Z().AsFloat();
//        cout << "light direction[" << index << "]: " << _dirLightDirections[index] << endl;
//        cout << "light color: " << _dirLightColors[index] << endl;
        glLightfv(GLLightTable[index],GL_POSITION,lightDirection);
        
        ConvertToGLColor(_dirLightColors[index],lightColor);
        
        glLightfv(GLLightTable[index],GL_AMBIENT,lightBlack);
        glLightfv(GLLightTable[index],GL_DIFFUSE,lightColor);
        glLightfv(GLLightTable[index],GL_SPECULAR,lightBlack);
        AssertGLOK();
    }

   ConvertToGLColor(_fogColor,lightColor);
   glFogfv(GL_FOG_COLOR, lightColor); 
   glFogf(GL_FOG_START,_fogNear.AsFloat());
   glFogf(GL_FOG_END,_fogFar.AsFloat());
   glFogf(GL_FOG_MODE,GL_LINEAR);


#if 0
	for(int debugIndex=0;debugIndex < 3;debugIndex++)
		cout << "dirlight[" << debugIndex << "] = " << _dirLightColors[debugIndex] << std::endl;
#endif

    DBSTREAM1( cgfx<< "RenderCamera::RenderBegin: _position = " << std::endl << _position << std::endl; )
    DBSTREAM1( cgfx<< "RenderCamera::RenderBegin: _invertedPosition = " << std::endl << _invertedPosition << std::endl; )
    DBSTREAM1( cgfx<< "RenderCamera::RenderBegin done" << std::endl; )
}

//=============================================================================

void
RenderCamera::RenderEnd()
{
    DBSTREAM1( cgfx<< "RenderCamera::RenderEnd" << std::endl; )
	_viewPort.RenderEnd();
#if DO_ASSERTIONS
	_renderInProgress = false;
#endif
	scratchPadMemory->Free(_scratchMemory,sizeof(RendererScratchVariablesStruct));
    DBSTREAM1( cgfx<< "RenderCamera::RenderEnd done" << std::endl; )
}

//============================================================================

void
RenderCamera::RenderObject(RenderObject3D& object,const Matrix34& objectPosition)
{
    DBSTREAM1( cgfx<< "RenderCamera::RenderObject" << std::endl; )
	_viewPort.Validate();
	assert(_renderInProgress);
	// set up lighting

//#error kts write code here
	Matrix34 invertedObjectMatrix;
	invertedObjectMatrix[3] = Vector3::zero;
	invertedObjectMatrix.InverseDetOne(objectPosition);			// rotate lights into local coordinate space
    //cout << "Object position: " << objectPosition << std::endl;
    //cout << "invertedObjectMatrix = " << invertedObjectMatrix << std::endl;
    invertedObjectMatrix[3] = Vector3::zero;

	Matrix34 temp(objectPosition);
	temp *= _invertedPosition;

   //cout << "Final matrix: " << temp << endl;
	object.Render(_viewPort,temp);

    DBSTREAM1( cgfx<< "RenderCamera::RenderObject done" << std::endl; )
}

//============================================================================

void
RenderCamera::RenderMatte(ScrollingMatte& _matte, const TileMap& map, Scalar xMult, Scalar yMult)
{
	_viewPort.Validate();
//	cout << "RenderCamera::RenderMatte:" << std::endl;
	assert(_renderInProgress);

	Vector3 probe(Scalar::zero, Scalar::zero, Scalar::one);
	Matrix34 rotOnly(_invertedPosition);
	rotOnly[3] = Vector3::zero;
	probe *= rotOnly;
	// kts vector to euler
	Scalar x( probe[0]);
	Scalar y( probe[1]);
//	Scalar z( probe[2]);

//	FntPrint("vector = \n");
//	FntPrintScalar(probe[0]);
//	FntPrint("\n");
//	FntPrintScalar(probe[1]);
//	FntPrint("\n");
//	FntPrintScalar(probe[2]);

	Angle theta( y.ATan2( x ) );
	probe.RotateZ( -theta );
	Angle phi( probe.X().ATan2( probe.Z() ) - Angle::Revolution( SCALAR_CONSTANT( 0.25 ) ) );
	Angle r( Angle::zero );

//	FntPrint("euler = \n");
//	FntPrintScalar(r.AsScalar());
//	FntPrint("\n");
//	FntPrintScalar(phi.AsScalar());
//	FntPrint("\n");
//	FntPrintScalar(theta.AsScalar());

	Euler camEuler(r,phi,theta);

	Scalar xSize(map.xSize*ScrollingMatte::TILE_SIZE,0);
	Scalar ySize(map.ySize*ScrollingMatte::TILE_SIZE,0);
	int xOffset = -(xMult * xSize * camEuler.GetC().AsRevolution()).WholePart();
	int yOffset = -(yMult * ySize * camEuler.GetB().AsRevolution()).WholePart();

//	cscreen << "xOffset = " << xOffset << std::endl;
//	cscreen << "yOffset = " << yOffset << std::endl;

//	xOffset = 0;			            // kts temp
//	yOffset = 0;
#if defined(DO_STEREOGRAM)
#pragma message ("KTS " __FILE__ ": kludge, do proper math for mattes")
	if(_viewPort.GetConstructionOrderTableIndex() & 1)
		xOffset -= 30;
#endif

	_matte.Render(_viewPort,map,xOffset,yOffset);
//	cout << "RenderCamera::RenderObject: done" << std::endl;
}

//============================================================================

