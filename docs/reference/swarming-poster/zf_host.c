/* zf_host.c: a standalone zForth host for testing level scripts without the engine.
 *
 * It is the engine's own zForth (engine/vendor/zforth-41db72d1) built with the engine's own zfconf.h (float cells, 64 KB dictionary, 64-deep stacks),
 * plus the one thing level scripts need from the game: the mailboxes (read-mailbox / write-mailbox, syscalls 128 / 129). One global bank of floats.
 *
 * It reads commands on stdin, one per line (replies on stdout):
 *   E <forth text>     evaluate; prints "ok" or "err <name>"
 *   W <idx> <value>    write a mailbox
 *   R <idx> [<count>]  print <count> mailboxes (default 1), space separated
 *   F <path>           evaluate a file line by line (stops at the first error); prints "ok" or "err <name> line <n>"
 *   S                  print the dictionary size used (zf_uservar HERE) so a script's footprint can be read
 *   N                  print and reset the mailbox read and write counts (how many bridge calls a script makes)
 *   T <n> <forth>      evaluate <forth> n times and print the mean milliseconds per evaluation (for timing on a device, with no pipe in the way)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include "zforth.h"

#define NMAIL 8192
static float g_mail[NMAIL];
static long g_reads, g_writes;           /* mailbox calls, reported by N */

zf_input_state zf_host_sys(zf_ctx *ctx, zf_syscall_id id, const char *last_word)
{
    (void)last_word;
    switch ((int)id) {
    case 128: { g_reads++; int i = (int)zf_pop(ctx); zf_push(ctx, (zf_cell)((i >= 0 && i < NMAIL) ? g_mail[i] : 0.0f)); break; }
    case 129: { g_writes++; int i = (int)zf_pop(ctx); float v = (float)zf_pop(ctx); if (i >= 0 && i < NMAIL) g_mail[i] = v; break; }
    case ZF_SYSCALL_PRINT: { zf_cell v = zf_pop(ctx); printf(ZF_CELL_FMT " ", v); break; }
    case ZF_SYSCALL_EMIT: { putchar((char)zf_pop(ctx)); break; }
    default: break;
    }
    return ZF_INPUT_INTERPRET;
}

void zf_host_trace(zf_ctx *ctx, const char *fmt, va_list va) { (void)ctx; (void)fmt; (void)va; }

zf_cell zf_host_parse_num(zf_ctx *ctx, const char *buf)
{
    char *end = NULL;
    float v = strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;
    zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
    return 0;
}

static const char *err_name(zf_result r)
{
    switch (r) {
    case ZF_OK: return "ok";
    case ZF_ABORT_INTERNAL_ERROR: return "internal_error";
    case ZF_ABORT_OUTSIDE_MEM: return "outside_mem";
    case ZF_ABORT_DSTACK_UNDERRUN: return "dstack_underrun";
    case ZF_ABORT_DSTACK_OVERRUN: return "dstack_overrun";
    case ZF_ABORT_RSTACK_UNDERRUN: return "rstack_underrun";
    case ZF_ABORT_RSTACK_OVERRUN: return "rstack_overrun";
    case ZF_ABORT_NOT_A_WORD: return "not_a_word";
    case ZF_ABORT_COMPILE_ONLY_WORD: return "compile_only_word";
    case ZF_ABORT_INVALID_SIZE: return "invalid_size";
    case ZF_ABORT_DIVISION_BY_ZERO: return "division_by_zero";
    default: return "other";
    }
}

int main(int argc, char **argv)
{
    if (argc > 1 && (!strcmp(argv[1], "-h") || !strcmp(argv[1], "--help"))) {
        puts("usage: zf_host   (commands on stdin: E <forth> | W <idx> <val> | R <idx> [n] | F <file> | S)");
        return 0;
    }
    static zf_ctx ctx;
    zf_init(&ctx, 0);
    zf_bootstrap(&ctx);
    char line[1 << 16];
    while (fgets(line, sizeof line, stdin)) {
        size_t n = strlen(line);
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
        if (!n) continue;
        char *arg = line + 1;
        while (*arg == ' ') arg++;
        switch (line[0]) {
        case 'E': { zf_result r = zf_eval(&ctx, arg); printf("%s\n", err_name(r)); break; }
        case 'W': { int i = 0; float v = 0; if (sscanf(arg, "%d %f", &i, &v) == 2 && i >= 0 && i < NMAIL) g_mail[i] = v; break; }
        case 'R': { int i = 0, c = 1; sscanf(arg, "%d %d", &i, &c); for (int k = 0; k < c; k++) printf("%.9g%c", (i + k < NMAIL) ? g_mail[i + k] : 0.0f, k + 1 < c ? ' ' : '\n'); break; }
        case 'F': {
            FILE *f = fopen(arg, "rb"); char b[4096]; int ln = 0; zf_result r = ZF_OK;
            if (!f) { printf("err cannot_open\n"); break; }
            while (fgets(b, sizeof b, f)) { ln++; r = zf_eval(&ctx, b); if (r != ZF_OK) break; }
            fclose(f);
            if (r == ZF_OK) printf("ok\n"); else printf("err %s line %d\n", err_name(r), ln);
            break;
        }
        case 'S': { zf_cell h = 0; zf_uservar_get(&ctx, ZF_USERVAR_HERE, &h); printf("%d\n", (int)h); break; }
        case 'N': { printf("%ld reads %ld writes\n", g_reads, g_writes); g_reads = g_writes = 0; break; }
        case 'T': {
            int reps = atoi(arg); char *src = arg; while (*src && *src != ' ') src++;
            struct timespec a, b; clock_gettime(CLOCK_MONOTONIC, &a);
            zf_result r = ZF_OK;
            for (int k = 0; k < reps && r == ZF_OK; k++) r = zf_eval(&ctx, src);
            clock_gettime(CLOCK_MONOTONIC, &b);
            if (r != ZF_OK) printf("err %s\n", err_name(r));
            else printf("%.4f ms\n", ((b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6) / (reps ? reps : 1));
            break;
        }
        default: printf("err unknown_command\n");
        }
        fflush(stdout);
    }
    return 0;
}
