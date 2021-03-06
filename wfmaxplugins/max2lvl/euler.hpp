
#ifndef _EULER_HPP
#define _EULER_HPP

// ------------------------------------------------------------------------

class ostream;
class Matrix3;

class WFEuler
{
public:
	enum
	{
		FIRST			= 0x03,
			FIRST_X			= 0x00,
			FIRST_Y			= 0x01,
			FIRST_Z			= 0x02,

		EULER_PARITY			= 0x04,
			EULER_PARITY_EVEN		= 0x00,
			EULER_PARITY_ODD		= 0x04,

		REPEAT			= 0x08,
			REPEAT_NO		= 0x00,
			REPEAT_YES		= 0x08,

		FRAME			= 0x10,
			FRAME_STATIC	= 0x00,
			FRAME_ROTATING	= 0x10,
	};

#define ORDER( a, p, r, f )\
	( FIRST_##a | EULER_PARITY_##p | REPEAT_##r | FRAME_##f )

	enum Order
	{
		XYZ_S = ORDER( X, EVEN, NO , STATIC ),
		XYX_S = ORDER( X, EVEN, YES, STATIC ),
		XZY_S = ORDER( X, ODD , NO , STATIC ),
		XZX_S = ORDER( X, ODD , YES, STATIC ),
		YZX_S = ORDER( Y, EVEN, NO , STATIC ),
		YZY_S = ORDER( Y, EVEN, YES, STATIC ),
		YXZ_S = ORDER( Y, ODD , NO , STATIC ),
		YXY_S = ORDER( Y, ODD , YES, STATIC ),
		ZXY_S = ORDER( Z, EVEN, NO , STATIC ),
		ZXZ_S = ORDER( Z, EVEN, YES, STATIC ),
		ZYX_S = ORDER( Z, ODD , NO , STATIC ),
		ZYZ_S = ORDER( Z, ODD , YES, STATIC ),

		ZYX_R = ORDER( X, EVEN, NO , ROTATING ),
		XYX_R = ORDER( X, EVEN, YES, ROTATING ),
		YZX_R = ORDER( X, ODD , NO , ROTATING ),
		XZX_R = ORDER( X, ODD , YES, ROTATING ),
		XZY_R = ORDER( Y, EVEN, NO , ROTATING ),
		YZY_R = ORDER( Y, EVEN, YES, ROTATING ),
		ZXY_R = ORDER( Y, ODD , NO , ROTATING ),
		YXY_R = ORDER( Y, ODD , YES, ROTATING ),
		YXZ_R = ORDER( Z, EVEN, NO , ROTATING ),
		ZXZ_R = ORDER( Z, EVEN, YES, ROTATING ),
		XYZ_R = ORDER( Z, ODD , NO , ROTATING ),
		ZYZ_R = ORDER( Z, ODD , YES, ROTATING ),
	};
#undef ORDER

private:
	Order _order;
	double _axes[3];

public:
	WFEuler( WFEuler::Order order = XYZ_S );
	WFEuler( WFEuler::Order order, double a, double b, double c );
	WFEuler( WFEuler::Order order, const Matrix3& );

	WFEuler::Order GetOrder() const { return _order; }
	double GetA() const { return _axes[0]; }
	double GetB() const { return _axes[1]; }
	double GetC() const { return _axes[2]; }

	void SetOrder( WFEuler::Order order ) { _order = order; }
	void SetA( double a ) { _axes[0] = a; }
	void SetB( double b ) { _axes[1] = b; }
	void SetC( double c ) { _axes[2] = c; }

	// row access
	double& operator [] ( int idxAxis );
		// read/write access to angle data, i = 0..2
	const double& operator [] ( int idxAxis ) const;
		// read-only access to angle data, i = 0..2

	void AsMatrix3( Matrix3& ) const;

	// conditional operators
	int operator == ( const WFEuler& ) const;
	int operator != ( const WFEuler& ) const;
	int operator <  ( const WFEuler& ) const;
	int operator <= ( const WFEuler& ) const;
	int operator >  ( const WFEuler& ) const;
	int operator >= ( const WFEuler& ) const;

	friend ostream& operator << ( ostream&, const WFEuler& );
};

// ------------------------------------------------------------------------

#endif /* _EULER_HPP */
