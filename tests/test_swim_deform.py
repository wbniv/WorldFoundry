"""Shared model-frame waves keep fin roots attached without changing legacy deformers."""
from pathlib import Path
import subprocess


def test_common_span_root_attachment_and_bounded_rest_pose(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=tmp_path/'swim.cc'
    source.write_text(r'''
#include "wfsource/source/renderassets/swim_deform.h"
#include <cassert>
#include <cmath>
int main() {
 using wf_render::SwimWaveWeight;
 auto body=SwimWaveWeight::make(-1.8f,.2f,-3.25f,2.69f,.3f,0);
 auto root=SwimWaveWeight::make(-1.8f,.22f,-3.25f,2.69f,.3f,0);
 auto edge=SwimWaveWeight::make(-1.8f,.22f,-3.25f,2.69f,.3f,1);
 auto head=SwimWaveWeight::make(2.3f,.1f,-3.25f,2.69f,.9f,0);
 for(int frame=0;frame<10000;frame++) {
  float p=frame*.01f,s=std::sin(p),c=std::cos(p);
  auto b=body.deform(s,c,.2f,-.35f,s,c,0);
  auto r=root.deform(s,c,.2f,-.35f,s,c,.15f);
  assert(std::abs((r-b)-.02f)<.000001f);
  assert(head.deform(s,c,.2f,-.35f,s,c,.15f)==.1f);
  assert(std::abs(edge.deform(s,c,.2f,-.35f,s,c,.15f)-r)<=.150001f);
  assert(body.deform(s,c,0,0,s,c,0)==.2f);
 }
 assert(body.body.y==.2f && root.body.y==.22f);
}
''')
    binary=tmp_path/'swim'
    subprocess.run(['c++','-std=c++11','-I'+str(root),'-I'+str(root/'wfsource/source'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
