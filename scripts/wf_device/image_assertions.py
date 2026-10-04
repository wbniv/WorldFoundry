"""Minimal 8-bit RGB/RGBA PNG decoder for unchanged-camera animation assertions."""
import struct
import zlib


def pixels(data):
    if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Not PNG')
    compressed=[];offset=8;width=height=channels=None
    while offset<len(data):
        size=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];chunk=data[offset+8:offset+8+size];offset+=size+12
        if kind==b'IHDR':
            width,height,depth,color,_,_,interlace=struct.unpack('>IIBBBBB',chunk)
            if depth!=8 or color not in (2,6) or interlace:raise ValueError('Unsupported PNG format')
            channels=3 if color==2 else 4
        elif kind==b'IDAT':compressed.append(chunk)
        elif kind==b'IEND':break
    if not width or width*height>4096*4096:raise ValueError('PNG dimensions out of bounds')
    raw=zlib.decompress(b''.join(compressed));stride=width*channels;rows=[];previous=bytearray(stride);offset=0
    for _ in range(height):
        method=raw[offset];current=bytearray(raw[offset+1:offset+stride+1]);offset+=stride+1
        for i in range(stride):
            a=current[i-channels] if i>=channels else 0;b=previous[i];c=previous[i-channels] if i>=channels else 0
            if method==0:predict=0
            elif method==1:predict=a
            elif method==2:predict=b
            elif method==3:predict=(a+b)//2
            elif method==4:
                p=a+b-c;pa=abs(p-a);pb=abs(p-b);pc=abs(p-c)
                predict=a if pa<=pb and pa<=pc else b if pb<=pc else c
            else:raise ValueError('Unsupported PNG filter')
            current[i]=(current[i]+predict)&255
        rows.append(current);previous=current
    return width,height,channels,rows


def changed_center(first,second):
    w,h,c,a=pixels(first);w2,h2,c2,b=pixels(second)
    if (w,h,c)!=(w2,h2,c2):raise ValueError('Animation image dimensions changed')
    return sum(a[y][x*c:x*c+3]!=b[y][x*c:x*c+3]
               for y in range(int(h*.30),int(h*.65)) for x in range(int(w*.35),int(w*.65)))
