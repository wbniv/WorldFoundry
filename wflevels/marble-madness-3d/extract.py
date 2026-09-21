"""Offline arcade terrain extraction. Research: magno73/marble-love (MIT)."""
import argparse, hashlib, json, os, shutil, struct, subprocess, tempfile, zipfile
from pathlib import Path

def s16(n):
    return (n + 32768) % 65536 - 32768

class Terrain:
    def __init__(self, path, capture, level=0):
        self.rom = bytearray(0x88000)
        with zipfile.ZipFile(path) as z:
            for even, odd, base in [('623','624',0x10000), ('625','626',0x18000), ('627','628',0x20000), ('229','630',0x28000), ('107','108',0x80000)]:
                self.rom[base:base+0x8000:2] = z.read('136033.'+even)
                self.rom[base+1:base+0x8000:2] = z.read('136033.'+odd)
        self.bank = 0
        self.header = self.long(0x2be00+4*level)
        self.terrain_bank = self.word(0x239a0+2*level)
        self.tile_bank = self.word(0x239ac+2*level)
        self.bank = self.terrain_bank
        self.bound = self.word(self.header+0x18)
        self.base=[]
        p=self.long(self.header+12)
        while self.word(p):
            self.base.extend([self.word(p+2)]*self.word(p)); p+=4
        self.code_table=self.long(self.header+0x26)
        self.direct=self.long(self.header)
        self.pf=bytearray((capture/'pf.bin').read_bytes())
        self.ram=(capture/'ram.bin').read_bytes()
        self.indirect=struct.unpack_from('>32H',self.ram,0x76e)
        self.bank=self.terrain_bank

    def byte(self,a):
        if 0x80000 <= a < 0x88000: a=0x80000+self.bank*8192+(a&8191)
        return self.rom[a]
    def word(self,a): return self.byte(a)*256+self.byte(a+1)
    def long(self,a): return self.word(a)*65536+self.word(a+2)

    def heights(self,x,y):
        """The arcade's 16-word neighborhood at integer 8-unit tile x,y."""
        row=x+y-20
        col=21-x+(row//2)
        steps=0x24b3a+(18 if row&1 else 0)
        out=[0]*16; dest=0
        for i in range(4):
            values=[0]*4
            if 0<=row<self.bound:
                d=col+(22 if row&1 else 0)
                if not 0<=d<44: return [0]*16
                # ROM lookup addresses the packed collision data in playfield memory.
                address=self.word(0x1eb3a+(row&~1))+self.byte(0x1ed0a+d)-2
                packed=struct.unpack_from('>I',self.pf,address)[0]
                idx=(packed>>self.byte(0x1ed36+d))&0x7fe
                code=self.word(self.code_table+idx)
                seen=set()
                while 0x800<=code<0x1000:
                    if code in seen: raise ValueError('Cyclic indirect terrain reference')
                    seen.add(code)
                    index=(code&0x7fe)//2
                    if index>=len(self.indirect): raise ValueError('Uncaptured dynamic terrain index')
                    code=self.indirect[index]
                base=self.base[row]
                if code>=0x1000:
                    top=(base+(code&127)-64)&65535
                    coef=self.word(0x1ed62+((code>>6)&62))
                    low=0 if coef==4096 else (top-coef)&65535
                    values=[top if code&(1<<(12+k)) else low for k in range(4)]
                elif code:
                    values=[(self.byte(self.direct+code+k)+base-128)&65535 if self.byte(self.direct+code+k) else 0 for k in range(4)]
            out[dest:dest+4]=values
            col+=s16(self.word(steps+i*6));row+=s16(self.word(steps+i*6+2))
            dest+=4+s16(self.word(steps+i*6+4))//2
        return out


def extract(rom_dir, output, mame):
    with tempfile.TemporaryDirectory(prefix='mm3d-extract-') as temp:
        capture=Path(temp)
        env=os.environ.copy();env['MM3D_CAPTURE_DIR']=temp
        command=[mame,'marble','-rompath',str(rom_dir),'-video','none','-sound','none',
                 '-nothrottle','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',
                 str(Path(__file__).with_name('capture.lua')),'-nvram_directory',temp,
                 '-cfg_directory',temp,'-snapshot_directory',temp]
        with (capture/'mame.log').open('w') as log:
            subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
        t=Terrain(str(rom_dir/'marble.zip'),capture)
        ram=t.ram
        assert struct.unpack_from('>I',ram,0x474)[0]==0x2bee2, 'MAME did not start Practice'
        traces=json.loads((capture/'queries.json').read_text())
        mismatches=[]
        for q in traces:
            actual=t.heights(q['x'],q['y'])
            if actual!=q['h']:mismatches.append(q)
        if mismatches:raise RuntimeError(f'{len(mismatches)} MAME terrain queries disagreed')
        cells=[]
        for x in range(t.bound+22):
            for y in range(t.bound+22):
                h=t.heights(x,y);corners=[h[13],h[8],h[7],h[2]]
                if any(corners):cells.append([x,y,corners])
        data={'format':1,'course':'Practice','level_header':'0x2bee2',
              'source':'Atari Marble Madness set 1; MAME runtime collision map',
              'rom_sha256':hashlib.sha256((rom_dir/'marble.zip').read_bytes()).hexdigest(),
              'capture_frame':600,'corner_order':['00','10','11','01'],
              'tile_units':8,'height_origin':16384,'spawn_native':[136,136],
              'query_checks':len(traces),'cells':cells}
        output.write_text(json.dumps(data,separators=(',',':'))+'\n')
        print(f'PASS: {len(traces)} MAME queries matched; {len(cells)} terrain cells extracted')
        shutil.copy(capture/'mame.log',output.with_suffix('.mame.log'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path(__file__).with_name('practice.json'))
    p.add_argument('--mame',default=shutil.which('mame') or '/usr/games/mame')
    a=p.parse_args();extract(a.rom_dir.resolve(),a.output.resolve(),a.mame)
