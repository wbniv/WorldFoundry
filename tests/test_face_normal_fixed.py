"""Exercise fixed-point face normal math against exact integer products."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fixed_point_face_normals(tmp_path):
    binary = tmp_path / 'face-normal-fixed'
    flags = ['DEBUG=0', 'DEBUG_VARIABLES=0', 'DO_ASSERTIONS=0', 'DO_DEBUGGING_INFO=0',
             'DO_DEBUG_FILE_SYSTEM=0', 'DO_IOSTREAMS=0', 'DO_TEST_CODE=0',
             'DO_VALIDATION=0', 'SW_DBSTREAM=0', 'RENDERER_GL',
             'RENDERER_PIPELINE_GL', 'SCALAR_TYPE_FIXED', 'WF_TARGET_LINUX', '__LINUX__']
    subprocess.run(['g++', '-O2', '-std=c++17', '-fno-rtti', '-fpermissive', '-Wno-register',
                    *['-D' + flag for flag in flags], '-Iwfsource/source', '-Iengine/include',
                    '-Iengine/stubs', 'tests/face_normal_fixed_regression.cc', '-o', str(binary)],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
