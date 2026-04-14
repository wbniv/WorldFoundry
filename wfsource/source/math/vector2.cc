// ------------------------------------------------------------------------
// Copyright( c ) 1997,1998,1999,2000,2002 World Foundry Group  
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

// ------------------------------------------------------------------------

#define _VECTOR2_CC

// ------------------------------------------------------------------------
// 3D Vector Class: Inlined Functions
// ------------------------------------------------------------------------

#include <math/vector2.hp>

// ------------------------------------------------------------------------

const Vector2 Vector2::zero = Vector2( Scalar::zero, Scalar::zero );
const Vector2 Vector2::one = Vector2(  Scalar::one, Scalar::one );
const Vector2 Vector2::unitX = Vector2( Scalar::one, Scalar::zero );
const Vector2 Vector2::unitY = Vector2( Scalar::zero, Scalar::one );
const Vector2 Vector2::unitNegativeX = Vector2( Scalar::negativeOne, Scalar::zero );
const Vector2 Vector2::unitNegativeY = Vector2( Scalar::zero, Scalar::negativeOne );

// ------------------------------------------------------------------------
// Debug ostream support

#if DO_IOSTREAMS

std::ostream&
operator << ( std::ostream& os, const Vector2& v )
{
        os << "( " << v._arrScalar[0] << ", " << v._arrScalar[1] << " )";
	return os;
}

#endif // DO_IOSTREAMS

// ------------------------------------------------------------------------
// Binary I/O Stream Support
// ------------------------------------------------------------------------

#if defined( WRITER )

binostream&
operator << ( binostream& binos, const Vector2& v )
{
        return binos << v._arrScalar[0] << v._arrScalar[1];
}

#endif

// ------------------------------------------------------------------------

binistream&
operator >> ( binistream& binis, Vector2& v )
{
        return binis >> v._arrScalar[0] >> v._arrScalar[1];
}

//=============================================================================

Scalar
Vector2::Length() const
{
   return ((X()*X())+(Y()*Y())).Abs().Sqrt();
}

//-----------------------------------------------------------------------------

Scalar
Vector2::RLength() const
{
   return ((X()*X())+(Y()*Y())).Abs().FastSqrt();
}

//=============================================================================
