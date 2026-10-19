#!/usr/bin/env python3
"""Compatibility alias for administration owned by the standalone project."""
from pathlib import Path
import subprocess
import sys

project=Path.home()/'chromecast-coordinator'
helper=project/'scripts/deploy-reviewed.py'
if not helper.is_file():
    raise SystemExit('Open the standalone coordinator project: '+str(project))
if not sys.argv[1:] and not (project/'deploy/review.json').is_file():
    raise SystemExit('Prepare/review a release in '+str(project)+
                     ', then use task coordinator:deploy there or pass --source RELEASE --review REVIEW to this alias.')
raise SystemExit(subprocess.call([sys.executable,str(helper),*sys.argv[1:]]))
