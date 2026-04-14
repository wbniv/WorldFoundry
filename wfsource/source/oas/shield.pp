/*============================================================================*/
/* shield.ht: created from OADTYPES.S and shield.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef shield_HT
#define shield_HT









 struct _"Shield" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 1 */
	





	
	fixed32 "Blink Frequency";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetBlink Frequency"() const { return Scalar::FromFixed32("Blink Frequency"); }
	
	fixed32 "Shield Purchase Display";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetShield Purchase Display"() const { return Scalar::FromFixed32("Shield Purchase Display"); }
	fixed32 "Invulnerability Display";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetInvulnerability Display"() const { return Scalar::FromFixed32("Invulnerability Display"); }
	
	

};



/*============================================================================*/
#endif         /* shield_HT */
/*============================================================================*/

