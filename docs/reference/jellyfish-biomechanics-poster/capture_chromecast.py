#!/usr/bin/env python3
"""Jellyfish capture compatibility alias to the shared coordinator profiler."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
from wf_device.legacy import profile
if __name__=='__main__':raise SystemExit(profile(jellyfish=True))
