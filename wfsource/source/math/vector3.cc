//=============================================================================
// math/vector3.cc: 3D Vector Class
// Copyright( c ) 1996,1997,1998,1999,2000,2002 World Foundry Group  
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

// Original Autor: Kevin T. Seghetti
//=============================================================================

#define _VECTOR3_CC

//-----------------------------------------------------------------------------

#include <math/vector3.hp>

// ------------------------------------------------------------------------

const Vector3 Vector3::zero  = Vector3( SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ) );
const Vector3 Vector3::one   = Vector3( SCALAR_CONSTANT( 1 ), SCALAR_CONSTANT( 1 ), SCALAR_CONSTANT( 1 ) );
const Vector3 Vector3::unitX = Vector3( SCALAR_CONSTANT( 1 ), SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ) );
const Vector3 Vector3::unitY = Vector3( SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 1 ), SCALAR_CONSTANT( 0 ) );
const Vector3 Vector3::unitZ = Vector3( SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 1 ) );
const Vector3 Vector3::unitNegativeX = Vector3( SCALAR_CONSTANT( -1 ), SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ) );
const Vector3 Vector3::unitNegativeY = Vector3( SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( -1 ), SCALAR_CONSTANT( 0 ) );
const Vector3 Vector3::unitNegativeZ = Vector3( SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( 0 ), SCALAR_CONSTANT( -1 ) );


// ------------------------------------------------------------------------

binistream&
operator >> ( binistream& binis, Vector3& v )
{
        return binis >> v._arrScalar[0] >> v._arrScalar[1] >> v._arrScalar[2];
}

//-----------------------------------------------------------------------------

Vector3
Vector3::CrossProduct(const Vector3& other) const
{
	Vector3 result;

	result.SetX((Y()*other.Z())-(Z()*other.Y()));
	result.SetY((Z()*other.X())-(X()*other.Z()));
	result.SetZ((X()*other.Y())-(Y()*other.X()));
	return(result);
}

//-----------------------------------------------------------------------------

Scalar
Vector3::Length() const
{
   return ((X()*X()) + (Y()*Y()) + (Z()*Z())).Abs().Sqrt();
}

//-----------------------------------------------------------------------------

Scalar
Vector3::RLength() const
{
   return ((X()*X()) + (Y()*Y()) + (Z()*Z())).FastSqrt();

}

//=============================================================================
// Debug ostream support

#if DO_IOSTREAMS

std::ostream&
operator << ( std::ostream& os, const Vector3& v )
{
        os << v._arrScalar[0] << ", " << v._arrScalar[1] << ", " << v._arrScalar[2];
	return os;
}

#endif // DO_IOSTREAMS

// ------------------------------------------------------------------------
// Binary I/O Stream Support
// ------------------------------------------------------------------------

#if defined( WRITER )

binostream&
operator << ( binostream& binos, const Vector3& v )
{
        return binos << v._arrScalar[0] << v._arrScalar[1] << v._arrScalar[2];
}

//==============================================================================
#endif
//=============================================================================
