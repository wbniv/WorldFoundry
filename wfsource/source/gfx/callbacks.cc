//============================================================================
// gfx/callbacks.cc:
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

#include "callbacks.hp"
#include <cstdio>
#include <cstdlib>

//==============================================================================

GfxCallbacks::~GfxCallbacks()
{

}

//==============================================================================

int32
GfxCallbacks::LookupGeometry(const char* /*name*/, int32 /*userData*/) const
{
   return 0;		// no shared geometry: the loader reports the model and reference
}

binistream
GfxCallbacks::GetGeometryStream(int32 geometryAssetID) const
{
   // Unreachable: LookupGeometry above never returns an id. Not an assert,
   // which a release build compiles out.
   std::fprintf(stderr, "GfxCallbacks::GetGeometryStream(%08x): no shared geometry support\n", unsigned(geometryAssetID));
   std::fflush(stderr);
   _sys_assert(0, "GfxCallbacks::GetGeometryStream without LookupGeometry", __FILE__, __LINE__);
   std::abort();
}

const char*
GfxCallbacks::LookupAssetName(int32 /*userData*/) const
{
   return "";
}

//==============================================================================

void  
GfxCallbacks::Validate() const
{
#if DO_VALIDATION
   _Validate();
#endif   
}

//==============================================================================

