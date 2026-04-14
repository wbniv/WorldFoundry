/*============================================================================*/
/* camshot.ht: created from OADTYPES.S and camshot.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef camshot_HT
#define camshot_HT







 struct _"CamShot" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





	
	

	

	int32 "Target";                               /* index into master object list, = OBJECT_NULL if no reference */
	int32 "Follow";                               /* index into master object list, = OBJECT_NULL if no reference */

	
	fixed32 "Climb Rate";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetClimb Rate"() const { return Scalar::FromFixed32("Climb Rate"); }
	fixed32 "Elasticity";         /* Minumum: ( ((long) 1 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetElasticity"() const { return Scalar::FromFixed32("Elasticity"); }
	

	
	int32 "Track Object Mailbox";               /* Minumum: 0 Maximum: 3999 Default: 0 */
	int32 "Track Object";                               /* index into master object list, = OBJECT_NULL if no reference */
	
	
	int32 "Rotation";     /* Default: 0 */

	int32 "Position X";     /* Default: 1 */	// absolute or relative position switches, for each axis
	int32 "Position Y";     /* Default: 1 */
	int32 "Position Z";     /* Default: 1 */
	
	fixed32 "FOV";         /* Minumum: ( ((long) 1 * 65536.0)) Maximum: ( ((long) 180 * 65536.0)) */   
    Scalar "GetFOV"() const { return Scalar::FromFixed32("FOV"); }
	fixed32 "Roll";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 32000 * 65536.0)) */   
    Scalar "GetRoll"() const { return Scalar::FromFixed32("Roll"); }
	
	fixed32 "Pan Time In Seconds";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 10 * 65536.0)) */   
    Scalar "GetPan Time In Seconds"() const { return Scalar::FromFixed32("Pan Time In Seconds"); }
	
	
	

	
	fixed32 "Hither";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetHither"() const { return Scalar::FromFixed32("Hither"); }
	fixed32 "Yon";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetYon"() const { return Scalar::FromFixed32("Yon"); }
	
	

};



/*============================================================================*/
#endif         /* camshot_HT */
/*============================================================================*/

