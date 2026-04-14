/*============================================================================*/
/* tool.ht: created from OADTYPES.S and tool.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef tool_HT
#define tool_HT








 struct _"Tool" {
    

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 1 */
	





	
	int32 "Activation Script";

	int32 "Object To Throw";                               /* index into master object list, = OBJECT_NULL if no reference */
	int32 "Activation Cost";               /* Minumum: 0 Maximum: 100 Default: 1 */
	int32 "Autofire";        /* Default: 0 */
	int32 "Moving Throw Percentage";               /* Minumum: 0 Maximum: 100 Default: 25 */

	int32 "Type";               /* Minumum: 0 Maximum: 3 Default: 1 */
	int32 "Activation Button";               /* Minumum: 0 Maximum: 7 Default: 1 */

	fixed32 "Recharge";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetRecharge"() const { return Scalar::FromFixed32("Recharge"); }

	fixed32 "Horiz Speed";         /* Minumum: ( ((long) 0.0 * 65536.0)) Maximum: ( ((long) 360.0 * 65536.0)) */   
    Scalar "GetHoriz Speed"() const { return Scalar::FromFixed32("Horiz Speed"); }
	fixed32 "Vert Speed";         /* Minumum: ( ((long) 0.0 * 65536.0)) Maximum: ( ((long) 360.0 * 65536.0)) */   
    Scalar "GetVert Speed"() const { return Scalar::FromFixed32("Vert Speed"); }


	
	fixed32 "Max Range";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 10000 * 65536.0)) */   
    Scalar "GetMax Range"() const { return Scalar::FromFixed32("Max Range"); }
	fixed32 "Beam Spread Angle";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1 * 65536.0)) */   
    Scalar "GetBeam Spread Angle"() const { return Scalar::FromFixed32("Beam Spread Angle"); }
	
	

};



/*============================================================================*/
#endif         /* tool_HT */
/*============================================================================*/

