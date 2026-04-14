/*============================================================================*/
/* spike.ht: created from OADTYPES.S and spike.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef spike_HT
#define spike_HT




 struct _"Spike" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





	
	fixed32 "Health Modifier";         /* Minumum: ( ((long) -100 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetHealth Modifier"() const { return Scalar::FromFixed32("Health Modifier"); }
	int32 activatePageOffset;                 /* offset in page data for this objects page */
	

};



/*============================================================================*/
#endif         /* spike_HT */
/*============================================================================*/

