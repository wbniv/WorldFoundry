#!/usr/bin/env python3
"""Parse the Royal Thai Navy Hydrographic Department's yearly tide table (station HD) into events.

    python3 -I parse_hd.py HD2026.pdf 2026   ->  prints a summary; importable: parse(pdf, year)

Each page has three months; each month is two sub-tables (days 1-15 and 16-31) whose TIME columns start at
x = 72, 159, 246, 333, 420, 507 pt. A sub-table has a day-number column 21 pt left of TIME, then a TIME column
and a height column; each row is one predicted high or low (local Thai time, UTC+7; heights in metres).
"""
import datetime as dt
import re
import subprocess
import sys

TIME_X = [72, 159, 246, 333, 420, 507]


def words(pdf, page):
    out = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True, check=True).stdout
    return [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in
            re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', out)]


def parse(pdf, year):
    events = []                              # (datetime, height)
    for page in range(1, 5):
        ws = words(pdf, page)
        for k, tx in enumerate(TIME_X):
            month = (page - 1) * 3 + k // 2 + 1
            half = k % 2
            col = [w for w in ws if tx - 32 <= w[0] < tx + 62 and w[1] > 140]
            days = sorted((w[1], int(w[4])) for w in col if re.fullmatch(r"\d{1,2}", w[4]) and tx - 32 <= w[0] < tx - 8)
            times = [(w[1], w[4]) for w in col if re.fullmatch(r"\d{4}", w[4]) and tx - 8 <= w[0] < tx + 25]
            heights = [(w[1], float(w[4])) for w in col if re.fullmatch(r"\d\.\d\d", w[4]) and tx + 25 <= w[0] < tx + 62]
            for i, (y0, day) in enumerate(days):
                y1 = days[i + 1][0] if i + 1 < len(days) else 1e9
                ev_t = sorted((y, t) for y, t in times if y0 - 1.5 <= y < y1 - 1.5)
                for y, t in ev_t:
                    hs = [h for yh, h in heights if abs(yh - y) < 2.0]
                    assert len(hs) == 1, (page, month, day, t, hs)
                    hh, mm = int(t[:2]), int(t[2:])
                    events.append((dt.datetime(year, month, day) + dt.timedelta(hours=hh, minutes=mm), hs[0]))
    events.sort()
    return events


def check(events, year):
    problems = []
    days = {}
    for t, h in events:
        days.setdefault(t.date(), []).append((t, h))
    d = dt.date(year, 1, 1)
    while d.year == year:
        n = len(days.get(d, []))
        if n < 1 or n > 4:
            problems.append(f"{d}: {n} events")
        d += dt.timedelta(days=1)
    for (t0, h0), (t1, h1) in zip(events, events[1:]):
        gap = (t1 - t0).total_seconds() / 3600
        if not (2.0 <= gap <= 14.0):
            problems.append(f"gap {gap:.1f} h between {t0} and {t1}")
    return problems, days


if __name__ == "__main__":
    pdf, year = sys.argv[1], int(sys.argv[2])
    ev = parse(pdf, year)
    probs, days = check(ev, year)
    hs = [h for _, h in ev]
    print(f"{year}: {len(ev)} events on {len(days)} days; height {min(hs):.2f} to {max(hs):.2f} m; {len(probs)} problems")
    for p in probs[:12]:
        print("  ", p)
    from collections import Counter
    print("events per day:", dict(sorted(Counter(len(v) for v in days.values()).items())))
