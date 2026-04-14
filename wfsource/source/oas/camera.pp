/*============================================================================*/
/* camera.ht: created from OADTYPES.S and camera.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef camera_HT
#define camera_HT




 struct _"Camera" {

    

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	




	
	
	fixed32 "EyeDistance";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 10 * 65536.0)) */   
    Scalar "GetEyeDistance"() const { return Scalar::FromFixed32("EyeDistance"); }
	fixed32 "EyeAngle";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 360 * 65536.0)) */   
    Scalar "GetEyeAngle"() const { return Scalar::FromFixed32("EyeAngle"); }
	
	
	
	int32 "FoggingColor";
	fixed32 "FoggingStartDistance";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetFoggingStartDistance"() const { return Scalar::FromFixed32("FoggingStartDistance"); }
	fixed32 "FoggingCompleteDistance";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetFoggingCompleteDistance"() const { return Scalar::FromFixed32("FoggingCompleteDistance"); }
	

};



/*============================================================================*/
#endif         /* camera_HT */
/*============================================================================*/

