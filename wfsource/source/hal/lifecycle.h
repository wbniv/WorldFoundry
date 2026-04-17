//=============================================================================
// lifecycle.h:
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
// Description: Suspend/resume hooks for platforms with app-lifecycle events.
//
// Linux has no suspend concept — HALIsSuspended() always returns 0.
// Android's NativeActivity wires onPause → HALNotifySuspend() and
// onResume → HALNotifyResume() (Phase 3 of the Android port plan).
//
// The main game loop checks HALIsSuspended() before rendering and skips
// render + PageFlip when true, avoiding GL calls against a torn-down context.
//=============================================================================

#ifndef _HAL_LIFECYCLE_H
#define _HAL_LIFECYCLE_H

#if defined(__cplusplus)
extern "C" {
#endif

void HALNotifySuspend(void);
void HALNotifyResume(void);
int  HALIsSuspended(void);   // 0 = running, nonzero = suspended

#if defined(__cplusplus)
}
#endif

#endif // _HAL_LIFECYCLE_H
