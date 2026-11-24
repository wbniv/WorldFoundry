"""The tulip colorways share index images and preserve a pale measuring petal."""
import importlib.util
import struct
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'wflevels/corolla_gauge'
spec=importlib.util.spec_from_file_location('corolla_palette_assets',DIR/'palette_assets.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_colorways_keep_one_index_pattern_and_complete_lookup_tables():
    module.build()
    def indices(name):
        image=Image.open(DIR/name).convert('RGB')
        return [((r//8)<<3)|(g//8) for r,g,b in image.getdata()]
    rose=indices('petal-rose-index.png');ivory=indices('petal-ivory-index.png')
    assert len(rose)==512*512 and len(ivory)==len(rose)
    assert all(a<128 and b==a+128 for a,b in zip(rose,ivory))
    blob=(DIR/'tulip-palettes.bin').read_bytes()
    assert blob[:4]==b'DPLT'
    version,count=struct.unpack_from('<HH',blob,4)
    assert (version,count)==(1,6) and len(blob)==8+count*768
    tables=[blob[8+i*768:8+(i+1)*768] for i in range(count)]
    assert len({table[:384] for table in tables})==count
    assert len({table[384:] for table in tables})==1
