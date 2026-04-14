/*============================================================================*/
/* movebloc.ht: created from OADTYPES.S and movebloc.oas DO NOT MODIFY */
/*============================================================================*/

#include <pigsys/pigsys.hp>
#include <math/scalar.hp>
                 
                 




/*      maximum value of a long int     */

/* minimum value of a long int  */



























































#ifndef movebloc_HT
#define movebloc_HT




 struct _"Movement" {
    














                                                                                       




















	
        
        
        
        
        
        
        
        
        
	
        
        
        
        
        
        
        
        
        
        
        
        
	
	
	





        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
               
        
        
        
        
        
        
        
	
	
	







                                                                 



	int32 "MovementClass";               /* Minumum: 0 Maximum: 100 Default: Movement_KIND */
        
	int32 "Mobility";               /* Minumum: 0 Maximum: 4 Default: 0 */
  	fixed32 "Mass";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetMass"() const { return Scalar::FromFixed32("Mass"); }
	int32 "Moves Between Rooms";        /* Default: 0 */
	int32 "Movement Mailbox";               /* Minumum: 0 Maximum: 3999 Default: 1 */
	fixed32 "Step Size";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetStep Size"() const { return Scalar::FromFixed32("Step Size"); }
	fixed32 "Vertical Elasticity";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1 * 65536.0)) */   
    Scalar "GetVertical Elasticity"() const { return Scalar::FromFixed32("Vertical Elasticity"); }
	fixed32 "Horizontal Elasticity";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1 * 65536.0)) */   
    Scalar "GetHorizontal Elasticity"() const { return Scalar::FromFixed32("Horizontal Elasticity"); }
	fixed32 "Surface Friction";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 1.0 * 65536.0)) */   
    Scalar "GetSurface Friction"() const { return Scalar::FromFixed32("Surface Friction"); }

	
		int32 "At End Of Path";               /* Minumum: 0 Maximum: 5 Default: 0 */
		int32 "Object To Follow";                               /* index into master object list, = OBJECT_NULL if no reference */
		int32 "Follow Offset";                               /* index into master object list, = OBJECT_NULL if no reference */
	

	
		fixed32 "Running Acceleration";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetRunning Acceleration"() const { return Scalar::FromFixed32("Running Acceleration"); }
		fixed32 "Running Deceleration";         /* Minumum: ( ((long) -1.0 * 65536.0)) Maximum: ( ((long) 1.0 * 65536.0)) */   
    Scalar "GetRunning Deceleration"() const { return Scalar::FromFixed32("Running Deceleration"); }
		fixed32 "Max Ground Speed";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetMax Ground Speed"() const { return Scalar::FromFixed32("Max Ground Speed"); }
		fixed32 "Turn Rate";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetTurn Rate"() const { return Scalar::FromFixed32("Turn Rate"); }
	

	
		fixed32 "Crawling Acceleration";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetCrawling Acceleration"() const { return Scalar::FromFixed32("Crawling Acceleration"); }
	

	
		fixed32 "Jumping Acceleration";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetJumping Acceleration"() const { return Scalar::FromFixed32("Jumping Acceleration"); }
		fixed32 "Jumping Momentum Transfer";         /* Minumum: ( ((long) -1.0 * 65536.0)) Maximum: ( ((long) 1.0 * 65536.0)) */   
    Scalar "GetJumping Momentum Transfer"() const { return Scalar::FromFixed32("Jumping Momentum Transfer"); }
	

	
		fixed32 "Air Acceleration";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetAir Acceleration"() const { return Scalar::FromFixed32("Air Acceleration"); }
		fixed32 "Horiz Air Drag";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetHoriz Air Drag"() const { return Scalar::FromFixed32("Horiz Air Drag"); }
		fixed32 "Vert Air Drag";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetVert Air Drag"() const { return Scalar::FromFixed32("Vert Air Drag"); }
		fixed32 "Max Air Speed";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetMax Air Speed"() const { return Scalar::FromFixed32("Max Air Speed"); }
	

	
		fixed32 "Falling Acceleration";         /* Minumum: ( ((long) -1000 * 65536.0)) Maximum: ( ((long) 1000 * 65536.0)) */   
    Scalar "GetFalling Acceleration"() const { return Scalar::FromFixed32("Falling Acceleration"); }
		fixed32 "Fall Anim Threshold";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetFall Anim Threshold"() const { return Scalar::FromFixed32("Fall Anim Threshold"); }
	

	fixed32 "Stun Threshold";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetStun Threshold"() const { return Scalar::FromFixed32("Stun Threshold"); }
	fixed32 "Stun Duration";         /* Minumum: ( ((long) 0 * 65536.0)) Maximum: ( ((long) 100 * 65536.0)) */   
    Scalar "GetStun Duration"() const { return Scalar::FromFixed32("Stun Duration"); }





};



/*============================================================================*/
#endif         /* movebloc_HT */
/*============================================================================*/

