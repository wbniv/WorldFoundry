"""Run deliberately broken ownership lifecycles; failures must identify survivors."""
import subprocess
import sys

binary = sys.argv[1]
for mode in ['clean', 'persistent', 'context-loss', 'bulk-arena']:
    result = subprocess.run([binary, mode], capture_output=True, text=True)
    assert result.returncode == 0, (mode, result.stdout, result.stderr)
for mode, evidence in [
    ('missing-destructor', 'arena-survivor'),
    ('missing-free', 'arena-survivor'),
    ('missing-heap-delete', 'kind=heap'),
    ('missing-gl-delete', 'type=GL buffer'),
    ('persistent-leak', 'owner=1'),
    ('unscoped-object', 'type=TestObject'),
    ('duplicate', 'duplicate-acquire'),
    ('unknown-release', 'unknown-release'),
]:
    result = subprocess.run([binary, mode], capture_output=True, text=True)
    assert result.returncode == 86, (mode, result.returncode, result.stderr)
    assert evidence in result.stderr, (mode, result.stderr)
print('Lifetime diagnostics: balanced cycles pass; eight deliberate failures detected')
