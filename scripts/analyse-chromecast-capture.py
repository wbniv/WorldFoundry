#!/usr/bin/env python3
"""Analyse downloaded captures and extract recording frames locally."""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('evidence',type=Path)
args=parser.parse_args();directory=args.evidence.resolve()
if (directory/'capture.mp4').is_file():
    # A static screen may encode only one frame; always decode that first frame.
    for index,seconds in enumerate((0,.3,1.4,2.5),1):
        frame=directory/f'record-frame-{index:02}.png'
        with (directory/f'ffmpeg-frame-{index:02}.txt').open('w') as log:
            result=subprocess.run(['ffmpeg','-nostdin','-y','-ss',str(seconds),'-i',str(directory/'capture.mp4'),
                                   '-frames:v','1',str(frame)],stdout=log,stderr=subprocess.STDOUT,timeout=30)
        if result.returncode or not frame.is_file():
            print('No frame at '+str(seconds)+' seconds; see '+str(directory/f'ffmpeg-frame-{index:02}.txt'))
summary={}
for path in sorted(directory.glob('*.png')):
    with Image.open(path) as original:
        image=original.convert('RGBA');extrema=image.getextrema()
        summary[path.name]={'size':image.size,'rgba_extrema':extrema,
                            'fully_transparent':extrema[3][1]==0,
                            'rgb_all_zero':all(top==0 for low,top in extrema[:3])}
(directory/'image-analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
