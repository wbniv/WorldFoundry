/*============================================================================*/
/* room.ht: created from OADTYPES.S and room.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef room_HT
#define room_HT



























 struct _"room" {
	int32 commonPageOffset;                 /* offset in page data for this objects page */
	

	
	
	int32 "Adjacent Room 1";                               /* index into master object list, = OBJECT_NULL if no reference */
	int32 "Adjacent Room 2";                               /* index into master object list, = OBJECT_NULL if no reference */
	
	int32 "Room Loaded Mailbox";               /* Minumum: 0 Maximum: 3999 Default: 0 */
	
};



/*============================================================================*/
#endif         /* room_HT */
/*============================================================================*/

