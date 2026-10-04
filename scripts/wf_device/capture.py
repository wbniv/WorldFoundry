"""Reviewed observational capture methods; no caller shell or app control."""
import json
import struct
import time
import zlib
from pathlib import Path

METHODS = {'png', 'raw', 'uiautomation', 'record', 'compare'}


def png_rgba(width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + pixels[i:i + width * 4] for i in range(0, len(pixels), width * 4))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def save_raw(data, out):
    # Android 12+ raw screencap: packed row pixels after four little-endian words.
    if len(data) < 16:
        raise RuntimeError('Raw capture header is truncated')
    width, height, fmt, color_space = struct.unpack('<4I', data[:16])
    if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 16777216:
        raise RuntimeError('Raw capture dimensions exceed reviewed limits')
    if fmt not in (1, 2):
        raise RuntimeError('Raw capture pixel format is unsupported: ' + str(fmt))
    pixels = data[16:]
    if len(pixels) != width * height * 4:
        raise RuntimeError('Raw capture pixel length does not match dimensions')
    (out / 'raw-screencap.bin').write_bytes(data)
    (out / 'raw-preserved.png').write_bytes(png_rgba(width, height, pixels))
    opaque = bytearray(pixels)
    opaque[3::4] = b'\xff' * (width * height)
    (out / 'raw-opaque-preview.png').write_bytes(png_rgba(width, height, opaque))
    summary = {'width': width, 'height': height, 'format': fmt, 'color_space': color_space,
               'alpha_min': min(pixels[3::4]), 'alpha_max': max(pixels[3::4]),
               'nonzero_rgb_pixels': sum(any(pixels[i:i + 3]) for i in range(0, len(pixels), 4)),
               'opaque_preview': 'Derived preview: original alpha replaced with 255; RGB unchanged'}
    (out / 'raw-analysis.json').write_text(json.dumps(summary, indent=2))
    return summary


def require_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 24:
        raise RuntimeError('Screen capture did not return a PNG')


def capture_current(adapter):
    method = adapter.req.get('method', 'png')
    selected = ['png', 'raw', 'uiautomation', 'record'] if method == 'compare' else [method]
    results = {}
    for name in selected:
        adapter.guard()
        adapter.store.phase(adapter.job['id'], 'capturing-' + name)
        started = time.time()
        try:
            if name == 'png':
                data = adapter.adb('exec-out', 'screencap', '-p', binary=True)
                require_png(data)
                (adapter.out / 'screenshot.png').write_bytes(data)
            elif name == 'raw':
                data = adapter.adb('exec-out', 'screencap', binary=True)
                # Preserve bytes even if an unsupported vendor format cannot be decoded.
                (adapter.out / 'raw-screencap.bin').write_bytes(data)
                save_raw(data, adapter.out)
            elif name == 'uiautomation':
                helper = Path(__file__).resolve().parents[2] / 'config' / 'capture-helper.jar'
                if not helper.is_file():
                    helper = Path(__file__).resolve().parents[2] / 'config/device-coordinator/capture-helper.jar'
                if not helper.is_file():
                    raise RuntimeError('Protected UI Automation helper is not installed')
                remote = '/data/local/tmp/wf-' + adapter.job['id'] + '-helper.jar'
                image = '/data/local/tmp/wf-' + adapter.job['id'] + '-automation.png'
                adapter.capture_remote.extend([remote, image])
                adapter.adb('push', str(helper), remote)
                # Device-side timeout bounds helper lifetime even if the ADB client dies.
                command = 'CLASSPATH=' + remote + ' timeout 15 app_process /system/bin WfCapture ' + image
                output = adapter.adb('shell', command, timeout=20)
                (adapter.out / 'uiautomation-helper.txt').write_text(output)
                data = adapter.adb('exec-out', 'cat', image, binary=True)
                require_png(data)
                (adapter.out / 'uiautomation.png').write_bytes(data)
            elif name == 'record':
                remote = '/data/local/tmp/wf-' + adapter.job['id'] + '.mp4'
                log = '/data/local/tmp/wf-' + adapter.job['id'] + '-screenrecord.txt'
                adapter.capture_remote.extend([remote, log])
                command = ('screenrecord --time-limit 3 --size 1280x720 --bit-rate 6000000 '
                           + remote + ' >' + log + ' 2>&1 & echo $!')
                adapter.record_pid = int(adapter.adb('shell', command).strip())
                (adapter.out / 'recording.json').write_text(json.dumps({'pid': adapter.record_pid, 'path': remote}))
                deadline = time.monotonic() + 13
                while time.monotonic() < deadline:
                    running = adapter.shell('cat', '/proc/' + str(adapter.record_pid) + '/cmdline', allow_failure=True)
                    if 'screenrecord' not in running:
                        break
                    adapter.wait(.25)
                else:
                    raise RuntimeError('Observational screen recording exceeded duration bound')
                adapter.record_pid = None
                (adapter.out / 'screenrecord.txt').write_text(adapter.shell('cat', log, allow_failure=True))
                data = adapter.adb('exec-out', 'cat', remote, binary=True)
                if len(data) < 1000:
                    raise RuntimeError('Observational screen recording is empty')
                (adapter.out / 'capture.mp4').write_bytes(data)
            results[name] = {'status': 'captured', 'started': started, 'finished': time.time()}
        except (RuntimeError, TimeoutError, ValueError) as exc:
            results[name] = {'status': 'failed', 'error': str(exc), 'started': started, 'finished': time.time()}
            (adapter.out / 'capture-methods.json').write_text(json.dumps(results, indent=2))
            if method != 'compare' or adapter.record_pid:
                raise
    (adapter.out / 'capture-methods.json').write_text(json.dumps(results, indent=2))
    if not any(entry['status'] == 'captured' for entry in results.values()):
        raise RuntimeError('All observational capture methods failed')
