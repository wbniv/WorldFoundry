# WorldFoundry Compile-Time Switches

*Generated 2026-04-14 · 929 unique switches · sorted most→least used*

| Switch | # | Files |
|--------|--:|-------|
| `#define __LINUX__` | 33 | |
| | | `source/cpplib/libstrm.cc  source/cpplib/stdstrm.{cc,hp}  source/cpplib/strmnull.{cc,hp}  source/game/gamestrm.cc  source/game/main.cc  source/gfx/camera.cc  source/gfx/display.hp  source/gfx/otable.hp  source/gfx/rendmatt.cc  source/gfx/gl/display.cc  source/hal/platform.h  source/hal/time.{cc,hp}  source/ini/profile.cc  source/math/scalar.{cc,hpi}  source/movement/inputmap.hp  source/oas/levelcon.h  source/pigsys/_cf_linux.cc  source/pigsys/assert.hp  source/pigsys/cf_linux.h  source/pigsys/clib.h  source/pigsys/genfh.hp  source/pigsys/memory.hp  source/pigsys/minmax.hp  source/pigsys/pigsys.{cc,hp}  source/pigsys/pigtypes.h  source/streams/binstrm.{cc,hp}  source/streams/strtest.cc` |
| `#define WRITER` | 24 | |
| | | `source/cpplib/afftform.cc  source/game/level.cc  source/gfx/ccycle.cc  source/gfx/handle.{cc,hp}  source/math/angle.{cc,hp}  source/math/euler.{cc,hp}  source/math/matrix34.{cc,hp}  source/math/matrix3t.{cc,hp}  source/math/quat.{cc,hp}  source/math/scalar.{cc,hp}  source/math/vector2.{cc,hp}  source/math/vector3.{cc,hp}  source/streams/binstrm.{cc,hp,hpi}` |
| `#define USE_ORDER_TABLES` | 22 | |
| | | `source/gfx/display.{hp,hpi}  source/gfx/otable.hp  source/gfx/rendmatt.{cc,hp}  source/gfx/rendobj2.{cc,hp}  source/gfx/rendobj3.{cc,hpi}  source/gfx/viewport.{cc,hp,hpi}  source/gfx/gl/display.cc  source/gfx/gl/viewport.cc  source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc` |
| `#define VIDEO_MEMORY_IN_ONE_PIXELMAP` | 16 | |
| | | `source/gfx/display.{hp,hpi}  source/gfx/gfxtest.cc  source/gfx/rendmatt.cc  source/gfx/vmem.{cc,hp}  source/gfx/gl/display.cc  source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc  source/physics/physicstest.cc` |
| `#define SCALAR_TYPE_DOUBLE` | 13 | |
| | | `source/game/level.cc  source/game/main.cc  source/math/angle.hpi  source/math/mathtest.cc  source/math/matrix34.{hp,hpi}  source/math/scalar.{cc,hp,hpi}  source/math/vector2.cc  source/math/vector3.cc  source/physics/ode/ode.hp  source/savegame/sgout.cc` |
| `#define SCALAR_TYPE_FIXED` | 12 | |
| | | `source/game/level.cc  source/game/main.cc  source/math/mathtest.cc  source/math/matrix34.{hp,hpi}  source/math/scalar.{cc,hp,hpi}  source/math/vector2.cc  source/math/vector3.cc  source/physics/ode/ode.hp  source/savegame/sgout.cc` |
| `#define DESIGNER_CHEATS` | 11 | |
| | | `source/asset/assslot.cc  source/game/actor.hp  source/game/game.cc  source/game/main.cc  source/game/player.cc  source/gfx/vmem.{cc,hp}  source/hal/linux/platform.cc  source/pigsys/pigsys.{cc,hp}  source/pigsys/psysvers.h` |
| `#define FLAG_GOURAUD` | 8 | |
| | | `source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc` |
| `#define FLAG_LIGHTING` | 8 | |
| | | `source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc` |
| `#define FLAG_TEXTURE` | 8 | |
| | | `source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc` |
| `#define PRINT_EVERYTHING` | 8 | |
| | | `source/gfx/glpipeline/rendfcl.cc  source/gfx/glpipeline/rendfcp.cc  source/gfx/glpipeline/rendftl.cc  source/gfx/glpipeline/rendftp.cc  source/gfx/glpipeline/rendgcl.cc  source/gfx/glpipeline/rendgcp.cc  source/gfx/glpipeline/rendgtl.cc  source/gfx/glpipeline/rendgtp.cc` |
| `#define OLD_IOSTREAMS` | 7 | |
| | | `source/cpplib/stdstrm.hp  source/cpplib/strmnull.{cc,hp}  source/ini/profile.cc  source/pigsys/assert.hp  source/pigsys/genfh.hp  source/pigsys/pigsys.hp` |
| `#define _MSC_VER` | 7 | |
| | | `source/asset/assettest.cc  source/cpplib/cpptest.cc  source/cpplib/stdstrm.hp  source/hal/tasker.cc  source/math/mathtest.cc  source/oas/oad.h  source/scripting/scriptingtest.cc` |
| `#define DO_SLOW_STEREOGRAM` | 6 | |
| | | `source/game/game.cc  source/gfx/display.{hp,hpi}  source/gfx/gfxtest.cc  source/gfx/otable.hp  source/particle/test.cc` |
| `#define DO_STEREOGRAM` | 6 | |
| | | `source/game/camera.cc  source/game/game.cc  source/gfx/camera.{cc,hp}  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define DO_MULTITASKING` | 5 | |
| | | `source/hal/hal.{cc,h}  source/hal/halbase.h  source/hal/message.cc  source/hal/tasker.cc` |
| `#define SIZE` | 5 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc  source/physics/physicstest.cc  source/renderassets/rendcrow.cc` |
| `#define STREAMENTRY` | 5 | |
| | | `source/cpplib/libstrm.{cc,hp}  source/game/gamestrm.{cc,hp}  source/game/main.cc` |
| `#define __PSX__` | 5 | |
| | | `source/cpplib/afftform.cc  source/game/main.cc  source/gfx/camera.cc  source/math/matrix3t.cc  source/streams/binstrm.cc` |
| `#define ADJUST_ANGLE` | 4 | |
| | | `source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc  source/physics/physicstest.cc` |
| `#define ADJUST_DELTA` | 4 | |
| | | `source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc  source/physics/physicstest.cc` |
| `#define MODEL_COUNT` | 4 | |
| | | `source/anim/animtest.cc  source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define NULL_STREAM` | 4 | |
| | | `source/cpplib/libstrm.cc  source/game/gamestrm.cc  source/pigsys/pigsys.hp  source/streams/binstrm.cc` |
| `#define PHYSICS_ENGINE_ODE` | 4 | |
| | | `source/game/level.cc  source/physics/physical.{cc,hp,hpi}` |
| `#define TASKER` | 4 | |
| | | `source/game/level.{cc,hp}  source/game/main.cc  source/hal/hal.cc` |
| `#define XYLIMIT` | 4 | |
| | | `source/anim/animtest.cc  source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define ZMAXLIMIT` | 4 | |
| | | `source/anim/animtest.cc  source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define ZMINLIMIT` | 4 | |
| | | `source/anim/animtest.cc  source/anim/preview.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define _SYS_NOCHECK_DIRECT_STD` | 4 | |
| | | `source/pigsys/_atexit.cc  source/pigsys/pigsys.cc  source/pigsys/scanf.cc  source/pigsys/stack.cc` |
| `#define ANIMATE_MATERIAL` | 3 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define ANIMATE_VERTEX` | 3 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define EXTERNSTREAMENTRY` | 3 | |
| | | `source/game/gamestrm.{cc,hp}  source/game/main.cc` |
| `#define GFX_ZBUFFER` | 3 | |
| | | `source/gfx/display.hp  source/gfx/pixelmap.cc  source/gfx/gl/display.cc` |
| `#define JOYSTICK_RECORDER` | 3 | |
| | | `source/game/level.{cc,hp}  source/game/main.cc` |
| `#define LASTCHAR` | 3 | |
| | | `source/audiofmt/log.cc  source/audiofmt/sox.cc  source/audiofmt/util.cc` |
| `#define PHYSICS_ENGINE_WF` | 3 | |
| | | `source/physics/physical.{cc,hp,hpi}` |
| `#define PI` | 3 | |
| | | `source/audiofmt/resdefs.h  source/math/angle.hpi  source/math/tables.cc` |
| `#define READ_INTERMEDIATE_ANIM_FORMAT` | 3 | |
| | | `source/anim/anim.{cc,hp}  source/anim/animcycl.cc` |
| `#define RENDERER_BRENDER` | 3 | |
| | | `source/game/explode.cc  source/gfx/ccycle.{cc,hp}` |
| `#define SCALAR_TYPE_FLOAT` | 3 | |
| | | `source/math/scalar.{hp,hpi}  source/physics/ode/ode.hp` |
| `#define SYS_INT32` | 3 | |
| | | `source/oas/oad.h  source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define TEST_2D` | 3 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define TEST_3D` | 3 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define TEST_MODEL_LOAD` | 3 | |
| | | `source/anim/animtest.cc  source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define TEST_TEXTURES` | 3 | |
| | | `source/gfx/gfxtest.cc  source/particle/test.cc  source/physics/physicstest.cc` |
| `#define _PIGSYS_H` | 3 | |
| | | `source/pigsys/_atexit.h  source/pigsys/endian.h  source/pigsys/pigsys.hp` |
| `#define __GNUC__` | 3 | |
| | | `source/gfx/prim.hp  source/pigsys/assert.hp  source/pigsys/pigsys.hp` |
| `#define ABS` | 2 | |
| | | `source/audiofmt/resdefs.h  source/pigsys/pigsys.hp` |
| `#define ANIMATE_OBJECT` | 2 | |
| | | `source/anim/animtest.cc  source/anim/preview.cc` |
| `#define ANIMATE_POSITION` | 2 | |
| | | `source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define CHARBITS` | 2 | |
| | | `source/regexp/regexp.cc  source/regexp/regsub.cc` |
| `#define CI_NOTHING` | 2 | |
| | | `source/physics/collision.{cc,hp}` |
| `#define CI_PHYSICS` | 2 | |
| | | `source/physics/collision.{cc,hp}` |
| `#define CI_SPECIAL` | 2 | |
| | | `source/physics/collision.{cc,hp}` |
| `#define DEFINE_MAIN` | 2 | |
| | | `source/gfx/gfxtest.cc  source/particle/test.cc` |
| `#define DUMPDATA` | 2 | |
| | | `source/memory/lmalloc.cc  source/memory/realmalloc.cc` |
| `#define ENTRIES` | 2 | |
| | | `source/math/mathtest.cc  source/math/tables.cc` |
| `#define FAST_ALAW_CONVERSION` | 2 | |
| | | `source/audiofmt/libst.{cc,h}` |
| `#define FAST_ULAW_CONVERSION` | 2 | |
| | | `source/audiofmt/libst.{cc,h}` |
| `#define HIERARCHY_HP` | 2 | |
| | | `source/cpplib/hierarch.{hp,hpi}` |
| `#define INT16_MAX` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigsys.hp` |
| `#define LINUXSOUND` | 2 | |
| | | `source/audiofmt/handlers.cc  source/audiofmt/sbdsp.cc` |
| `#define LISTEMPTY` | 2 | |
| | | `source/baseobject/msgport.hpi  source/hal/_list.cc` |
| `#define MAILBOXENTRY` | 2 | |
| | | `source/mailbox/mailbox.hp  source/scripting/tcl.cc` |
| `#define MAX` | 2 | |
| | | `source/audiofmt/resdefs.h  source/pigsys/minmax.hp` |
| `#define MAXCOMM` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define MAX_COMMAND_LINES` | 2 | |
| | | `source/console/test.cc  source/menu/menutest.cc` |
| `#define MEMPOOL_ENTRIES` | 2 | |
| | | `source/hal/mempool.cc  source/memory/mempool.cc` |
| `#define MEMPOOL_FILLVALUE` | 2 | |
| | | `source/hal/mempool.cc  source/memory/mempool.cc` |
| `#define MEMPOOL_REALTRACKING` | 2 | |
| | | `source/hal/mempool.cc  source/memory/mempool.cc` |
| `#define MEMPOOL_SIZE` | 2 | |
| | | `source/hal/mempool.cc  source/memory/mempool.cc` |
| `#define MEMPOOL_TRASHMEMORY` | 2 | |
| | | `source/hal/mempool.cc  source/memory/mempool.cc` |
| `#define MIDI_MUSIC` | 2 | |
| | | `source/game/level.{cc,hp}` |
| `#define MIDI_UNITY` | 2 | |
| | | `source/audiofmt/smp.cc  source/audiofmt/st.h` |
| `#define MIN` | 2 | |
| | | `source/audiofmt/resdefs.h  source/pigsys/minmax.hp` |
| `#define MINCOMM` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define NDEBUG` | 2 | |
| | | `source/gfxfmt/bitmap.cc  source/iffwrite/_iffwr.cc` |
| `#define NO_ASSERT_EXPR` | 2 | |
| | | `source/pigsys/assert.hp  source/pigsys/pigsys.hp` |
| `#define PHYSICAL_INTERNAL_EULER` | 2 | |
| | | `source/physics/physical.{hp,hpi}` |
| `#define PHYSICAL_INTERNAL_MATRIX` | 2 | |
| | | `source/physics/physical.{hp,hpi}` |
| `#define SF_BUFSIZE` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_COMMENT` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_END` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_MAGIC` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_MAXAMP` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_MAXCHAN` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SF_SHORT` | 2 | |
| | | `source/audiofmt/sfheader.h  source/audiofmt/sfircam.h` |
| `#define SIZEOF_BSD_HEADER` | 2 | |
| | | `source/audiofmt/sf.cc  source/audiofmt/sfheader.h` |
| `#define SW_DBSTREAM` | 2 | |
| | | `source/recolib/global.hp  source/streams/dbstrm.hp` |
| `#define SYS_BOOL` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_INT16` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_INT8` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_LARGEINT` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_SMALLINT` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_TOOL` | 2 | |
| | | `source/pigsys/pigsys.hp  source/recolib/global.hp` |
| `#define SYS_UCHAR` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_UINT` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_UINT16` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_UINT32` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_UINT8` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_ULONG` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define SYS_USHORT` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define TEST_JOYSTICK` | 2 | |
| | | `source/hal/_input.h  source/hal/halbase.h` |
| `#define TEST_MAIN` | 2 | |
| | | `source/shell/hiscore.cc  source/shell/score.cc` |
| `#define TEST_SIGNAL` | 2 | |
| | | `source/hal/_signal.cc  source/hal/halbase.h` |
| `#define TOOLTIPS` | 2 | |
| | | `source/attrib/oaddlg.{cc,hp}` |
| `#define UCHARAT` | 2 | |
| | | `source/regexp/regexp.cc  source/regexp/regsub.cc` |
| `#define UNIMPLEMENTED` | 2 | |
| | | `source/game/actor.cc  source/hal/halbase.h` |
| `#define VMS` | 2 | |
| | | `source/audiofmt/sox.cc  source/audiofmt/st.h` |
| `#define WF_BIG_ENDIAN` | 2 | |
| | | `source/pigsys/cf_linux.h  source/pigsys/pigsys.hp` |
| `#define _CAMSHOT_CC` | 2 | |
| | | `source/game/camshot.{cc,hp}` |
| `#define _DESTROY_CC` | 2 | |
| | | `source/game/destroyer.{cc,hp}` |
| `#define _EULER_CC` | 2 | |
| | | `source/math/euler.{cc,hp}` |
| `#define _IFFREAD_CC` | 2 | |
| | | `source/iff/iffread.{cc,hp}` |
| `#define _INPUTDIG_CC` | 2 | |
| | | `source/input/inputdig.cc  source/orphaned/inputdig.cc` |
| `#define _MAX_PATH` | 2 | |
| | | `source/pigsys/cf_linux.h  source/pigsys/genfh.hp` |
| `#define _MOVEFOLL_CC` | 2 | |
| | | `source/movement/movefoll.{cc,hp}` |
| `#define _MSGPORT_CC` | 2 | |
| | | `source/baseobject/msgport.{cc,hp}` |
| `#define _OBJECTS_HS` | 2 | |
| | | `source/oas/objects.{e,h}` |
| `#define _STDDEF_H` | 2 | |
| | | `source/oas/pigtool.h  source/pigsys/pigtypes.h` |
| `#define _WARP_CC` | 2 | |
| | | `source/game/warp.{cc,hp}` |
| `#define __DOOMSTICK__` | 2 | |
| | | `source/movement/movement.{cc,hp}` |
| `#define __OS2__` | 2 | |
| | | `source/audiofmt/sox.cc  source/audiofmt/st.h` |
| `#define __WIN__` | 2 | |
| | | `source/gfx/material.cc  source/pigsys/memory.hp` |
| `#define ACCUMULATE` | 1 | |
| | | `source/math/matrix34.cc` |
| `#define ACLIP` | 1 | |
| | | `source/audiofmt/libst.cc` |
| `#define ACTIVATE_HP` | 1 | |
| | | `source/physics/activate.hp` |
| `#define ACTUAL_ANGLE_FOR_SHOOTING` | 1 | |
| | | `source/game/toolngun.cc` |
| `#define ADJACENT_ROOM_NULL` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define AFFTFORM_HPI` | 1 | |
| | | `source/cpplib/afftform.hpi` |
| `#define ALAW` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define ALIGN_POW2` | 1 | |
| | | `source/cpplib/align.hp` |
| `#define ANIMATE_ROTATION` | 1 | |
| | | `source/gfx/gfxtest.cc` |
| `#define ANIMATION` | 1 | |
| | | `source/anim/animmang.hp` |
| `#define ANY` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define ANYBUT` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define ANYOF` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define APSTUDIO_INVOKED` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define APSTUDIO_READONLY_SYMBOLS` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ARM` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define ASSERTIONS` | 1 | |
| | | `source/pigsys/assert.hp` |
| `#define ASSERT_DEBUG_MENU` | 1 | |
| | | `source/pigsys/assert.cc` |
| `#define ASSETMANAGER_JUSTDEFS` | 1 | |
| | | `source/asset/assets.hp` |
| `#define ASSET_EXTENSION` | 1 | |
| | | `source/streams/asset.hp` |
| `#define ASSIGNOSTREAM` | 1 | |
| | | `source/cpplib/stdstrm.hp` |
| `#define ATTRIB_HP` | 1 | |
| | | `source/attrib/attrib.hp` |
| `#define ATTRIB_TYPES_HP` | 1 | |
| | | `source/attrib/types.hp` |
| `#define AUDIO_BUFFER_HP` | 1 | |
| | | `source/audio/buffer.hp` |
| `#define AUDIO_DEVICE_HP` | 1 | |
| | | `source/audio/device.hp` |
| `#define AUDIO_ENCODING_ALAW` | 1 | |
| | | `source/audiofmt/g72x.h` |
| `#define AUDIO_ENCODING_LINEAR` | 1 | |
| | | `source/audiofmt/g72x.h` |
| `#define AUDIO_ENCODING_ULAW` | 1 | |
| | | `source/audiofmt/g72x.h` |
| `#define BACK` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define BAD_ENDIAN` | 1 | |
| | | `source/pigsys/endian.cc` |
| `#define BASE_OBJECT_HP` | 1 | |
| | | `source/baseobject/baseobject.hp` |
| `#define BIAS` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define BI_BITFIELDS` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define BI_RGB` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define BI_RLE4` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define BI_RLE8` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define BOL` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define BRANCH` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define BR_BLU` | 1 | |
| | | `source/attrib/buttons/notupg~1/colorpck.cc` |
| `#define BR_COLOUR_RGB` | 1 | |
| | | `source/attrib/buttons/notupg~1/colorpck.cc` |
| `#define BR_GRN` | 1 | |
| | | `source/attrib/buttons/notupg~1/colorpck.cc` |
| `#define BR_RED` | 1 | |
| | | `source/attrib/buttons/notupg~1/colorpck.cc` |
| `#define BUFINCR` | 1 | |
| | | `source/audiofmt/hcom.cc` |
| `#define BUTTON` | 1 | |
| | | `source/attrib/attrib.cc` |
| `#define BUTTONS_CHECKBOX_HP` | 1 | |
| | | `source/attrib/buttons/checkbox.hp` |
| `#define BUTTONS_DROPMENU_HP` | 1 | |
| | | `source/attrib/buttons/dropmenu.hp` |
| `#define BUTTONS_FILENAME_HP` | 1 | |
| | | `source/attrib/buttons/filename.hp` |
| `#define BUTTONS_GROUP_HP` | 1 | |
| | | `source/attrib/buttons/group.hp` |
| `#define BUTTONS_PROPSHET_HP` | 1 | |
| | | `source/attrib/buttons/propshet.hp` |
| `#define BUTTONS_STRING_HP` | 1 | |
| | | `source/attrib/buttons/string.hp` |
| `#define BUTTON_CAMERA_REFERENCE` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_CLASS_REFERENCE` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_EXTRACT_CAMERA` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_FILENAME` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_FIXED16` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_FIXED32` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_GROUP_START` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_GROUP_STOP` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_INT16` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_INT32` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_INT8` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_LIGHT_REFERENCE` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_MESHNAME` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_OBJECT_REFERENCE` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_PROPERTY_SHEET` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_STRING` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_WAVEFORM` | 1 | |
| | | `source/oas/oad.h` |
| `#define BUTTON_XDATA` | 1 | |
| | | `source/oas/oad.h` |
| `#define CCYC_HP` | 1 | |
| | | `source/gfx/ccyc.hp` |
| `#define CDDA_CD_HP` | 1 | |
| | | `source/cdda/cd.hp` |
| `#define CHANNEL_NULL` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define CHAN_1` | 1 | |
| | | `source/audiofmt/pick.cc` |
| `#define CHAN_2` | 1 | |
| | | `source/audiofmt/pick.cc` |
| `#define CHAN_3` | 1 | |
| | | `source/audiofmt/pick.cc` |
| `#define CHAN_4` | 1 | |
| | | `source/audiofmt/pick.cc` |
| `#define CLASSREF_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/classref.hp` |
| `#define CLIMB_RATE` | 1 | |
| | | `source/movement/movement.cc` |
| `#define CLIP01` | 1 | |
| | | `source/gfx/material.cc` |
| `#define CLOSE` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define COLORPCK_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/colorpck.hp` |
| `#define COLOURCYCLE_HP` | 1 | |
| | | `source/gfx/ccycle.hp` |
| `#define COMBOBOX_H` | 1 | |
| | | `source/attrib/buttons/combobox.hp` |
| `#define COMMA` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define COMMENTLEN` | 1 | |
| | | `source/audiofmt/smp.cc` |
| `#define COMMONBLOCK_HP` | 1 | |
| | | `source/baseobject/commonblock.hp` |
| `#define CONSOLE_CONSOLE_HP` | 1 | |
| | | `source/console/console.hp` |
| `#define CONSOLE_HDUMP_HP` | 1 | |
| | | `source/console/hdump.hp` |
| `#define CONSOLE_MENU_HP` | 1 | |
| | | `source/console/menu.hp` |
| `#define CONSOLE_TEXTBUFF_HP` | 1 | |
| | | `source/console/textbuff.hp` |
| `#define CREATEANDASSIGNOSTREAM` | 1 | |
| | | `source/cpplib/stdstrm.hp` |
| `#define CREATENULLSTREAM` | 1 | |
| | | `source/cpplib/strmnull.hp` |
| `#define CYCLE_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/cycle.hp` |
| `#define C_LINKAGE` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define D0` | 1 | |
| | | `source/audiofmt/pred.cc` |
| `#define D1` | 1 | |
| | | `source/audiofmt/pred.cc` |
| `#define D2R` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define DBSTREAM1` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define DBSTREAM2` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define DBSTREAM3` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define DBSTREAM4` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define DBSTREAM5` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define DEBUG` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define DEBUG_MEMORY` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define DEC_INV_MAGIC` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define DEC_MAGIC` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define DEFAULT_FREQUENCY` | 1 | |
| | | `source/audiofmt/sound2su.cc` |
| `#define DELAYBUFSIZ` | 1 | |
| | | `source/audiofmt/echo.cc` |
| `#define DENSITY` | 1 | |
| | | `source/physics/physical.hpi` |
| `#define DIRECTORY_SEPARATOR` | 1 | |
| | | `source/pigsys/cf_linux.h` |
| `#define DIRECTORY_VIEW_TOOL` | 1 | |
| | | `source/game/player.cc` |
| `#define DO_3RD_CHECK` | 1 | |
| | | `source/physics/physical.cc` |
| `#define DO_CD_IFF` | 1 | |
| | | `source/game/game.cc` |
| `#define DO_CD_STREAMING` | 1 | |
| | | `source/hal/diskfile.cc` |
| `#define DO_HDUMP` | 1 | |
| | | `source/hal/dfhd.cc` |
| `#define DO_OAD_IFF` | 1 | |
| | | `source/attrib/attrib.cc` |
| `#define DO_PROFILE` | 1 | |
| | | `source/game/main.cc` |
| `#define DYNAMICITEMS` | 1 | |
| | | `source/hal/item.h` |
| `#define EFFECT` | 1 | |
| | | `source/audiofmt/handlers.cc` |
| `#define EFF_CHAN` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define EFF_MCHAN` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define EFF_RATE` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define EFF_REPORT` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define EJ_BUTTONB_1` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_2` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_A` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_B` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_C` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_D` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_DOWN` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_E` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_F` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_G` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_H` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_I` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_J` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_K` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_L` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_LEFT` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_M` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_N` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_O` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_P` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_Q` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_R` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_RIGHT` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_S` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_T` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_U` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_UP` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_V` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_W` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_X` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_Y` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONB_Z` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_1` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_2` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_A` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_B` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_C` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_D` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_DOWN` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_E` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_F` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_G` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_H` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_I` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_J` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_K` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_L` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_LEFT` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_M` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_N` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_NONE` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_O` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_P` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_Q` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_R` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_RIGHT` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_S` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_T` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_U` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_UP` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_V` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_W` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_X` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_Y` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define EJ_BUTTONF_Z` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define END` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define END_EXTERN_C` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define EOL` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define EPSILON` | 1 | |
| | | `source/math/matrix34.cc` |
| `#define ERRAVAIL` | 1 | |
| | | `source/regexp/regerror.cc` |
| `#define ERROR` | 1 | |
| | | `source/game/actor.cc` |
| `#define ERR_HAL_ERROR` | 1 | |
| | | `source/hal/hal.h` |
| `#define ERR_HAL_LOGMASK` | 1 | |
| | | `source/hal/hal.h` |
| `#define ERR_HAL_PROGRESS` | 1 | |
| | | `source/hal/hal.h` |
| `#define ERR_HAL_WARNING` | 1 | |
| | | `source/hal/hal.h` |
| `#define EXACTLY` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define EXPORTER_EXCEPTION_DEFINED` | 1 | |
| | | `source/pigsys/assert.hp` |
| `#define EXPR_EXPR_H` | 1 | |
| | | `source/eval/expr.h` |
| `#define FADE_THRESH` | 1 | |
| | | `source/audiofmt/echo.cc` |
| `#define FAIL` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define FALSE` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define FHCLOSE` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHEOF` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHINIT` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHINITOK` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHOPENRD` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHOPENRDWR` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHOPENWR` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHREAD` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHSEEKABS` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHSEEKEND` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHSEEKREL` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHTELL` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FHWRITE` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define FILENAME_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define FILE_INSTR` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define FILE_LOOPS` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define FILE_STEREO` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define FIXED16` | 1 | |
| | | `source/oas/oad.h` |
| `#define FIXED32` | 1 | |
| | | `source/oas/oad.h` |
| `#define FIXED_H` | 1 | |
| | | `source/attrib/buttons/fixed.hp` |
| `#define FLOAT_TYPE` | 1 | |
| | | `source/math/scalar.hp` |
| `#define FONT_HP` | 1 | |
| | | `source/menu/font.hp` |
| `#define FOPEN_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define FORMAT` | 1 | |
| | | `source/audiofmt/handlers.cc` |
| `#define FREESPEED` | 1 | |
| | | `source/game/player.cc` |
| `#define GAMEFILE_LEVELSTART` | 1 | |
| | | `source/game/game.cc` |
| `#define GAMEFILE_SCRIPT` | 1 | |
| | | `source/game/game.cc` |
| `#define GFXFMT_BMP_HP` | 1 | |
| | | `source/gfxfmt/bmp.hp` |
| `#define GFXFMT_SGI_HP` | 1 | |
| | | `source/gfxfmt/sgi.hp` |
| `#define GFXFMT_TGA_HP` | 1 | |
| | | `source/gfxfmt/tga.hp` |
| `#define GFX_TGA_HP` | 1 | |
| | | `source/gfx/tga.hp` |
| `#define GFX_WFPRIM_H` | 1 | |
| | | `source/gfx/gl/wfprim.h` |
| `#define GNUALIGN` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define GRENADE_GUARD_HACK` | 1 | |
| | | `source/game/enemy.hp` |
| `#define GROUND_DIR_D` | 1 | |
| | | `source/movement/movement.cc` |
| `#define GROUND_DIR_L` | 1 | |
| | | `source/movement/movement.cc` |
| `#define GROUND_DIR_R` | 1 | |
| | | `source/movement/movement.cc` |
| `#define GROUND_DIR_U` | 1 | |
| | | `source/movement/movement.cc` |
| `#define HALCONV_H` | 1 | |
| | | `source/hal/halconv.h` |
| `#define HALFABIT` | 1 | |
| | | `source/audiofmt/mask.cc` |
| `#define HALMEM` | 1 | |
| | | `source/hal/linux/platform.cc` |
| `#define HAL_DISKFILE_HP` | 1 | |
| | | `source/hal/diskfile.hp` |
| `#define HAL_DMALLOC_SIZE` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HAL_INTERRUPTS` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HAL_MAX_MESSAGES` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HAL_MAX_PORTS` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HAL_MAX_TASKS` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HAL_MAX_TIMER_SUBSCRIBERS` | 1 | |
| | | `source/hal/halbase.h` |
| `#define HASWIDTH` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define HEADERSIZE` | 1 | |
| | | `source/audiofmt/smp.cc` |
| `#define HELP_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/help.hp` |
| `#define HUGE_VAL` | 1 | |
| | | `source/audiofmt/aiff.cc` |
| `#define IBM_FORMAT_ADPCM` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define IBM_FORMAT_ALAW` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define IBM_FORMAT_MULAW` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define IBUFFSIZE` | 1 | |
| | | `source/audiofmt/resample.cc` |
| `#define IDC_BOX` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_COPYRIGHT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_EDIT1` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_ICON` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_POSITION` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_SCROLLBAR2` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_SCROLLBAR3` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_STATIC` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_VERSION` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDC_ZOOM` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDD_ABOUT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDD_UDM` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDI_ICON1` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDI_ICON2` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDI_WORLDFOUNDRY` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_ABOUT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_COMBOBOX` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_CYCLEBUTTON` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_ENABLE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_EXIT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_PROPERTIES` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_RMENU` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_RMENU_INT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDM_SLIDER` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IDR_MENU1` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILE_CLOSE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILE_EXIT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILE_OPEN` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILE_SAVE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILE_SAVEAS` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_FILTER_OPEN` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_HELP_ABOUT` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_HELP_DOCUMENTATIONHOMEPAGE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define ID_PREFERENCES_EXPANDEDDISPLAY` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define IFFTAG` | 1 | |
| | | `source/iff/iffread.hp` |
| `#define IFFWRITE_BACKPATCH_HP` | 1 | |
| | | `source/iffwrite/backpatch.hp` |
| `#define IFFWRITE_FIXED_HP` | 1 | |
| | | `source/iffwrite/fixed.hp` |
| `#define IFFWRITE_H` | 1 | |
| | | `source/iffwrite/iffwrite.hp` |
| `#define IFFWRITE_ID_HP` | 1 | |
| | | `source/iffwrite/id.hp` |
| `#define IFFWRITE_PRINTF_HP` | 1 | |
| | | `source/iffwrite/printf.hp` |
| `#define IFF_LEFT_SHIFT_OPERATOR` | 1 | |
| | | `source/iffwrite/iffwrite.hp` |
| `#define IFF_WRITER_OUTPUT` | 1 | |
| | | `source/iffwrite/iffwrite.hp` |
| `#define INI_PROFILE_HP` | 1 | |
| | | `source/ini/profile.hp` |
| `#define INLINE` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT16_MIN` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT32_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT32_MIN` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT8_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT8_MIN` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define INT_H` | 1 | |
| | | `source/attrib/buttons/int.hp` |
| `#define INVALID_POS` | 1 | |
| | | `source/recolib/fpath.cc` |
| `#define IOSTREAM` | 1 | |
| | | `source/recolib/boolean.hp` |
| `#define IOSTREAMS` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define IRCAM` | 1 | |
| | | `source/audiofmt/sf.cc` |
| `#define ISMULT` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define ITEMCREATE` | 1 | |
| | | `source/hal/item.h` |
| `#define ITEMDESTROY` | 1 | |
| | | `source/hal/item.h` |
| `#define ITEMLOOKUP` | 1 | |
| | | `source/hal/item.h` |
| `#define ITEMRETRIEVE` | 1 | |
| | | `source/hal/item.h` |
| `#define ITEMTYPECREATE` | 1 | |
| | | `source/hal/item.h` |
| `#define ITEM_PRINT` | 1 | |
| | | `source/hal/halbase.h` |
| `#define LAST_BUTTON_WIDTH` | 1 | |
| | | `source/attrib/oaddlg.hp` |
| `#define LATER` | 1 | |
| | | `source/audiofmt/sf.cc` |
| `#define LEFT` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define LEVELCONFLAG_COMMONBLOCK` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_ENDCOMMON` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_EXTRACTCAMERA` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_EXTRACTCAMERANEW` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_EXTRACTLIGHT` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_NOINSTANCES` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_NOMESH` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_ROOM` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_SHORTCUT` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_SINGLEINSTANCE` | 1 | |
| | | `source/oas/oad.h` |
| `#define LEVELCONFLAG_TEMPLATE` | 1 | |
| | | `source/oas/oad.h` |
| `#define LINCLIP` | 1 | |
| | | `source/audiofmt/libst.h` |
| `#define LMALLOC_DEFINE_NEW` | 1 | |
| | | `source/memory/memory.hpi` |
| `#define LMALLOC_TRACK_LINE_AND_FILE` | 1 | |
| | | `source/memory/lmalloc.cc` |
| `#define LMALLOC_TRACK_SIZE` | 1 | |
| | | `source/memory/lmalloc.cc` |
| `#define LOADFILE_LOADFILE_HP` | 1 | |
| | | `source/loadfile/loadfile.hp` |
| `#define LOGFLAG` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define LOOP_8` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define LOOP_NONE` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define LOOP_SUSTAIN_DECAY` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define MAC` | 1 | |
| | | `source/audiofmt/handlers.cc` |
| `#define MAGIC` | 1 | |
| | | `source/regexp/regmagic.hp` |
| `#define MAILBOX_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/mailbox.hp` |
| `#define MATH_DEBUG` | 1 | |
| | | `source/math/scalar.hp` |
| `#define MATH_PLANE_HP` | 1 | |
| | | `source/math/plane.hp` |
| `#define MATRIX34_HPI` | 1 | |
| | | `source/math/matrix34.hpi` |
| `#define MATRIX3T_HPI` | 1 | |
| | | `source/math/matrix3t.hpi` |
| `#define MAUDHEADERSIZE` | 1 | |
| | | `source/audiofmt/maud.cc` |
| `#define MAXDELAYS` | 1 | |
| | | `source/audiofmt/echo.cc` |
| `#define MAXEFF` | 1 | |
| | | `source/audiofmt/sox.cc` |
| `#define MAXFACTOR` | 1 | |
| | | `source/audiofmt/resampl.h` |
| `#define MAXITEMS` | 1 | |
| | | `source/hal/item.h` |
| `#define MAXLIN` | 1 | |
| | | `source/audiofmt/libst.h` |
| `#define MAXNWING` | 1 | |
| | | `source/audiofmt/resampl.h` |
| `#define MAXRATE` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define MAX_ADJACENT_ROOMS` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define MAX_ANGLE_DEVIATION` | 1 | |
| | | `source/math/mathtest.cc` |
| `#define MAX_ATAN_DEVIATION` | 1 | |
| | | `source/math/mathtest.cc` |
| `#define MAX_COLLISION_EVENTS` | 1 | |
| | | `source/physics/collision.hp` |
| `#define MAX_DEVIATION` | 1 | |
| | | `source/math/mathtest.cc` |
| `#define MAX_EULER_DEVIATION` | 1 | |
| | | `source/math/mathtest.cc` |
| `#define MAX_GUARDS` | 1 | |
| | | `source/game/toolngun.hp` |
| `#define MEMCHECK` | 1 | |
| | | `source/pigsys/psystest.cc` |
| `#define MEMORY_DEFINE_NEW` | 1 | |
| | | `source/memory/memory.hpi` |
| `#define MEMORY_DELETE` | 1 | |
| | | `source/memory/memory.hp` |
| `#define MEMORY_DELETE_ARRAY` | 1 | |
| | | `source/memory/memory.hp` |
| `#define MEMORY_DELETE_PTR` | 1 | |
| | | `source/memory/memory.hp` |
| `#define MEMORY_IS_REGISTERED` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define MEMORY_NAMED` | 1 | |
| | | `source/memory/memory.hp` |
| `#define MEMORY_REGISTER` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define MEMORY_TRACK_FILE_LINE` | 1 | |
| | | `source/memory/memory.hp` |
| `#define MEMORY_UNREGISTER` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define MESHNAME_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/meshname.hp` |
| `#define META` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define MINLIN` | 1 | |
| | | `source/audiofmt/libst.h` |
| `#define MINMAX_HP` | 1 | |
| | | `source/pigsys/minmax.hp` |
| `#define MIX_CENTER` | 1 | |
| | | `source/audiofmt/avg.cc` |
| `#define MIX_LEFT` | 1 | |
| | | `source/audiofmt/avg.cc` |
| `#define MIX_RIGHT` | 1 | |
| | | `source/audiofmt/avg.cc` |
| `#define MOVEFOLL_HPI` | 1 | |
| | | `source/movement/movefoll.hpi` |
| `#define MSVC` | 1 | |
| | | `source/physics/physicstest.cc` |
| `#define MYBUFSIZ` | 1 | |
| | | `source/audiofmt/echo.cc` |
| `#define M_PI` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define NAMELEN` | 1 | |
| | | `source/audiofmt/smp.cc` |
| `#define NEED_STRERROR` | 1 | |
| | | `source/audiofmt/misc.cc` |
| `#define NEXT` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define NLOOPS` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define NODEINLIST` | 1 | |
| | | `source/hal/_list.h` |
| `#define NOMEMCHECK` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define NORMIT` | 1 | |
| | | `source/audiofmt/dyn.cc` |
| `#define NOTHING` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define NO_CD` | 1 | |
| | | `source/hal/halbase.h` |
| `#define NO_CONSOLE` | 1 | |
| | | `source/pigsys/assert.hp` |
| `#define NO_CPP` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define NSEGS` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define NSUBEXP` | 1 | |
| | | `source/regexp/regexp.hp` |
| `#define NSYMS` | 1 | |
| | | `source/eval/expr.h` |
| `#define NULL` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define NULLITEM` | 1 | |
| | | `source/hal/item.h` |
| `#define OADDLG_H` | 1 | |
| | | `source/attrib/oaddlg.hp` |
| `#define OAD_H` | 1 | |
| | | `source/oas/oad.h` |
| `#define OAS_MOVEMENT_H` | 1 | |
| | | `source/oas/movement.h` |
| `#define OBJECT_NULL` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define OBJREF_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/objref.hp` |
| `#define OBUFFSIZE` | 1 | |
| | | `source/audiofmt/resample.cc` |
| `#define OFFSET_AMOUNT` | 1 | |
| | | `source/movement/movement.cc` |
| `#define ONE12BIT` | 1 | |
| | | `source/math/matrix3t.hpi` |
| `#define OP` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define OPEN` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define OPERAND` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define OTABLE_FUDGE` | 1 | |
| | | `source/gfx/otable.cc` |
| `#define P1` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define P2` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define P3` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define P4` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define PAD_POW2` | 1 | |
| | | `source/cpplib/align.hp` |
| `#define PARTICLE_EMITTER_HP` | 1 | |
| | | `source/particle/emitter.hp` |
| `#define PARTICLE_PARTICLE_HP` | 1 | |
| | | `source/particle/particle.hp` |
| `#define PATCHLEVEL` | 1 | |
| | | `source/audiofmt/patchlvl.h` |
| `#define PATH_NULL` | 1 | |
| | | `source/oas/levelcon.h` |
| `#define PCLIB_BOOLEAN_H` | 1 | |
| | | `source/recolib/boolean.hp` |
| `#define PCLIB_STRMNULL_HP` | 1 | |
| | | `source/cpplib/strmnull.hp` |
| `#define PHYSICS_TELEMETRY` | 1 | |
| | | `source/movement/movement.cc` |
| `#define PI2` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define PIGSYS_PIGTYPES_H` | 1 | |
| | | `source/pigsys/pigtypes.h` |
| `#define PIGS_USE_MEMCHECK` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define PLUS` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define PORTNAMELEN` | 1 | |
| | | `source/hal/message.h` |
| `#define PRECISION_LIMIT` | 1 | |
| | | `source/math/matrix34.cc` |
| `#define PREMOVEMENT_CHECK` | 1 | |
| | | `source/movement/movement.cc` |
| `#define PRIVSIZE` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define PROC_STACKSIZE` | 1 | |
| | | `source/hal/linux/_procsta.h` |
| `#define PSION_HDRSIZE` | 1 | |
| | | `source/audiofmt/wve.cc` |
| `#define PSION_MAGIC` | 1 | |
| | | `source/audiofmt/wve.cc` |
| `#define PSION_VERSION` | 1 | |
| | | `source/audiofmt/wve.cc` |
| `#define PSXMEM` | 1 | |
| | | `source/hal/linux/platform.cc` |
| `#define PSYS_VERSION` | 1 | |
| | | `source/pigsys/psysvers.h` |
| `#define PSYS_VERSION_BODY` | 1 | |
| | | `source/pigsys/psysvers.h` |
| `#define PSYS_VERSION_HEAD` | 1 | |
| | | `source/pigsys/psysvers.h` |
| `#define PS_SCALAR_CONSTANT` | 1 | |
| | | `source/math/vector3p.hp` |
| `#define PS_SCALAR_CONSTANT12` | 1 | |
| | | `source/math/vector3p.hp` |
| `#define QNX` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define QUANT_MASK` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define QUAT_HPI` | 1 | |
| | | `source/math/quat.hpi` |
| `#define QUIETFLAG` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define R2D` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define RADIOBUTTONNAMELEN` | 1 | |
| | | `source/oas/oad.h` |
| `#define RANGE_HP` | 1 | |
| | | `source/cpplib/range.hp` |
| `#define READ` | 1 | |
| | | `source/savegame/savetest.cc` |
| `#define READBINARY` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define READING` | 1 | |
| | | `source/audiofmt/reverse.cc` |
| `#define READ_OPEN` | 1 | |
| | | `source/audiofmt/sound2su.cc` |
| `#define REALMALLOC_TRACK_LINE_AND_FILE` | 1 | |
| | | `source/memory/realmalloc.cc` |
| `#define REALMALLOC_TRACK_SIZE` | 1 | |
| | | `source/memory/realmalloc.cc` |
| `#define RIGHT` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define RMUV_HP` | 1 | |
| | | `source/gfx/rmuv.hp` |
| `#define SAVEGAME_HP` | 1 | |
| | | `source/savegame/savegame.hp` |
| `#define SAVEGAME_HPI` | 1 | |
| | | `source/savegame/savegame.hpi` |
| `#define SBLAST` | 1 | |
| | | `source/audiofmt/sbdsp.cc` |
| `#define SCALAR_CONSTANT` | 1 | |
| | | `source/math/scalar.hp` |
| `#define SCALAR_ONE_LS` | 1 | |
| | | `source/math/scalar.hp` |
| `#define SCORE_HP` | 1 | |
| | | `source/shell/score.hp` |
| `#define SCRATCHMEM` | 1 | |
| | | `source/hal/linux/platform.cc` |
| `#define SCRIPTINTERPRETER_HP` | 1 | |
| | | `source/scripting/scriptinterpreter.hp` |
| `#define SCRIPTINTERPRETER_PERL_HP` | 1 | |
| | | `source/scripting/perl/scriptinterpreter_perl.hp` |
| `#define SECTORSIZE` | 1 | |
| | | `source/audiofmt/cdr.cc` |
| `#define SEEK_CUR` | 1 | |
| | | `source/audiofmt/aiff.cc` |
| `#define SEEK_SET` | 1 | |
| | | `source/audiofmt/aiff.cc` |
| `#define SEG_MASK` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define SEG_SHIFT` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define SF_ALAW` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_AUDIOENCOD` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_CHAR` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_CODMAX` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_LINK` | 1 | |
| | | `source/audiofmt/sfheader.h` |
| `#define SF_LINKCODE` | 1 | |
| | | `source/audiofmt/sfheader.h` |
| `#define SF_MACHINE` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_MAGIC1` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_MAGIC2` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_MIPS` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_NEXT` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_PVDATA` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_SUN` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_ULAW` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SF_VAX` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SGN` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define SHOW_AS_CHECKBOX` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_COLOR` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_COMBOBOX` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_DROPMENU` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_FILENAME` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_HIDDEN` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_MAILBOX` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_NUMBER` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_N_A` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_RADIOBUTTONS` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_SLIDER` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_TEXTEDITOR` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_TOGGLE` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_AS_VECTOR` | 1 | |
| | | `source/oas/oad.h` |
| `#define SHOW_COLLISION_AS_BOXES` | 1 | |
| | | `source/game/actor.cc` |
| `#define SIGN2` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define SIGNAL_INVALID` | 1 | |
| | | `source/hal/_signal.h` |
| `#define SIGN_BIT` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define SIMPLE` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define SIMPMENU_HP` | 1 | |
| | | `source/menu/menu.hp` |
| `#define SIXTEEN_BIT_VRAM` | 1 | |
| | | `source/gfx/pixelmap.hp` |
| `#define SIZEOF_HEADER` | 1 | |
| | | `source/audiofmt/sfircam.h` |
| `#define SLIDING_FUDGE` | 1 | |
| | | `source/anim/animmang.cc` |
| `#define SOUND` | 1 | |
| | | `source/game/actor.cc` |
| `#define SPSTART` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define STACK_CALL_MAX_DEPTH` | 1 | |
| | | `source/pigsys/stack.cc` |
| `#define STAR` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define START_EXTERN_C` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define STATIC` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define STRICT` | 1 | |
| | | `source/cdda/win/cd.cc` |
| `#define STRINGMAXLEN` | 1 | |
| | | `source/hal/halbase.h` |
| `#define SUN` | 1 | |
| | | `source/audiofmt/aiff.cc` |
| `#define SUN_G721` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_G723_3` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_G723_5` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_HDRSIZE` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_INV_MAGIC` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_LIN_16` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_LIN_24` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_LIN_32` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_LIN_8` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_MAGIC` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_ULAW` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUN_UNSPEC` | 1 | |
| | | `source/audiofmt/au.cc` |
| `#define SUPERCEDED` | 1 | |
| | | `source/audiofmt/g711.cc` |
| `#define SVXHEADERSIZE` | 1 | |
| | | `source/audiofmt/8svx.cc` |
| `#define SWORD_DAMAGE` | 1 | |
| | | `source/anim/animmang.cc` |
| `#define SW_MEMORY_NAMED` | 1 | |
| | | `source/memory/memory.hp` |
| `#define SYMBOL_HP` | 1 | |
| | | `source/template/symbol.hp` |
| `#define SYS_FILENAME_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define SYS_FOPEN_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define SYS_MAC_ATEXIT_FUNCS` | 1 | |
| | | `source/pigsys/_atexit.h` |
| `#define SYS_SUPPRESS_BASE_TYPEDEFS` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define SYS_SUPPRESS_BSD_TYPEDEFS` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define SYS_TICKS` | 1 | |
| | | `source/hal/time.hp` |
| `#define TARG_UNIMPLEMENTED` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define TASKNAMELEN` | 1 | |
| | | `source/hal/_tasker.h` |
| `#define TEMPLATE_TEMPLATE_HP` | 1 | |
| | | `source/template/template.hp` |
| `#define TEST_DISKFILE` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_EMITTER` | 1 | |
| | | `source/particle/test.cc` |
| `#define TEST_GENERAL` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_ITEM` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_LIST` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_MEMPOOL` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_MESSAGE` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_SIG` | 1 | |
| | | `source/hal/tasker.cc` |
| `#define TEST_TASKER` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEST_TIMER` | 1 | |
| | | `source/hal/halbase.h` |
| `#define TEXTURE_FORMAT` | 1 | |
| | | `source/gfx/pixelmap.cc` |
| `#define TEXTURE_INTERNAL_FORMAT` | 1 | |
| | | `source/gfx/pixelmap.cc` |
| `#define TEXTURE_PAGE_XSIZE` | 1 | |
| | | `source/gfx/material.cc` |
| `#define TEXTURE_PAGE_XSTART_BOUNDRY` | 1 | |
| | | `source/gfx/material.cc` |
| `#define TEXTURE_PAGE_YSIZE` | 1 | |
| | | `source/gfx/material.cc` |
| `#define TEXTURE_PAGE_YSTART_BOUNDRY` | 1 | |
| | | `source/gfx/material.cc` |
| `#define TEXTURE_XPOS` | 1 | |
| | | `source/anim/preview.cc` |
| `#define TEXTURE_YPOS` | 1 | |
| | | `source/anim/preview.cc` |
| `#define TIMER_CLOCK_HP` | 1 | |
| | | `source/timer/clock.hp` |
| `#define TIMER_PRI` | 1 | |
| | | `source/hal/timer.cc` |
| `#define TIMER_SYSCLOCK` | 1 | |
| | | `source/hal/timer.h` |
| `#define TIMER_VBLANK` | 1 | |
| | | `source/hal/timer.h` |
| `#define TOOLNGUN_HP` | 1 | |
| | | `source/game/toolngun.hp` |
| `#define TOOLSHLD_HP` | 1 | |
| | | `source/game/toolshld.hp` |
| `#define TRIFACEONDISK` | 1 | |
| | | `source/gfx/face.hp` |
| `#define TRUE` | 1 | |
| | | `source/audiofmt/resdefs.h` |
| `#define UINT16_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define UINT32_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define UINT8_MAX` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define ULAW` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define UNNEEDED` | 1 | |
| | | `source/audiofmt/raw.cc` |
| `#define UNSIGNED` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define USE_ASSET_ID` | 1 | |
| | | `source/renderassets/rendcrow.cc` |
| `#define USE_INLINE_DEFS` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define USE_OLD_IOSTREAMS` | 1 | |
| | | `source/recolib/ktstoken.cc` |
| `#define USE_TEST_CAMERA` | 1 | |
| | | `source/game/level.cc` |
| `#define USG` | 1 | |
| | | `source/audiofmt/libst.h` |
| `#define UTIL_H` | 1 | |
| | | `source/attrib/util.hp` |
| `#define VALIDATEITEM` | 1 | |
| | | `source/hal/item.h` |
| `#define VALIDATEJOYSTICK` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define VALIDATEJOYSTICKPTR` | 1 | |
| | | `source/hal/sjoystic.h` |
| `#define VALIDATELIST` | 1 | |
| | | `source/hal/_list.h` |
| `#define VALIDATEMEMPOOL` | 1 | |
| | | `source/hal/_mempool.h` |
| `#define VALIDATEMESSAGE` | 1 | |
| | | `source/hal/message.cc` |
| `#define VALIDATEMESSAGEPORT` | 1 | |
| | | `source/hal/_message.h` |
| `#define VALIDATEMESSAGEPORTLIST` | 1 | |
| | | `source/hal/_message.h` |
| `#define VALIDATEMESSAGEPORTLISTPTR` | 1 | |
| | | `source/hal/_message.h` |
| `#define VALIDATEMESSAGEPORTPTR` | 1 | |
| | | `source/hal/_message.h` |
| `#define VALIDATENODE` | 1 | |
| | | `source/hal/_list.h` |
| `#define VALIDATENODEINLIST` | 1 | |
| | | `source/hal/_list.h` |
| `#define VALIDATENODENOTINLIST` | 1 | |
| | | `source/hal/_list.h` |
| `#define VALIDATEPROCSTATE` | 1 | |
| | | `source/hal/linux/_procsta.h` |
| `#define VALIDATEPTR` | 1 | |
| | | `source/hal/halbase.h` |
| `#define VALIDATESIGNAL` | 1 | |
| | | `source/hal/_signal.h` |
| `#define VALIDATESTRING` | 1 | |
| | | `source/hal/halbase.h` |
| `#define VALIDATETASK` | 1 | |
| | | `source/hal/tasker.h` |
| `#define VALIDATETASKPTR` | 1 | |
| | | `source/hal/tasker.h` |
| `#define VAXC` | 1 | |
| | | `source/audiofmt/sound2su.cc` |
| `#define VERSION` | 1 | |
| | | `source/audiofmt/version.h` |
| `#define VERSIONFLAG` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define VFW_H` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define VOC_CONT` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_DATA` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_DATA_16` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_LOOP` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_LOOPEND` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_MARKER` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_SILENCE` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_TERM` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define VOC_TEXT` | 1 | |
| | | `source/audiofmt/voc.cc` |
| `#define WARP_HP` | 1 | |
| | | `source/game/warp.hp` |
| `#define WAVE_FORMAT_ADPCM` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_ALAW` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_DIGIFIX` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_DIGISTD` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_MULAW` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_OKI_ADPCM` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_PCM` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WAVE_FORMAT_UNKNOWN` | 1 | |
| | | `source/audiofmt/wav.h` |
| `#define WORST` | 1 | |
| | | `source/regexp/regexp.cc` |
| `#define WRITEBINARY` | 1 | |
| | | `source/audiofmt/st.h` |
| `#define WRITING` | 1 | |
| | | `source/audiofmt/reverse.cc` |
| `#define WR_OPEN` | 1 | |
| | | `source/audiofmt/sound2su.cc` |
| `#define XDATA_CONTEXTUALANIMATIONLIST` | 1 | |
| | | `source/oas/oad.h` |
| `#define XDATA_CONVERSION_MAX` | 1 | |
| | | `source/oas/oad.h` |
| `#define XDATA_COPY` | 1 | |
| | | `source/oas/oad.h` |
| `#define XDATA_H` | 1 | |
| | | `source/attrib/buttons/notupg~1/xdata.hp` |
| `#define XDATA_IGNORE` | 1 | |
| | | `source/oas/oad.h` |
| `#define XDATA_OBJECTLIST` | 1 | |
| | | `source/oas/oad.h` |
| `#define XDATA_SCRIPT` | 1 | |
| | | `source/oas/oad.h` |
| `#define XSLEW` | 1 | |
| | | `source/game/movecam.cc` |
| `#define YSLEW` | 1 | |
| | | `source/game/movecam.cc` |
| `#define YY_USES_REJECT` | 1 | |
| | | `source/eval/flexle~1.h` |
| `#define ZEROTRAP` | 1 | |
| | | `source/audiofmt/libst.cc` |
| `#define ZSLEW` | 1 | |
| | | `source/game/movecam.cc` |
| `#define _ACTBOXOR_CC` | 1 | |
| | | `source/game/actboxor.cc` |
| `#define _ACTBOX_CC` | 1 | |
| | | `source/game/actbox.cc` |
| `#define _ACTIVEROOMS_HPI` | 1 | |
| | | `source/room/actrooms.hpi` |
| `#define _ACTOR_HP` | 1 | |
| | | `source/game/actor.hp` |
| `#define _ACTROOMSITER_HP` | 1 | |
| | | `source/room/actroit.hp` |
| `#define _ACTROOMS_HP` | 1 | |
| | | `source/room/actrooms.hp` |
| `#define _AFFTFORM_CC` | 1 | |
| | | `source/cpplib/afftform.cc` |
| `#define _ALGO_HP` | 1 | |
| | | `source/cpplib/algo.hp` |
| `#define _ALIGN_HP` | 1 | |
| | | `source/cpplib/align.hp` |
| `#define _ANGLE_CC` | 1 | |
| | | `source/math/angle.cc` |
| `#define _ANGLE_HP` | 1 | |
| | | `source/math/angle.hp` |
| `#define _ANIMATIONMANAGER_CC` | 1 | |
| | | `source/anim/animmang.cc` |
| `#define _ANIMATIONMANAGER_HP` | 1 | |
| | | `source/anim/animmang.hp` |
| `#define _APS_NEXT_COMMAND_VALUE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define _APS_NEXT_CONTROL_VALUE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define _APS_NEXT_RESOURCE_VALUE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define _APS_NEXT_SYMED_VALUE` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define _APS_NO_MFC` | 1 | |
| | | `source/attrib/udm/resource.h` |
| `#define _ARRAY_HP` | 1 | |
| | | `source/cpplib/array.hp` |
| `#define _ASSERT_DEFINED` | 1 | |
| | | `source/pigsys/assert.hp` |
| `#define _ASSERT_HP` | 1 | |
| | | `source/pigsys/assert.hp` |
| `#define _ASSETMANAGER_HP` | 1 | |
| | | `source/asset/assets.hp` |
| `#define _BINSTRM_CC` | 1 | |
| | | `source/streams/binstrm.cc` |
| `#define _BINSTRM_HP` | 1 | |
| | | `source/streams/binstrm.hp` |
| `#define _BOOL_IS_DEFINED_` | 1 | |
| | | `source/pigsys/cf_linux.h` |
| `#define _BRBMP_H` | 1 | |
| | | `source/game/wf_vfw.h` |
| `#define _CAMERA_CC` | 1 | |
| | | `source/game/camera.hp` |
| `#define _CF_LINUX_H` | 1 | |
| | | `source/pigsys/cf_linux.h` |
| `#define _CHANNEL_HP` | 1 | |
| | | `source/anim/channel.hp` |
| `#define _COLBOX_CC` | 1 | |
| | | `source/physics/colbox.cc` |
| `#define _COLBOX_HP` | 1 | |
| | | `source/physics/colbox.hp` |
| `#define _COLLISIO_HP` | 1 | |
| | | `source/physics/collision.hp` |
| `#define _COLSPACE_CC` | 1 | |
| | | `source/physics/colspace.cc` |
| `#define _COLSPACE_HP` | 1 | |
| | | `source/physics/colspace.hp` |
| `#define _COMMAND_HP` | 1 | |
| | | `source/recolib/command.hp` |
| `#define _CTYPE_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _DBSTRM_HP` | 1 | |
| | | `source/streams/dbstrm.hp` |
| `#define _DFOFF_CC` | 1 | |
| | | `source/hal/dfoff.cc` |
| `#define _DISKFILE_CC` | 1 | |
| | | `source/hal/diskfile.cc` |
| `#define _DISKTOC_HP` | 1 | |
| | | `source/iff/disktoc.hp` |
| `#define _EULER_HP` | 1 | |
| | | `source/math/euler.hp` |
| `#define _EXPLODE_CC` | 1 | |
| | | `source/game/explode.cc` |
| `#define _EXPLODE_HP` | 1 | |
| | | `source/game/explode.hp` |
| `#define _G72X_H` | 1 | |
| | | `source/audiofmt/g72x.h` |
| `#define _GAMECALLBACKS_HP` | 1 | |
| | | `source/game/callbacks.hp` |
| `#define _GAMEMAILBOX_HP` | 1 | |
| | | `source/game/mailbox.hp` |
| `#define _GAMESTRM_CC` | 1 | |
| | | `source/game/gamestrm.cc` |
| `#define _GAMESTRM_HP` | 1 | |
| | | `source/game/gamestrm.hp` |
| `#define _GAME_HP` | 1 | |
| | | `source/game/game.hp` |
| `#define _GENFH_HP` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define _GFXCALLBACKS_HP` | 1 | |
| | | `source/gfx/callbacks.hp` |
| `#define _HANDLE_HP` | 1 | |
| | | `source/gfx/handle.hp` |
| `#define _I16LIST_HP` | 1 | |
| | | `source/cpplib/int16li.hp` |
| `#define _INFILE_HP` | 1 | |
| | | `source/recolib/infile.hp` |
| `#define _INPUTDIGGAME_HP` | 1 | |
| | | `source/orphaned/inputdig.hp` |
| `#define _INPUTDIG_HP` | 1 | |
| | | `source/input/inputdig.hp` |
| `#define _INPUTMAP_HP` | 1 | |
| | | `source/movement/inputmap.hp` |
| `#define _ITERWRAPPER_HP` | 1 | |
| | | `source/cpplib/iterwrapper.hp` |
| `#define _LEVELROOMS_HPI` | 1 | |
| | | `source/room/rooms.hpi` |
| `#define _LEVEL_CC` | 1 | |
| | | `source/game/level.cc` |
| `#define _LEVEL_HP` | 1 | |
| | | `source/game/level.hp` |
| `#define _LIGHT_CC` | 1 | |
| | | `source/game/light.hp` |
| `#define _LIMITS_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _LMALLOC_CC` | 1 | |
| | | `source/memory/lmalloc.cc` |
| `#define _LMALLOC_HP` | 1 | |
| | | `source/memory/lmalloc.hp` |
| `#define _MAILBOX_HP` | 1 | |
| | | `source/mailbox/mailbox.hp` |
| `#define _MAIN_CC` | 1 | |
| | | `source/game/main.cc` |
| `#define _MATRIX34_CC` | 1 | |
| | | `source/math/matrix34.cc` |
| `#define _MATRIX34_HP` | 1 | |
| | | `source/math/matrix34.hp` |
| `#define _MATRIX3T_CC` | 1 | |
| | | `source/math/matrix3t.cc` |
| `#define _MATRIX3T_HP` | 1 | |
| | | `source/math/matrix3t.hp` |
| `#define _MATTE_CC` | 1 | |
| | | `source/game/matte.cc` |
| `#define _MATTE_HP` | 1 | |
| | | `source/game/matte.hp` |
| `#define _MAX` | 1 | |
| | | `source/cpplib/utility.hp` |
| `#define _MAX_EXT` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define _MAX_FNAME` | 1 | |
| | | `source/pigsys/genfh.hp` |
| `#define _MAX_PATHNAME` | 1 | |
| | | `source/streams/asset.hp` |
| `#define _MEMORY_HP` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define _MESSAGE_H` | 1 | |
| | | `source/hal/message.h` |
| `#define _MIN` | 1 | |
| | | `source/cpplib/utility.hp` |
| `#define _MINLIST_HP` | 1 | |
| | | `source/cpplib/minlist.hp` |
| `#define _MISSILE_CC` | 1 | |
| | | `source/game/missile.cc` |
| `#define _MISSILE_HP` | 1 | |
| | | `source/game/missile.hp` |
| `#define _MKINC` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _MOVECAM_CC` | 1 | |
| | | `source/game/movecam.cc` |
| `#define _MOVECAM_HP` | 1 | |
| | | `source/game/movecam.hp` |
| `#define _MOVEFOLL_HP` | 1 | |
| | | `source/movement/movefoll.hp` |
| `#define _MOVEMENTMANAGER_HP` | 1 | |
| | | `source/movement/movementmanager.hp` |
| `#define _MOVEMENT_HP` | 1 | |
| | | `source/movement/movement.hp` |
| `#define _MOVEPATH_CC` | 1 | |
| | | `source/movement/movepath.cc` |
| `#define _MOVEPATH_HP` | 1 | |
| | | `source/movement/movepath.hp` |
| `#define _MSGPORT_HP` | 1 | |
| | | `source/baseobject/msgport.hp` |
| `#define _NEW_CC` | 1 | |
| | | `source/pigsys/new.cc` |
| `#define _ODE_CC` | 1 | |
| | | `source/physics/ode/ode.cc` |
| `#define _ODE_HP` | 1 | |
| | | `source/physics/ode/ode.hp` |
| `#define _PATH_CC` | 1 | |
| | | `source/anim/path.cc` |
| `#define _PATH_HP` | 1 | |
| | | `source/anim/path.hp` |
| `#define _PHYSICALOBJECT_CC` | 1 | |
| | | `source/physics/physicalobject.cc` |
| `#define _PHYSICALOBJECT_HP` | 1 | |
| | | `source/physics/physicalobject.hp` |
| `#define _PHYSICAL_CC` | 1 | |
| | | `source/physics/physical.cc` |
| `#define _PHYSICAL_HP` | 1 | |
| | | `source/physics/physical.hp` |
| `#define _PIGSYS_C` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define _PIGS_C` | 1 | |
| | | `source/hal/hal.cc` |
| `#define _PIGS_ENDIAN_H` | 1 | |
| | | `source/pigsys/endian.h` |
| `#define _PIGTOOL_H` | 1 | |
| | | `source/oas/pigtool.h` |
| `#define _PLATFORM_C` | 1 | |
| | | `source/hal/linux/platform.cc` |
| `#define _PLAYER_CC` | 1 | |
| | | `source/game/player.cc` |
| `#define _POINTERCONTANER_HP` | 1 | |
| | | `source/cpplib/pointercontainer.hp` |
| `#define _PSYSTEST_C` | 1 | |
| | | `source/pigsys/psystest.cc` |
| `#define _PSYSVERS_H` | 1 | |
| | | `source/pigsys/psysvers.h` |
| `#define _QUAT_CC` | 1 | |
| | | `source/math/quat.cc` |
| `#define _QUAT_HP` | 1 | |
| | | `source/math/quat.hp` |
| `#define _REALMALLOC_HP` | 1 | |
| | | `source/memory/realmalloc.hp` |
| `#define _RENDERACTOR_HP` | 1 | |
| | | `source/renderassets/rendacto.hp` |
| `#define _RENDMATT_HP` | 1 | |
| | | `source/gfx/rendmatt.hp` |
| `#define _ROOMS_HP` | 1 | |
| | | `source/room/rooms.hp` |
| `#define _ROOM_CC` | 1 | |
| | | `source/room/room.cc` |
| `#define _SAVEGAME_CC` | 1 | |
| | | `source/savegame/savegame.hp` |
| `#define _SCALAR_CC` | 1 | |
| | | `source/math/scalar.cc` |
| `#define _SCALAR_HP` | 1 | |
| | | `source/math/scalar.hp` |
| `#define _SCANF_C` | 1 | |
| | | `source/pigsys/scanf.cc` |
| `#define _SCANF_GETC` | 1 | |
| | | `source/pigsys/scanf.cc` |
| `#define _SCANF_UNGETC` | 1 | |
| | | `source/pigsys/scanf.cc` |
| `#define _SETJMP_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _STDARG_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _STDIO_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _STDLIB_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _STDSTRM_CC` | 1 | |
| | | `source/cpplib/stdstrm.cc` |
| `#define _STDSTRM_HP` | 1 | |
| | | `source/cpplib/stdstrm.hp` |
| `#define _STRING_H` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _SYS_ALIGNMENT` | 1 | |
| | | `source/pigsys/memory.hp` |
| `#define _SYS_CAST_2CHARP` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define _SYS_CAST_2INT` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define _SYS_NONEW_AGGREGATE` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _SYS_NO_STDOUT` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define _SYS_NO_UNBUFFERED_STDOUT` | 1 | |
| | | `source/pigsys/pigsys.cc` |
| `#define _SYS_VANILLA_NEW` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define _TCL_HP` | 1 | |
| | | `source/scripting/tcl.hp` |
| `#define _TOOLSHLD_CC` | 1 | |
| | | `source/game/toolshld.hp` |
| `#define _VECTOR2_CC` | 1 | |
| | | `source/math/vector2.cc` |
| `#define _VECTOR2_HP` | 1 | |
| | | `source/math/vector2.hp` |
| `#define _VECTOR2_HPI` | 1 | |
| | | `source/math/vector2.hpi` |
| `#define _VECTOR3_CC` | 1 | |
| | | `source/math/vector3.cc` |
| `#define _VECTOR3_HP` | 1 | |
| | | `source/math/vector3.hp` |
| `#define _VECTOR3_HPI` | 1 | |
| | | `source/math/vector3.hpi` |
| `#define _VERSION_HP` | 1 | |
| | | `source/game/version.hp` |
| `#define _WIN32` | 1 | |
| | | `source/audiofmt/sox.cc` |
| `#define __ATEXIT_C` | 1 | |
| | | `source/pigsys/_atexit.cc` |
| `#define __ATEXIT_H` | 1 | |
| | | `source/pigsys/_atexit.h` |
| `#define __ATT2_1` | 1 | |
| | | `source/pigsys/pigsys.hp` |
| `#define __BUNGEE_CAM__` | 1 | |
| | | `source/game/movecam.cc` |
| `#define __CF_LINUX_C` | 1 | |
| | | `source/pigsys/_cf_linux.cc` |
| `#define __FLEX_LEXER_H` | 1 | |
| | | `source/eval/flexle~1.h` |
| `#define __INPUT_H` | 1 | |
| | | `source/hal/_input.h` |
| `#define __MESSAGE_H` | 1 | |
| | | `source/hal/_message.h` |
| `#define __PIGS__` | 1 | |
| | | `source/pigsys/psysvers.h` |
| `#define __PLATFORM_H` | 1 | |
| | | `source/hal/linux/platform.h` |
| `#define __PROCSTATE_H` | 1 | |
| | | `source/hal/linux/_procsta.h` |
| `#define __PSX` | 1 | |
| | | `source/gfx/material.hpi` |
| `#define __SAT__` | 1 | |
| | | `source/pigsys/psystest.cc` |
| `#define __TIME_HP_` | 1 | |
| | | `source/hal/time.hp` |
| `#define __WATCOMC__` | 1 | |
| | | `source/cpplib/stdstrm.hp` |
| `#define __WIN` | 1 | |
| | | `source/game/main.cc` |
