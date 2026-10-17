//============================================================================
// game/callbacks.cc:
// Copyright ( c ) 2003 World Foundry Group  
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

// ===========================================================================
// Original Author: Kevin T. Seghetti
//============================================================================

#include <game/callbacks.hp>

//==============================================================================

GameGfxCallbacks::GameGfxCallbacks(AssetManager& assetManager) :
  _assetManager(assetManager)
{

}

//==============================================================================

GameGfxCallbacks::~GameGfxCallbacks()
{

}

//==============================================================================

void
GameGfxCallbacks::_Validate() const
{
   _assetManager.Validate();
}

//==============================================================================

LookupTextureStruct 
GameGfxCallbacks::LookupTexture(const char* name, int32 userData) const                 // in streaming, this should be an asset ID
{
   return _assetManager.LookupTexture(name,userData);
}

//==============================================================================

//==============================================================================
// Shared model geometry: levcomp registers a GREF appearance's geometry in the
// appearance's own room slot, so the room bits of userData (the appearance's
// packed id) select it, and that slot is resident while the appearance loads.

int32
GameGfxCallbacks::LookupGeometry(const char* name, int32 userData) const
{
   return _assetManager.LookupAssetID(name,packedAssetID(userData).Room());
}

binistream
GameGfxCallbacks::GetGeometryStream(int32 geometryAssetID) const
{
   return _assetManager.GetAssetStream(packedAssetID(geometryAssetID));
}

const char*
GameGfxCallbacks::LookupAssetName(int32 userData) const
{
   const char* name = _assetManager.FindAssetName(userData);
   return name ? name : "";
}

//==============================================================================
