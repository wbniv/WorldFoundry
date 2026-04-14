/*============================================================================*/
/* activate.ht: created from OADTYPES.S and activate.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef activate_HT
#define activate_HT
























 struct _"Activation" {
    

	int32 "Activated By";               /* Minumum: 0 Maximum: 3 Default: 1 */
	
		int32 "Activated By Actor";                               /* index into master object list, = OBJECT_NULL if no reference */
		int32 "Activated By Class";                               /* index into master class list, = CLASS_NULL if no reference */
		int32 "Activated By Object List";
	

	
              

};



/*============================================================================*/
#endif         /* activate_HT */
/*============================================================================*/

