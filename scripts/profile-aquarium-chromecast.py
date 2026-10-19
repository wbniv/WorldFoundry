#!/usr/bin/env python3
"""Compatibility entry point; shared coordinator owns device work."""
from wf_device.legacy import profile
if __name__=="__main__": raise SystemExit(profile())
