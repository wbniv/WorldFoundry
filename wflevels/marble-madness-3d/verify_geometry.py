#!/usr/bin/env python3
"""Geometry checks against captured data and independently evaluated samples."""
import hashlib
import json
from pathlib import Path
import unittest
import generate

HERE=Path(__file__).resolve().parent

class PracticeGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((HERE/'practice.json').read_text())
        cls.mesh,cls.top=generate.course(cls.data)

    def test_captured_source_identity(self):
        digest=hashlib.sha256(json.dumps(self.data['cells'],separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,'9c20cd575bf040300269361595e9ae61af018409a6f8e3ba5e7ac2c74e4764cd')
        self.assertEqual(self.data['spawn_native'],[136,136])
        self.assertEqual(self.data['level_header'],'0x2bee2')

    def test_native_projection_scale(self):
        # At 30 degrees elevation the horizontal tile projects twice as wide
        # as high. One native height unit projects one original screen unit.
        import math
        self.assertAlmostEqual(generate.Z_SCALE*math.cos(math.pi/6),1/(8*math.sqrt(2)))
        self.assertEqual(generate.world(17,17,16384),(0,0,0))

    def test_nondegenerate_unique_upward_surface(self):
        seen=set()
        for tri in self.top:
            self.assertGreater(generate.cross(*tri)[2],0)
            key=tuple(sorted(tri));self.assertNotIn(key,seen);seen.add(key)
        self.assertEqual(len(self.top),3502)
        for a,b,c,material in self.mesh.faces:
            pts=[self.mesh.vertices[i][:3] for i in (a,c,b)]
            self.assertGreater(sum(n*n for n in generate.cross(*pts)),1e-12)
            self.assertIn(material,range(4))
        self.assertLess(len(self.mesh.vertices),32768)

    def height_at(self,x,y):
        for tri in self.top:
            a,b,c=tri
            det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det
            v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
            if min(u,v,1-u-v)>=-1e-8:return u*a[2]+v*b[2]+(1-u-v)*c[2]
        return None

    def test_independent_arcade_interpolation_and_voids(self):
        samples=json.loads((HERE/'parity-samples.json').read_text())['samples']
        solid=void=0
        for x,y,z in samples:
            actual=self.height_at(x,y)
            if z is None:
                void+=1;self.assertIsNone(actual,(x,y))
            else:
                solid+=1;self.assertIsNotNone(actual,(x,y));self.assertAlmostEqual(actual,z,places=7)
        self.assertGreaterEqual(solid,20);self.assertGreater(void,0)

    def test_start_support_and_finish_channel(self):
        self.assertEqual(self.height_at(0,0),0)
        self.assertAlmostEqual(generate.RADIUS,.48)
        self.assertLess(self.height_at(49,55),-4)
        self.assertIsNone(self.height_at(9.5,9.5))

if __name__=='__main__':unittest.main(verbosity=2)
