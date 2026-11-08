#!/usr/bin/env python3
"""Create a visibly provisional, scrollable HTML review draft, never a print PDF."""
from pathlib import Path

import make_poster

HERE = Path(__file__).resolve().parent

if __name__ == '__main__':
    html, _ = make_poster.build(draft=True)
    out = HERE / 'review-draft.html'
    out.write_text(html, encoding='utf-8')
    print(out)
