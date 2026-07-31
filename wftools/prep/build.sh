#!/bin/bash
# Build prep for Linux.
# This replaces the Windows Watcom toolchain and the complex GNUMakefile.tool
# system (which requires pre-built wfsource libraries).
#
# prep is self-contained: its three support libraries (recolib, regexp, eval)
# live alongside it under wftools/prep/, so the only thing it pulls from the
# engine tree ($WF_SRC) is a handful of general headers (pigsys/, cpplib/,
# streams/). The eval parser/lexer are bison/flex generated — regenerate with:
#     ( cd eval && bison --defines=expr_tab.h -o expr_tab.cc expr.y && flex -o lexyy.cc expr.l )
#
# Bug fixed: unsigned delimiterIndex = token.find("=>") in macro.cc
# On 64-bit Linux, string::npos is 64-bit; truncating to unsigned caused
# the named-parameter branch to fire for every normal parameter token.
# Fixed by using std::string::size_type instead of unsigned.

set -euo pipefail
cd "$(dirname "$0")"
WF_SRC="$(cd ../../wfsource/source && pwd)"   # engine-general headers only (pigsys/, cpplib/, streams/)

g++ -std=c++14 \
    -I. -I"$WF_SRC" \
    -D__LINUX__ -DSW_DBSTREAM=0 \
    -O2 \
    -o prep \
    prep.cc macro.cc source.cc \
    recolib/command.cc \
    recolib/infile.cc \
    recolib/ktstoken.cc \
    eval/expr_tab.cc \
    eval/lexyy.cc \
    regexp/regexp.cc \
    regexp/regsub.cc \
    regexp/regerror.cc \
    2>&1 | { grep -v "warning:" || true; }   # grep exits 1 on a warning-free build; don't let that mask g++'s status

echo "prep built successfully"
