/*============================================================================*/
/* objects.c: created from objects.s, DO NOT MODIFY */
/*============================================================================*/











extern "C" {
#include "oas/oad.h"
}

/*============================================================================*/
/* note this routine may return NULL, if it does, it means there is no object to add (probably a template object) */

Actor*
ConstructOadObject(int32 type, const SObjectStartupData* startData)
{
	Actor* object = NULL;
	switch(type)
	 {



        	case Actor::ActBox_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadActBox(startData); 
			break;
        	case Actor::Generator_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadGenerator(startData); 
			break;
        	case Actor::Target_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadTarget(startData); 
			break;
        	case Actor::Room_KIND:
			object = NULL; 
			break;
        	case Actor::StatPlat_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadStatPlat(startData); 
			break;
        	case Actor::Enemy_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadEnemy(startData); 
			break;
        	case Actor::Platform_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadPlatform(startData); 
			break;
        	case Actor::Missile_KIND:
			object = NULL; 
			break;
        	case Actor::Explode_KIND:
			object = NULL; 
			break;
		case Actor::Spike_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadSpike(startData); 
			break;
        	case Actor::Matte_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadMatte(startData); 
			break;
        	case Actor::Destroyer_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadDestroyer(startData); 
			break;
        	case Actor::Camera_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadCamera(startData); 
			break;
        	case Actor::Shadow_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadShadow(startData); 
			break;
        	case Actor::LevelObj_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadLevelObj(startData); 
			break;
        	case Actor::CamShot_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadCamShot(startData); 
			break;
        	case Actor::ActBoxOR_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadActBoxOR(startData); 
			break;
        	case Actor::Warp_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadWarp(startData); 
			break;
        	case Actor::Tool_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadTool(startData); 
			break;
        	case Actor::Director_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadDirector(startData); 
			break;
        	case Actor::Shield_KIND:
			object = NULL; 
			break;
        	case Actor::Player_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadPlayer(startData); 
			break;
		case Actor::Light_KIND:
			if(!(startData->objectData->oadFlags & (1<<OADFLAG_TEMPLATE_OBJECT))) 
				object = OadLight(startData); 
			break;
		case Actor::Disabled_KIND:
			object = NULL; 
			break;
		case Actor::Alias_KIND:
			object = NULL; 
			break;





        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
               
        
        
        
        
        
        
        
	
	
	



		default:

			DBSTREAM1( cerror << "object " << type << " doesn't exist" << std::endl; )
			assert(0);					// attempted to construct object not in list
			break;
	 };
	return(object);
}







/*============================================================================*/
/* note this routine will construct template objects (or even non-template objects) */

Actor*
ConstructTemplateObject(int32 type, const SObjectStartupData* startData)
{
	Actor* object = NULL;
	assert( ValidPtr( startData ) );
	startData->objectData->oadFlags |= 1<<OADFLAG_TEMPLATE_OBJECT;
	((SObjectStartupData *)startData)->roomNum = -1;

	switch(type)
	 {



        	case Actor::ActBox_KIND:
			object = OadActBox(startData); 
			break;
        	case Actor::Generator_KIND:
			object = OadGenerator(startData); 
			break;
        	case Actor::Target_KIND:
			object = OadTarget(startData); 
			break;
        	case Actor::Room_KIND:
			object = NULL; 
			break;
        	case Actor::StatPlat_KIND:
			object = OadStatPlat(startData); 
			break;
        	case Actor::Enemy_KIND:
			object = OadEnemy(startData); 
			break;
        	case Actor::Platform_KIND:
			object = OadPlatform(startData); 
			break;
        	case Actor::Missile_KIND:
			object = OadMissile(startData); 
			break;
        	case Actor::Explode_KIND:
			object = OadExplode(startData); 
			break;
		case Actor::Spike_KIND:
			object = OadSpike(startData); 
			break;
        	case Actor::Matte_KIND:
			object = OadMatte(startData); 
			break;
        	case Actor::Destroyer_KIND:
			object = OadDestroyer(startData); 
			break;
        	case Actor::Camera_KIND:
			object = OadCamera(startData); 
			break;
        	case Actor::Shadow_KIND:
			object = OadShadow(startData); 
			break;
        	case Actor::LevelObj_KIND:
			object = OadLevelObj(startData); 
			break;
        	case Actor::CamShot_KIND:
			object = OadCamShot(startData); 
			break;
        	case Actor::ActBoxOR_KIND:
			object = OadActBoxOR(startData); 
			break;
        	case Actor::Warp_KIND:
			object = OadWarp(startData); 
			break;
        	case Actor::Tool_KIND:
			object = OadTool(startData); 
			break;
        	case Actor::Director_KIND:
			object = OadDirector(startData); 
			break;
        	case Actor::Shield_KIND:
			object = OadShield(startData); 
			break;
        	case Actor::Player_KIND:
			object = OadPlayer(startData); 
			break;
		case Actor::Light_KIND:
			object = OadLight(startData); 
			break;
		case Actor::Disabled_KIND:
			object = NULL; 
			break;
		case Actor::Alias_KIND:
			object = NULL; 
			break;





        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
               
        
        
        
        
        
        
        
	
	
	



		default:
			DBSTREAM1( cerror << "object " << type << " doesn't exist"; )
			assert(0);					// attempted to construct object not in list
			break;
	 };
	return(object);
}

/*============================================================================*/

