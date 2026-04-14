/*============================================================================*/
/* actbox.ht: created from OADTYPES.S and actbox.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef actbox_HT
#define actbox_HT








 struct _"ActBox" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	






	
	int32 activatePageOffset;                 /* offset in page data for this objects page */

	int32 "MailBox";               /* Minumum: 0 Maximum: 3999 Default: 2 */
	int32 "MailBoxValue";               /* Minumum: 0 Maximum: 65536 Default: 1 */
	int32 "Activated Actor Mailbox";               /* Minumum: 0 Maximum: 3999 Default: 0 */

	
	int32 "ClearOnExit";        /* Default: 0 */
	fixed32 "Mailbox Exit Value";         /* Minumum: ( ((long) -32767 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "GetMailbox Exit Value"() const { return Scalar::FromFixed32("Mailbox Exit Value"); }
	

	int32 "Activation Mailbox";               /* Minumum: 0 Maximum: 3999 Default: 1 */
	

	
	fixed32 "Vector X";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetVector X"() const { return Scalar::FromFixed32("Vector X"); }
	fixed32 "Vector Y";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetVector Y"() const { return Scalar::FromFixed32("Vector Y"); }
	fixed32 "Vector Z";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetVector Z"() const { return Scalar::FromFixed32("Vector Z"); }
	

};



/*============================================================================*/
#endif         /* actbox_HT */
/*============================================================================*/

