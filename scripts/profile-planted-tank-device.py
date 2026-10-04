#!/usr/bin/env python3
"""Compatibility entry point; shared coordinator owns device work."""
from wf_device.legacy import planted
if __name__=="__main__": raise SystemExit(planted())
