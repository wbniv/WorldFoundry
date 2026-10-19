# wf-minimal — WorldFoundry's "smallest JS that is still authorable" profile.
# Starts from stock `minimal` (everything off) and re-enables the builtins
# gameplay scripts cannot reasonably live without. ESNEXT stays off — if a
# game needs ES2015+, pick WF_JS_ENGINE=quickjs instead. Rationale lives in
# docs/plans/2026-04-14-pluggable-scripting-engine.md §4.

JERRY_BUILTINS=0
JERRY_UNICODE_CASE_CONVERSION=0

JERRY_BUILTIN_ARRAY=1
JERRY_BUILTIN_STRING=1
JERRY_BUILTIN_NUMBER=1
JERRY_BUILTIN_MATH=1
JERRY_BUILTIN_ERRORS=1
JERRY_BUILTIN_BOOLEAN=1
JERRY_BUILTIN_GLOBAL_THIS=1
