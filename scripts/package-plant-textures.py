#!/usr/bin/env python3
"""Format the generated six-tile albedo into the runtime's padded 256-square atlas."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'wflevels/aquarium_plants'
source=Image.open(folder/'leaf-surfaces-source.png').convert('RGB')
atlas=Image.new('RGB',(256,256),(120,138,72))
for tile in range(6):
    col,row=tile%3,tile//3
    region=source.crop((col*source.width//3,row*source.height//2,(col+1)*source.width//3,(row+1)*source.height//2))
    interior=region.resize((72,112),Image.Resampling.LANCZOS)
    x,y=col*80+4,row*120+4
    atlas.paste(interior,(x,y))
    # Extrude edge texels into gutters to avoid sampling a neighbouring species.
    atlas.paste(interior.crop((0,0,1,112)).resize((4,112)),(x-4,y))
    atlas.paste(interior.crop((71,0,72,112)).resize((4,112)),(x+72,y))
    atlas.paste(atlas.crop((x-4,y,x+76,y+1)).resize((80,4)),(x-4,y-4))
    atlas.paste(atlas.crop((x-4,y+111,x+76,y+112)).resize((80,4)),(x-4,y+112))
atlas.save(folder/'leaf_surfaces.tga')
atlas.save(folder/'leaf-surfaces-atlas.png')
print('Packed six 72x112 albedo tiles with four-pixel gutters into 256x256 RGB atlas')
