/*============================================================================*/
/* levelobj.ht: created from OADTYPES.S and levelobj.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef levelobj_HT
#define levelobj_HT






 struct _"LevelObj" {
	

	int32 moveblocPageOffset;                 /* offset in page data for this objects page */
	int32 toolsetPageOffset;                 /* offset in page data for this objects page */
	int32 commonPageOffset;                 /* offset in page data for this objects page */



	
			int32 "Mesh Name";	/* This is a packedAssetID */
	int32 meshPageOffset;                 /* offset in page data for this objects page */

	int32 shadowPageOffset;                 /* offset in page data for this objects page */
        



	
	int32 "Template Object";        /* Default: 0 */
	





	
	
		int32 "Number Of Mailboxes";               /* Minumum: 2 Maximum: 500 Default: 101 */
		int32 "Number Of Scratch Mailboxes";               /* Minumum: 0 Maximum: 500 Default: 10 */
	
	
		int32 "Number Of Temporary Objects";               /* Minumum: 0 Maximum: 500 Default: 200 */
	
	

	
			int32 "sfx0";	/* This is a packedAssetID */
			int32 "sfx1";	/* This is a packedAssetID */
			int32 "sfx2";	/* This is a packedAssetID */
			int32 "sfx3";	/* This is a packedAssetID */
			int32 "sfx4";	/* This is a packedAssetID */
			int32 "sfx5";	/* This is a packedAssetID */
			int32 "sfx6";	/* This is a packedAssetID */
			int32 "sfx7";	/* This is a packedAssetID */
			int32 "sfx8";	/* This is a packedAssetID */
			int32 "sfx9";	/* This is a packedAssetID */
			int32 "sfx10";	/* This is a packedAssetID */
			int32 "sfx11";	/* This is a packedAssetID */
			int32 "sfx12";	/* This is a packedAssetID */
			int32 "sfx13";	/* This is a packedAssetID */
			int32 "sfx14";	/* This is a packedAssetID */
			int32 "sfx15";	/* This is a packedAssetID */
			int32 "sfx16";	/* This is a packedAssetID */
			int32 "sfx17";	/* This is a packedAssetID */
			int32 "sfx18";	/* This is a packedAssetID */
			int32 "sfx19";	/* This is a packedAssetID */
			int32 "sfx20";	/* This is a packedAssetID */
			int32 "sfx21";	/* This is a packedAssetID */
			int32 "sfx22";	/* This is a packedAssetID */
			int32 "sfx23";	/* This is a packedAssetID */
			int32 "sfx24";	/* This is a packedAssetID */
			int32 "sfx25";	/* This is a packedAssetID */
			int32 "sfx26";	/* This is a packedAssetID */
			int32 "sfx27";	/* This is a packedAssetID */
			int32 "sfx28";	/* This is a packedAssetID */
			int32 "sfx29";	/* This is a packedAssetID */
			int32 "sfx30";	/* This is a packedAssetID */
			int32 "sfx31";	/* This is a packedAssetID */
			int32 "sfx32";	/* This is a packedAssetID */
			int32 "sfx33";	/* This is a packedAssetID */
			int32 "sfx34";	/* This is a packedAssetID */
			int32 "sfx35";	/* This is a packedAssetID */
			int32 "sfx36";	/* This is a packedAssetID */
			int32 "sfx37";	/* This is a packedAssetID */
			int32 "sfx38";	/* This is a packedAssetID */
			int32 "sfx39";	/* This is a packedAssetID */
			int32 "sfx40";	/* This is a packedAssetID */
			int32 "sfx41";	/* This is a packedAssetID */
			int32 "sfx42";	/* This is a packedAssetID */
			int32 "sfx43";	/* This is a packedAssetID */
			int32 "sfx44";	/* This is a packedAssetID */
			int32 "sfx45";	/* This is a packedAssetID */
			int32 "sfx46";	/* This is a packedAssetID */
			int32 "sfx47";	/* This is a packedAssetID */
			int32 "sfx48";	/* This is a packedAssetID */
			int32 "sfx49";	/* This is a packedAssetID */
			int32 "sfx50";	/* This is a packedAssetID */
			int32 "sfx51";	/* This is a packedAssetID */
			int32 "sfx52";	/* This is a packedAssetID */
			int32 "sfx53";	/* This is a packedAssetID */
			int32 "sfx54";	/* This is a packedAssetID */
			int32 "sfx55";	/* This is a packedAssetID */
			int32 "sfx56";	/* This is a packedAssetID */
			int32 "sfx57";	/* This is a packedAssetID */
			int32 "sfx58";	/* This is a packedAssetID */
			int32 "sfx59";	/* This is a packedAssetID */
			int32 "sfx60";	/* This is a packedAssetID */
			int32 "sfx61";	/* This is a packedAssetID */
			int32 "sfx62";	/* This is a packedAssetID */
			int32 "sfx63";	/* This is a packedAssetID */
			int32 "sfx64";	/* This is a packedAssetID */
			int32 "sfx65";	/* This is a packedAssetID */
			int32 "sfx66";	/* This is a packedAssetID */
			int32 "sfx67";	/* This is a packedAssetID */
			int32 "sfx68";	/* This is a packedAssetID */
			int32 "sfx69";	/* This is a packedAssetID */
			int32 "sfx70";	/* This is a packedAssetID */
			int32 "sfx71";	/* This is a packedAssetID */
			int32 "sfx72";	/* This is a packedAssetID */
			int32 "sfx73";	/* This is a packedAssetID */
			int32 "sfx74";	/* This is a packedAssetID */
			int32 "sfx75";	/* This is a packedAssetID */
			int32 "sfx76";	/* This is a packedAssetID */
			int32 "sfx77";	/* This is a packedAssetID */
			int32 "sfx78";	/* This is a packedAssetID */
			int32 "sfx79";	/* This is a packedAssetID */
			int32 "sfx80";	/* This is a packedAssetID */
			int32 "sfx81";	/* This is a packedAssetID */
			int32 "sfx82";	/* This is a packedAssetID */
			int32 "sfx83";	/* This is a packedAssetID */
			int32 "sfx84";	/* This is a packedAssetID */
			int32 "sfx85";	/* This is a packedAssetID */
			int32 "sfx86";	/* This is a packedAssetID */
			int32 "sfx87";	/* This is a packedAssetID */
			int32 "sfx88";	/* This is a packedAssetID */
			int32 "sfx89";	/* This is a packedAssetID */
			int32 "sfx90";	/* This is a packedAssetID */
			int32 "sfx91";	/* This is a packedAssetID */
			int32 "sfx92";	/* This is a packedAssetID */
			int32 "sfx93";	/* This is a packedAssetID */
			int32 "sfx94";	/* This is a packedAssetID */
			int32 "sfx95";	/* This is a packedAssetID */
			int32 "sfx96";	/* This is a packedAssetID */
			int32 "sfx97";	/* This is a packedAssetID */
			int32 "sfx98";	/* This is a packedAssetID */
			int32 "sfx99";	/* This is a packedAssetID */
			int32 "sfx100";	/* This is a packedAssetID */
			int32 "sfx101";	/* This is a packedAssetID */
			int32 "sfx102";	/* This is a packedAssetID */
			int32 "sfx103";	/* This is a packedAssetID */
			int32 "sfx104";	/* This is a packedAssetID */
			int32 "sfx105";	/* This is a packedAssetID */
			int32 "sfx106";	/* This is a packedAssetID */
			int32 "sfx107";	/* This is a packedAssetID */
			int32 "sfx108";	/* This is a packedAssetID */
			int32 "sfx109";	/* This is a packedAssetID */
			int32 "sfx110";	/* This is a packedAssetID */
			int32 "sfx111";	/* This is a packedAssetID */
			int32 "sfx112";	/* This is a packedAssetID */
			int32 "sfx113";	/* This is a packedAssetID */
			int32 "sfx114";	/* This is a packedAssetID */
			int32 "sfx115";	/* This is a packedAssetID */
			int32 "sfx116";	/* This is a packedAssetID */
			int32 "sfx117";	/* This is a packedAssetID */
			int32 "sfx118";	/* This is a packedAssetID */
			int32 "sfx119";	/* This is a packedAssetID */
			int32 "sfx120";	/* This is a packedAssetID */
			int32 "sfx121";	/* This is a packedAssetID */
			int32 "sfx122";	/* This is a packedAssetID */
			int32 "sfx123";	/* This is a packedAssetID */
			int32 "sfx124";	/* This is a packedAssetID */
			int32 "sfx125";	/* This is a packedAssetID */
			int32 "sfx126";	/* This is a packedAssetID */
			int32 "sfx127";	/* This is a packedAssetID */

	fixed32 "Sound Yon";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 500 * 65536.0)) */   
    Scalar "GetSound Yon"() const { return Scalar::FromFixed32("Sound Yon"); }
	

	
			int32 "MusicVh";	/* This is a packedAssetID */
			int32 "MusicVb";	/* This is a packedAssetID */
			int32 "MusicSeq";	/* This is a packedAssetID */
	

};



/*============================================================================*/
#endif         /* levelobj_HT */
/*============================================================================*/

