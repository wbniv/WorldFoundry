#=============================================================================
# Makefile for timer library
#=============================================================================
# 'make all'		: Builds the timer library.
# 'make test'		: Builds a test application which exercises the timer library.
# 'make clean'		: Deletes all of the results of this makefile.
#=============================================================================

.MS_NMAKE

LIB_NAME = timer
!include ../../Makefile.env
TEST_PROG = testtime
TEST_LIBS += $(MATH) $(STREAMS) $(CPPLIB) $(MEMORY) $(GFX) $(HAL)

################################################################################

LIB_OBJS += \
	$(LIB_OBJ_DIR)clock.obj \

################################################################################

!include ../Makefile.lib

################################################################################
