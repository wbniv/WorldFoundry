//=============================================================================
// display.cc: display hardware abstraction class
// Copyright ( c ) 1997,1998,1999,2000,2001 World Foundry Group  
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
// Description: The Display class encapsulates data and behavior for a single
//	 hardware screen
// Original Author: Kevin T. Seghetti
//============================================================================

#include <gfx/display.hp>

// Runtime VRAM box dimensions. Defaults preserve the historical 1024×512
// layout; main.cc overrides before Display construction when CLI flags
// are passed. See docs/plans/2026-05-30-runtime-vram-cli-overrides.md.
int Display::VRAMWidth  = 1024;
int Display::VRAMHeight = 512;

#if defined(WF_TARGET_IOS)
// iOS uses the Metal backend; windowing/drawable acquisition live in
// hal/ios/metal_view.mm rather than gfx/gl/mesa.cc. Display on iOS is a
// thin timer + projection-setup wrapper over the Metal RendererBackend.
#  include <hal/ios/display_ios.cc>
#elif defined(WF_TARGET_MACOS)
// macOS desktop (renderer-agnostic bring-up): headless Display — no window, no
// GL context. Thin timer + projection wrapper over the no-op RendererBackend.
#  include <hal/macos/display_macos.cc>
#else
#  include <gfx/gl/display.cc>
#endif

#if defined(_MSC_VER)
#pragma comment( lib, "opengl32.lib" )
#endif


//============================================================================
