//==============================================================================
// scalar.cc:
// Copyright (c) 1996,1997,1998,1999,2000,2001,2002 World Foundry Group   
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

//#include "anmswtch.hp"
#define _SCALAR_CC
#include <math/scalar.hp>
//#include <visual/brstrm.hp>
#include <math/angle.hp>

// ------------------------------------------------------------------------


// ------------------------------------------------------------------------
// static data members
// ------------------------------------------------------------------------

const Scalar Scalar::zero = SCALAR_CONSTANT( 0.0 );
const Scalar Scalar::one = SCALAR_CONSTANT( 1.0 );
const Scalar Scalar::negativeOne = SCALAR_CONSTANT( -1.0 );
const Scalar Scalar::two = SCALAR_CONSTANT( 2.0 );
const Scalar Scalar::half = SCALAR_CONSTANT( 0.5 );
const Scalar Scalar::epsilon(0,1);


#pragma message( __FILE__ ": better Scalar min and max definitions" )
const Scalar Scalar::min( -32767, 0 );
const Scalar Scalar::max( 32767, 0 );


//==============================================================================

void
Scalar::AsText(char* buffer, int length)
{
   Validate();

   assert(ValidPtr(buffer));
   assert(length > 0);

   snprintf(buffer,length,"%f",_value);

   int pos = strlen(buffer)-1;
   // delete trailing 0's and decimal if no fractional part
   while(pos > 0 && (buffer[pos] == '0'))
   {
      buffer[pos] = 0;        
      pos--;
   }
   if(buffer[pos] == '.')
      buffer[pos] = 0;        
}

// ------------------------------------------------------------------------
// IOStream Support
// ------------------------------------------------------------------------

#if DO_IOSTREAMS
std::ostream&
operator << ( std::ostream& s, const Scalar& q )
{
   q.Validate();
   s << std::setprecision(10) << q._value;
	return s;
}

#endif // DO_IOSTREAMS

// ------------------------------------------------------------------------
// Binary I/O Stream Support
// ------------------------------------------------------------------------

binistream& operator >> ( binistream& binis, Scalar& scalar )
{

	if( binis.scalartype() == binios::float32 )
		return binis >> (uint32&)scalar._value;
	else // need to convert fixed16_16 -> float32
	{
      assert(0);
//       uint32 fixed_scalar;
//       binis >> fixed_scalar;
//       scalar._value = XBrFixedToScalar( fixed_scalar );
		return binis;
	}
}

// ------------------------------------------------------------------------

#if defined( WRITER )

binostream& operator << ( binostream& binos, const Scalar scalar )
{
  #if BASED_FLOAT
	if( binos.scalartype() == binios::float32 )
		return binos << (uint32&)scalar._value;
	else // need to convert float32 -> fixed16_16
	{
		uint32 fixed_scalar = XBrScalarToFixed( scalar._value );
		return binos << fixed_scalar;
	}
  #else // BASED_FIXED
	if( binos.scalartype() == binios::fixed16_16 )
		return binos << (uint32&)scalar._value;
	else
	{
		assert(0);
//		uint32 float_scalar = XBrScalarToFloat( scalar._value );
//		return binos << float_scalar;
		return binos;
	}
  #endif
}

#endif

// ------------------------------------------------------------------------


// ------------------------------------------------------------------------
// Trigonometric Methods
// ------------------------------------------------------------------------

Scalar
Scalar::Sin( void ) const
{
   Validate();
   return Scalar(sin(_value*(2.0*PI)));
}

// ------------------------------------------------------------------------

Scalar
Scalar::Cos( void ) const
{
   Validate();

   return Scalar(cos(_value*(2.0*PI)));
}

//-----------------------------------------------------------------------------

Angle
Scalar::ACos( void ) const
{
   Validate();
   return Angle::Radian(Scalar(acos(_value)));
}

// ------------------------------------------------------------------------

Angle
Scalar::ASin( void ) const
{
   Validate();
   double result = asin(_value);
   AssertMsg(!isnan(result),"_value = " << _value << ", result = " << result);    
   return Angle::Radian(Scalar(result));
}

// ------------------------------------------------------------------------

Angle
Scalar::ATan2( const Scalar& in ) const
{
   Validate();
   //std::cout << "ATan2: _value = " << _value << ", in._value = " << in._value << std::endl;

   FLOAT_TYPE result = atan2(in._value, _value);
   //std::cout << "in._value = " << in._value << ", _value = " << _value << ", result = " << result << std::endl;

   AssertMsg(!isnan(result),"in._value = " << in._value << ", _value = " << _value << ", result = " << result);    
   return Angle::Radian(Scalar(result));
}

// ------------------------------------------------------------------------

Angle
Scalar::ATan2Quick( const Scalar& in ) const
{
   Validate();
   assert(0);
   // kts write a fast version of this 
}

//=============================================================================
// 64 bit operations
//=============================================================================


//=============================================================================

Scalar
Scalar::Random()
{
   long temp;
#if defined(__LINUX__)
#if !(RAND_MAX == INT_MAX)
#error update rand code
#endif
	temp = rand() >> 16;
#else 
#error rand not implemented for this platform
#endif

	Scalar random_value;


   random_value._value = temp;
   random_value._value /=  65536;

	RangeCheck( Scalar::zero, random_value, Scalar::one );
	return random_value;
}

//=============================================================================

Scalar
Scalar::Random( Scalar lower, Scalar upper )
{
	AssertMsg(lower < upper,"lower = " << lower << ", upper = " << upper);
	Scalar random_value = Scalar::Random();
	random_value *= ( upper - lower );
	random_value += lower;
	RangeCheck( lower, random_value, upper );

	return random_value;
}

//=============================================================================

