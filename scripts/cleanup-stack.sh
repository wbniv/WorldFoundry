#!/usr/bin/env bash
# cleanup-stack.sh — composable EXIT cleanup handlers.
#
# Bash has a single EXIT trap per shell, so libraries that set their own
# trap at source/call time (filelock.sh, asg-ssh-opts.sh setup_bastion,
# step-timer.sh run_init) silently clobber each other's cleanup. This file
# owns the EXIT trap exactly once and exposes push_cleanup() so every
# library and script can register additional handlers cooperatively.
#
# Usage:
#   source "$(dirname "$0")/cleanup-stack.sh"
#   push_cleanup 'rm -f /tmp/my-tempfile'
#   push_cleanup 'my_cleanup_function'
#   push_cleanup '_release_all_locks'
#
# Handlers run LIFO on EXIT so later registrations clean up before earlier
# ones — matching typical resource-acquisition-ordering expectations. Each
# handler is wrapped with `|| true` so a failing cleanup doesn't prevent
# the rest from running.
#
# This file must be idempotent: sourcing it twice (e.g. once by filelock.sh
# and again by asg-ssh-opts.sh) must NOT reinstall the trap or clear the
# stack. The _CLEANUP_STACK_INITIALIZED guard ensures that.
#
# Note: this is a sourced library and deliberately does NOT set
# `set -euo pipefail` at the top — that would leak into the caller's shell.

if [ -z "${_CLEANUP_STACK_INITIALIZED:-}" ]; then
    _CLEANUP_STACK=()
    _CLEANUP_STACK_INITIALIZED=1

    _run_all_cleanups() {
        local rc=$?
        local i handler
        # LIFO: later push_cleanup calls run first (like defer in Go).
        for (( i=${#_CLEANUP_STACK[@]}-1; i>=0; i-- )); do
            handler="${_CLEANUP_STACK[i]}"
            # eval so handler strings can include variable expansion and
            # multi-command bodies. Each handler is best-effort: a failing
            # cleanup shouldn't prevent the rest from running, and
            # shouldn't mask the script's actual exit code.
            eval "$handler" 2>/dev/null || true
        done
        # Preserve the original exit code so callers see the real failure,
        # not the exit code of the last cleanup command.
        return "$rc"
    }

    trap _run_all_cleanups EXIT
fi

# Register a cleanup handler. Handlers are run in reverse order of
# registration (LIFO) when the shell exits.
#
# Usage:
#   push_cleanup 'rm -f /tmp/foo'
#   push_cleanup my_cleanup_function
#   push_cleanup 'rm -f "$MY_TMPFILE"'  # note: single-quoted so $MY_TMPFILE
#                                       # is expanded at cleanup time, not
#                                       # registration time
push_cleanup() {
    _CLEANUP_STACK+=("$1")
}
