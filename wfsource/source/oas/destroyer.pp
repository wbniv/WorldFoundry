/*============================================================================*/
/* destroyer.ht: created from OADTYPES.S and destroyer.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef destroyer_HT
#define destroyer_HT




 struct _"Destroyer" {
    

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





	
	int32 "Activation MailBox";               /* Minumum: 0 Maximum: 3999 Default: 1 */		// mailbox to activate this
	int32 activatePageOffset;                 /* offset in page data for this objects page */
	

};



/*============================================================================*/
#endif         /* destroyer_HT */
/*============================================================================*/

