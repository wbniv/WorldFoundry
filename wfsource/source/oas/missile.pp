/*============================================================================*/
/* missile.ht: created from OADTYPES.S and missile.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef missile_HT
#define missile_HT








 struct _"Missile" {
    

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 1 */
	





	
	int32 "Explode On Impact";        /* Default: 1 */
	fixed32 "Arming Delay";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetArming Delay"() const { return Scalar::FromFixed32("Arming Delay"); }
	fixed32 "Explosion Delay";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 3600 * 65536.0)) */   
    Scalar "GetExplosion Delay"() const { return Scalar::FromFixed32("Explosion Delay"); }
	

};



/*============================================================================*/
#endif         /* missile_HT */
/*============================================================================*/

