#!/usr/bin/env python3
"""Audit timing sessions for the phone-controller panel; never changes measurements.

The aquarium APKs advertise a phone controller and draw its pairing panel over
the scene until Back hides it. Coordinator 8c24437 stopped sending that Back,
so later sessions can measure with the panel up. For every case this records
whether its app-layer capture shows the panel (white QR field plus black
modules inside the panel's QR rectangle) and, from the local raw logcat, when
the panel opened and whether Back hid it. Logcat stays local; only derived
booleans and second offsets are written.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from PIL import Image

STAMP = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)')


def capture_shows_panel(path):
    """True when the panel's QR field (x 132-706, y 232-806 at 1920x1080) is present."""
    with Image.open(path) as image:
        image = image.convert('RGB')
        if image.size != (1920, 1080):
            raise ValueError(f'Unexpected capture size {image.size}: {path}')
        samples = white = black = 0
        for y in range(240, 800, 8):
            for x in range(140, 700, 8):
                pixel = image.getpixel((x, y))
                samples += 1
                white += min(pixel) >= 245
                black += max(pixel) <= 12
    return white / samples >= 0.25 and black / samples >= 0.15


def log_events(path):
    if not path.exists():
        return dict(logcat='missing-locally')
    def times(needle):
        found = []
        for line in path.read_text(errors='replace').splitlines():
            stamp = STAMP.match(line)
            if needle in line and stamp:
                found.append(datetime.strptime('2026-' + stamp[1], '%Y-%m-%d %H:%M:%S.%f'))
        return found
    opened, hidden = times('phone controller: open'), times('Back: hides the phone panel')
    result = dict(panel_opened=bool(opened), back_hid_panel=bool(hidden), phone_connected=bool(times('Phone connected')))
    if opened and hidden:
        result['back_seconds_after_open'] = round((hidden[0] - opened[-1]).total_seconds(), 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('sessions', nargs='+', help='Session folders relative to --evidence')
    args = parser.parse_args()
    sessions = {}
    for session in args.sessions:
        folder = args.evidence / session
        receipt = json.loads((folder / 'receipt.json').read_text())
        dismissal = folder / 'panel-dismissal.json'
        dismissal = json.loads(dismissal.read_text()) if dismissal.exists() else {}
        cases = {}
        for run in sorted(folder.glob('*/run-1')):
            cases[run.parent.name] = dict(capture_shows_panel=capture_shows_panel(run / 'idle.png'),
                                          **log_events(run / 'logcat.txt'))
        screenshot = folder / 'screenshot.png'
        sessions[session] = dict(job=receipt['job'], device=receipt['device'],
                                 coordinator_back_sent=dismissal.get('back_sent', 'not-recorded (pre-8c24437: Back sent)'),
                                 coordinator_panel_visibility=dismissal.get('panel_visibility', 'not-recorded'),
                                 session_screenshot_shows_panel=capture_shows_panel(screenshot) if screenshot.exists() else None,
                                 cases=cases)
    with_panel = sorted(s for s, v in sessions.items() if any(c['capture_shows_panel'] for c in v['cases'].values()))
    result = dict(
        purpose='Phone-controller panel visibility in timing captures; an audit, not a measurement.',
        detector='QR field inside the panel rectangle: >=25% white and >=15% black samples (x 140-700, y 240-800, 8 px grid).',
        sessions_with_panel=with_panel,
        sessions_without_panel=sorted(set(sessions) - set(with_panel)),
        sessions=sessions)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(with_panel)} of {len(sessions)} sessions show the panel:', ', '.join(with_panel) or 'none')


if __name__ == '__main__':
    main()
