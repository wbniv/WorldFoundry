/*============================================================================*/
/* common.ht: created from OADTYPES.S and common.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef common_HT
#define common_HT




 struct _"Common" {
    






	




















	
		fixed32 "hp";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "Gethp"() const { return Scalar::FromFixed32("hp"); }
		int32 "Number Of Local Mailboxes";               /* Minumum: 0 Maximum: 40 Default: 0 */
		int32 "Poof";                               /* index into master object list, = OBJECT_NULL if no reference */
		int32 "Is Needle Gun Target";        /* Default: 0 */
		int32 "Write To Mailbox On Death";               /* Minumum: 0 Maximum: 3999 Default: 0 */
		int32 "Script";
		int32 "Script Controls Input";        /* Default: 0 */
			

		fixed32 "slopeA";         /* Minumum: ( ((long) -32768 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "GetslopeA"() const { return Scalar::FromFixed32("slopeA"); }
		fixed32 "slopeB";         /* Minumum: ( ((long) -32768 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "GetslopeB"() const { return Scalar::FromFixed32("slopeB"); }
		fixed32 "slopeC";         /* Minumum: ( ((long) -32768 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "GetslopeC"() const { return Scalar::FromFixed32("slopeC"); }
		fixed32 "slopeD";         /* Minumum: ( ((long) -32768 * 65536.0)) Maximum: ( ((long) 32767 * 65536.0)) */   
    Scalar "GetslopeD"() const { return Scalar::FromFixed32("slopeD"); }

	
	


};



/*============================================================================*/
#endif         /* common_HT */
/*============================================================================*/

