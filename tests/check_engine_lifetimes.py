"""Real engine allocator and repeated level teardown diagnostics (headless GL)."""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--level', required=True)
parser.add_argument('--sanitizers', action='store_true', help='Separate WF_ASAN=ON, WF_LIFETIME_DIAGNOSTICS=OFF binary')
parser.add_argument('engine_args', nargs=argparse.REMAINDER, help='Additional engine arguments after --')
args = parser.parse_args()
if args.engine_args[:1] == ['--']:
    args.engine_args = args.engine_args[1:]
root = Path(__file__).resolve().parents[1]
out = Path(args.out).resolve()
out.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', LSAN_OPTIONS='detect_leaks=1:exitcode=88',
           UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

def run(label, command, overrides=None):
    local = dict(env, **(overrides or {}))
    with (out / (label + '.log')).open('w') as log:
        result = subprocess.run(command, cwd=root / 'wfsource/source/game', env=local,
                                stdout=log, stderr=subprocess.STDOUT, timeout=120)
    text = (out / (label + '.log')).read_text(errors='replace')
    print(label, 'exit', result.returncode, flush=True)
    return result.returncode, text

binary = str(Path(args.binary).resolve())
if not args.sanitizers:
    code, text = run('pool-balanced', [binary, '--memory-test'])
    assert code == 0 and 'live=0 bytes=0 errors=0' in text, text[-8000:]
    for fault, evidence in [('allocation', 'kind=pool'), ('destructor', 'type=PoolFaultObject')]:
        code, text = run('pool-fault-' + fault, [binary, '--memory-test'], {'WF_LIFETIME_POOL_FAULT': fault})
        assert code == 86 and 'arena-survivor' in text and evidence in text, text[-8000:]
code, text = run('cycles-sanitizers' if args.sanitizers else 'cycles-lifetimes',
                 [binary, '-pps', '--frame-step-smoke=4', '--cycles=5', '-L' + str(Path(args.level).resolve()), *args.engine_args])
assert code == 0, text[-16000:]
assert text.count('Level::Level: leveldata=') == 5, text[-8000:]
for failure in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'arena-survivor', 'shutdown-survivor']:
    assert failure not in text, text[-16000:]
if not args.sanitizers:
    assert text.count('LIFETIME end owner=') == 5, text[-8000:]
    assert 'LIFETIME shutdown live=0 errors=0' in text, text[-8000:]
print('Engine lifecycle checks passed; logs:', out)
