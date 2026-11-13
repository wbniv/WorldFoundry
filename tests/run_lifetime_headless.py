"""Run a lifecycle check with a private Xvfb, using displayfd readiness (no signals).

Usage: run_lifetime_headless.py COMMAND [ARG...]
"""
import os
import select
import subprocess
import sys
import tempfile

read_fd, write_fd = os.pipe()
server = None
try:
    with tempfile.TemporaryFile() as errors:
        server = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0',
                                   '1280x1024x24', '-nolisten', 'tcp', '-ac'],
                                  pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=errors)
        os.close(write_fd)
        write_fd = None
        if not select.select([read_fd], [], [], 30)[0]:
            raise RuntimeError('Xvfb did not report a display within 30 seconds')
        number = os.read(read_fd, 128).decode().strip()
        if not number.isdigit():
            errors.seek(0)
            raise RuntimeError('Xvfb startup failed: ' + errors.read().decode(errors='replace'))
        result = subprocess.run(sys.argv[1:], env=dict(os.environ, DISPLAY=':' + number))
        sys.exit(result.returncode)
finally:
    os.close(read_fd)
    if write_fd is not None:
        os.close(write_fd)
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
