/*============================================================================*/
/* matte.ht: created from OADTYPES.S and matte.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef matte_HT
#define matte_HT






 struct _"Matte" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





	
	

};



/*============================================================================*/
#endif         /* matte_HT */
/*============================================================================*/

