#==============================================================================
# Makefile for wfbind: Copyright (c) 1997-1999, World Foundry Group  
# Part of the World Foundry 3D video game engine/production environment
# for more information about World Foundry, see www.worldfoundry.org
#==============================================================================
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# Version 2 as published by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# or see www.fsf.org
#==============================================================================
PROGRAM = wfbind
#==============================================================================


.MS_NMAKE

ALL : $(WF_DIR)\bin\$(PROGRAM).exe

#OBJ_DIR = $(PROGRAM).obj
OBJ_DIR =

OBJS += $(OBJ_DIR)$(PROGRAM).obj

!include ../Makefile.tool

$(WF_DIR)\bin\$(PROGRAM).exe : $(PROGRAM).exe
        copy $(.SOURCE) $(.TARGET)

$(PROGRAM).exe : $(OBJS) $(PIGS_LIBS)

################################################################################

clean .PHONY :
	del /q/y *.obj *.exe
	del /q/y vc50.*
	del /q/y *.ilk *.pdb

realclean .PHONY : clean
	del /q/y *.opt

################################################################################
