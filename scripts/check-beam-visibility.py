#!/usr/bin/env python3
"""Check colored clock-beam visibility in captured PC frames.

Usage: python3 scripts/check-beam-visibility.py frame.png [frame2.png ...]
The optional central exclusion prevents colored mirror housings from counting
as beams. Thresholds and exclusion are adjustable for other scenes/resolutions.
This measures sampled frames; it cannot prove visibility between samples.
"""
import argparse
from pathlib import Path
from PIL import Image
import numpy as np


def counts(path, exclusion=.075, center=(.5,.45)):
    im=Image.open(path).convert('RGB');w,h=im.size
    # Center of the instrument in this camera framing; ignore the mechanism.
    cx,cy=w*center[0],h*center[1];radius=min(w,h)*exclusion
    pixels=np.asarray(im,dtype=np.int16);r,g,b=(pixels[:,:,i] for i in range(3))
    y,x=np.ogrid[:h,:w];outside=(x-cx)**2+(y-cy)**2>=radius**2
    return {'amber':int(np.count_nonzero(outside & (r>150) & (r>g*1.3) & (g>45) & (b<80))),
            'green':int(np.count_nonzero(outside & (g>150) & (g>r*1.5) & (g>b*1.5))),
            'red':int(np.count_nonzero(outside & (r>160) & (r>g*2) & (r>b*2)))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames',nargs='+',type=Path)
    p.add_argument('--minimum',type=int,default=12,help='minimum visible colored pixels per beam')
    p.add_argument('--exclusion',type=float,default=.075,help='central exclusion radius as a fraction of the shorter screen side')
    p.add_argument('--center',type=float,nargs=2,default=(.5,.45),metavar=('X','Y'),help='mechanism center as fractions of image width and height')
    args=p.parse_args();fail=[]
    for frame in args.frames:
        c=counts(frame,args.exclusion,args.center)
        missing=[k for k,v in c.items() if v<args.minimum]
        print(frame, c, 'MISSING '+','.join(missing) if missing else 'PASS',flush=True)
        if missing:fail.append(frame)
    if fail:raise SystemExit(1)
if __name__=='__main__':main()
