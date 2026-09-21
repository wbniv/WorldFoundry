#!/usr/bin/env python3
"""Launch this standalone course from any working directory."""
import os
from pathlib import Path
import sys
here=Path(__file__).resolve().parent
root=here.parents[1]
os.chdir(root/'wfsource/source/game')
os.execv(str(root/'engine/wf_game'),[str(root/'engine/wf_game'),'-L'+str(here/'marble-madness-3d-standalone.iff'),*sys.argv[1:]])
