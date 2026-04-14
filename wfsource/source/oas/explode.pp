/*============================================================================*/
/* explode.ht: created from OADTYPES.S and explode.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef explode_HT
#define explode_HT






 struct _"Explode" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 1 */
	





	
	fixed32 "Health Modifier";         /* Minumum: ( ((long) -100 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetHealth Modifier"() const { return Scalar::FromFixed32("Health Modifier"); }
	fixed32 "Force";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetForce"() const { return Scalar::FromFixed32("Force"); }
	

};



/*============================================================================*/
#endif         /* explode_HT */
/*============================================================================*/

