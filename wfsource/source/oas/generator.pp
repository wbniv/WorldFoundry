/*============================================================================*/
/* generator.ht: created from OADTYPES.S and generator.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef generator_HT
#define generator_HT






 struct _"Generator" {
    

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





        
        int32 "Activation MailBox";               /* Minumum: 0 Maximum: 3999 Default: 1 */               // mailbox to activate this
        int32 "Object To Throw";                               /* index into master object list, = OBJECT_NULL if no reference */
        fixed32 "Generation Rate";         /* Minumum: ( ((long) 0.001 * 65536.0)) Maximum: ( ((long) 10.0 * 65536.0)) */   
    Scalar "GetGeneration Rate"() const { return Scalar::FromFixed32("Generation Rate"); }             // how long to wait between generating objects, in seconds */

	
        fixed32 "Object X Velocity";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetObject X Velocity"() const { return Scalar::FromFixed32("Object X Velocity"); }
        fixed32 "Object Y Velocity";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetObject Y Velocity"() const { return Scalar::FromFixed32("Object Y Velocity"); }
        fixed32 "Object Z Velocity";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetObject Z Velocity"() const { return Scalar::FromFixed32("Object Z Velocity"); }
	

	
        fixed32 "Random X Range";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetRandom X Range"() const { return Scalar::FromFixed32("Random X Range"); }
        fixed32 "Random Y Range";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetRandom Y Range"() const { return Scalar::FromFixed32("Random Y Range"); }
        fixed32 "Random Z Range";         /* Minumum: ( ((long) -100.0 * 65536.0)) Maximum: ( ((long) 100.0 * 65536.0)) */   
    Scalar "GetRandom Z Range"() const { return Scalar::FromFixed32("Random Z Range"); }
	
	

};



/*============================================================================*/
#endif         /* generator_HT */
/*============================================================================*/

