/*============================================================================*/
/* object.h: enumeration of all velocity game objects,  */
/*   created from  object.hs,DO NOT MODIFY */
/*============================================================================*/

#ifndef _OBJECTS_HS
#define _OBJECTS_HS








/*============================================================================*/



enum EActorKind { 
	NULL_KIND,
        ActBox_KIND,
        Generator_KIND,
        Target_KIND,
        Room_KIND,
        StatPlat_KIND,
        Enemy_KIND,
        Platform_KIND,
        Missile_KIND,
        Explode_KIND,
	Spike_KIND,
        Matte_KIND,
        Destroyer_KIND,
        Camera_KIND,
        Shadow_KIND,
        LevelObj_KIND,
        CamShot_KIND,
        ActBoxOR_KIND,
        Warp_KIND,
        Tool_KIND,
        Director_KIND,
        Shield_KIND,
        Player_KIND,
	Light_KIND,
	Disabled_KIND,
	Alias_KIND,

	};


COLTABLEHEADER
        COLTABLEENTRY(Explode,Explode,CI_SPECIAL,CI_SPECIAL)
        COLTABLEENTRY(Explode,Enemy,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(Explode,Player,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(Explode,Missile,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(Explode,Spike,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(Explode,Platform,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(Enemy,Enemy,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Enemy,Platform,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Enemy,Spike,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(Enemy,StatPlat,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Enemy,Player,CI_SPECIAL,CI_PHYSICS)
        COLTABLEENTRY(Enemy,Missile,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(Platform,Platform,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Platform,Spike,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(Platform,StatPlat,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Platform,Player,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Platform,Missile,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(Spike,Spike,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Spike,Player,CI_SPECIAL,CI_NOTHING)       
        COLTABLEENTRY(Spike,Missile,CI_SPECIAL,CI_NOTHING)
        COLTABLEENTRY(StatPlat,StatPlat,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(StatPlat,Spike,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(StatPlat,Player,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(StatPlat,Missile,CI_NOTHING,CI_SPECIAL)
        COLTABLEENTRY(Player,Player,CI_PHYSICS,CI_PHYSICS)
        COLTABLEENTRY(Player,Missile,CI_NOTHING,CI_SPECIAL)
	COLTABLEENTRY(Camera,Platform,CI_SPECIAL,CI_NOTHING)
	COLTABLEENTRY(Camera,StatPlat,CI_SPECIAL,CI_NOTHING)
	COLTABLEENTRY(Camera,Spike,CI_SPECIAL,CI_NOTHING)
COLTABLEFOOTER



/*============================================================================*/
#endif
/*============================================================================*/

