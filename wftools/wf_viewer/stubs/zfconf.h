/* zfconf.h — WF-specific zForth configuration.
 * Used instead of the vendor's src/linux/zfconf.h or src/atmega8/zfconf.h.
 * Placed in the stubs include directory so it shadows the vendor file when
 * -I<stubs_dir> is listed before -I<zforth_src_dir> in build_game.sh.
 */
#ifndef zfconf
#define zfconf

/* Tracing: off in WF builds — zf_host_trace never called. */
#define ZF_ENABLE_TRACE 0

/* Boundary checks: on — minimal .text cost, catches stack bugs during dev. */
#define ZF_ENABLE_BOUNDARY_CHECKS 1

/* Bootstrap: always on — WF builds the dictionary at runtime. */
#define ZF_ENABLE_BOOTSTRAP 1

/* Typed memory access: off — not needed for WF scripts. */
#define ZF_ENABLE_TYPED_MEM_ACCESS 0

/* Cell type: float — PC dev uses float mailboxes.
 * On the real fixed-point target, float mailbox values round-trip through
 * the fixed-point representation; results are exact for integer indices. */
typedef float zf_cell;
#define ZF_CELL_FMT  "%.14g"
#define ZF_SCAN_FMT  "%f"

typedef int zf_int;
typedef unsigned int zf_addr;
#define ZF_ADDR_FMT "%04x"

/* Dictionary: 16 KB — room for ~150 INDEXOF_xx / JOYSTICK_BUTTON_xx constants
 * (~4 KB) plus bootstrap words and user game scripts.
 * Stack sizes enlarged from the Linux default (8 each) to handle nesting. */
#define ZF_DICT_SIZE   16384
#define ZF_DSTACK_SIZE 64
#define ZF_RSTACK_SIZE 64

#endif /* zfconf */
