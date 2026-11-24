"""Prove ASan/LSan catch paths deliberately absent from the ownership registry."""
import os
import subprocess
import sys

env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0:exitcode=87',
           LSAN_OPTIONS='exitcode=88', UBSAN_OPTIONS='halt_on_error=1')
for mode, diagnostic in [('leak', 'LeakSanitizer: detected memory leaks'),
                         ('use-after-free', 'AddressSanitizer: heap-use-after-free')]:
    result = subprocess.run([sys.argv[1], mode], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and diagnostic in result.stderr, (mode, result.returncode, result.stderr)
print('Independent sanitizer fixtures: C malloc leak and use-after-free detected')
