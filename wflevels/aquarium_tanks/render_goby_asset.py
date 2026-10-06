"""Render the authored meshes/textures for plan review, without the engine."""
import argparse
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from goby import body, fins, write_textures, BODY_TEXTURE, FIN_TEXTURE, FIN_OPACITY


def raster(meshes, width=720, height=480, elevation=8, azimuth=0):
    """Orthographic source UV rasterizer; no per-face colour substitution.

    Sorted translucent triangles approximate blending for this review image;
    target-engine appearance remains subject to device verification.
    """
    pixels=np.empty((height,width,3),dtype=float);pixels[:]=(16,40,51)
    triangles=[];e=math.radians(elevation);a=math.radians(azimuth)
    scale=width/.98
    for mesh, image, opacity in meshes:
        texture=np.asarray(image,dtype=float)
        vertices=np.asarray(mesh.vertices);x,y,z=vertices.T
        xx=x*math.cos(a)-y*math.sin(a)
        yy=x*math.sin(a)+y*math.cos(a)
        projected=np.column_stack((width*.5+xx*scale,
                                  height*.56-(z*math.cos(e)+yy*math.sin(e))*scale,
                                  yy*math.cos(e)-z*math.sin(e)))
        for face in mesh.faces:
            for k in range(1,len(face)-1):
                ids=[face[0],face[k],face[k+1]]
                p=projected[ids];uv=np.asarray([mesh.uvs[i] for i in ids])
                triangles.append((float(p[:,2].mean()),p,uv,texture,opacity))
    for _,p,uv,texture,opacity in sorted(triangles,key=lambda t:t[0],reverse=True):
        lo=np.maximum(0,np.floor(p[:,:2].min(axis=0)).astype(int))
        hi=np.minimum((width-1,height-1),np.ceil(p[:,:2].max(axis=0)).astype(int))
        if np.any(hi<lo):continue
        xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
        den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(den)<1e-8:continue
        b0=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/den
        b1=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/den
        b2=1-b0-b1;inside=(b0>=0)&(b1>=0)&(b2>=0)
        u=np.clip(b0*uv[0,0]+b1*uv[1,0]+b2*uv[2,0],0,1)*255
        v=np.clip(b0*uv[0,1]+b1*uv[1,1]+b2*uv[2,1],0,1)*255
        tx,ty=u.astype(int),v.astype(int);fx=(u-tx)[...,None];fy=(v-ty)[...,None]
        nx,ny=np.minimum(tx+1,255),np.minimum(ty+1,255)
        rgb=(texture[ty,tx]*(1-fx)+texture[ty,nx]*fx)*(1-fy)+(texture[ny,tx]*(1-fx)+texture[ny,nx]*fx)*fy
        patch=pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        patch[inside]=patch[inside]*(1-opacity)+rgb[inside]*opacity
    return Image.fromarray(np.clip(pixels,0,255).astype('uint8'))


def render(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_textures(out)
    models=[(body(),Image.open(out/BODY_TEXTURE),1),
            (fins(),Image.open(out/FIN_TEXTURE),FIN_OPACITY)]
    canvas=Image.new('RGB',(1440,580),'#102833')
    canvas.paste(raster(models), (0,60))
    canvas.paste(raster(models,elevation=22,azimuth=-28), (720,60))
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    draw.text((40,26),'Side · actual UV texture sampling',font=font,fill='#e4f0ee')
    draw.text((760,26),'Oblique · turquoise cheek and patterned fins',font=font,fill='#e4f0ee')
    draw.text((155,548),'Authored mesh preview · not a device capture · transparency approximated',font=small,fill='#bad3d1')
    canvas.save(out/'goby-mesh-preview.png')
    atlas=Image.new('RGB',(512,300),'#102833')
    atlas.paste(Image.open(out/BODY_TEXTURE),(0,44));atlas.paste(Image.open(out/FIN_TEXTURE),(256,44))
    labels=ImageDraw.Draw(atlas);labels.text((12,10),'Body · 256²',font=small,fill='#e4f0ee')
    labels.text((268,10),'Fins · 256²',font=small,fill='#e4f0ee')
    atlas.save(out/'goby-texture-preview.png')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('out');render(parser.parse_args().out)
