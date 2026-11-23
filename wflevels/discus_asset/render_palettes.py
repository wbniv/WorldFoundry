"""Build and capture each palette in the real desktop renderer."""
import json,os,subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[2];p=Path(__file__).resolve().parent
names=list(json.loads((p/'palettes.json').read_text()))
for name in names:
 print('Rendering',name,flush=True)
 env=dict(os.environ,DISCUS_PALETTE=name)
 for command in [['blender','--background','--python-exit-code','1','--python',str(p/'model.py')],['blender','--background','--python-exit-code','1','--python',str(p/'export_level.py')],['bash',str(root/'wftools/wf_blender/build_level_binary.sh'),'discus_asset'],['python3',str(p/'check_desktop.py')]]:
  subprocess.run(command,cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)
 Image.open(p/'engine.png').save(p/('engine-'+name+'.png'))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
sheet=Image.new('RGB',(1920,((len(names)+2)//3)*390),'#111d22');draw=ImageDraw.Draw(sheet)
for i,name in enumerate(names):
 x=(i%3)*640;y=(i//3)*390
 im=Image.open(p/('engine-'+name+'.png')).convert('RGB');sheet.paste(im.crop((0,50,640,400)),(x,y));draw.text((x+24,y+350),name,font=font,fill='white')
sheet.save(p/'engine-palettes.png')
print('Saved',p/'engine-palettes.png',flush=True)
