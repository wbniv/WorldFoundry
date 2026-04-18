//=============================================================================
// lifecycle.cc:
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
// Description: Suspend/resume state as an atomic bool (Linux + Android).
//
// Linux never calls HALNotifySuspend, so HALIsSuspended always returns 0 there;
// Android's NativeActivity glue toggles the flag from the UI thread while the
// main loop reads it.
//=============================================================================

#include <hal/lifecycle.h>

#include <atomic>

namespace {
std::atomic<bool> g_suspended{false};
}

extern "C" void
HALNotifySuspend(void)
{
    g_suspended.store(true, std::memory_order_release);
}

extern "C" void
HALNotifyResume(void)
{
    g_suspended.store(false, std::memory_order_release);
}

extern "C" int
HALIsSuspended(void)
{
    return g_suspended.load(std::memory_order_acquire) ? 1 : 0;
}

extern "C" void
HALPumpSuspendedEvents(void)
{
    // No platform lifecycle events on Linux.
}
