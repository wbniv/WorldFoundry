//=============================================================================
// asset_accessor.cc:
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
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
//=============================================================================
// Description: AssetAccessor singleton holder. The platform-init path (Linux
// or Android) installs a concrete implementation before HALStart spawns the
// game; callers use HALGetAssetAccessor() after that.
//=============================================================================

#include <hal/asset_accessor.hp>
#include <pigsys/pigsys.hp>

namespace {
AssetAccessor* g_assetAccessor = nullptr;
}

void
HALSetAssetAccessor(AssetAccessor* accessor)
{
    g_assetAccessor = accessor;
}

AssetAccessor&
HALGetAssetAccessor()
{
    assert(g_assetAccessor);   // HAL did not install an accessor before use
    return *g_assetAccessor;
}
