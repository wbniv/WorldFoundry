"""Build a C zForth test host linked with the engine's math words (tests/forth_math_host.cpp).

The C hosts (tests/species_vm.c, docs/reference/swarming-poster/zf_host.c with -DWF_FORTH_MATH) call
wf_forth_math_register after zf_bootstrap and wf_forth_math_sys from their syscall handler, so a level
script that uses `floor` or `sqrt` runs on the shipped glue (engine/stubs/forth_math_zforth.hpp).
The C files compile as C and the shim as C++; c++ links them.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'


def build_c_host(host: Path, binary: Path, *flags: str) -> Path:
    """Compile `host` (a C file defining zf_host_sys) with zforth.c and the math shim into `binary`."""
    inc = ['-I' + str(ROOT / 'engine/stubs'), '-I' + str(VENDOR)]
    host_o, vm_o = binary.with_name(binary.name + '-host.o'), binary.with_name(binary.name + '-zforth.o')
    subprocess.run(['cc', '-O1', *flags, *inc, '-c', str(host), '-o', str(host_o)], check=True)
    subprocess.run(['cc', '-O1', *flags, *inc, '-c', str(VENDOR / 'zforth.c'), '-o', str(vm_o)], check=True)
    subprocess.run(['c++', '-std=c++17', '-O1', *flags, *inc, str(ROOT / 'tests/forth_math_host.cpp'),
                    str(host_o), str(vm_o), '-lm', '-o', str(binary)], check=True)
    return binary
