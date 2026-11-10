"""Run in the Blender container after building tests/.cache/wf_core.so.

WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --factory-startup --python-exit-code 1 --python /src/tests/blender_runner/editor_label_roundtrip.py
"""
import sys
import tempfile
from pathlib import Path
sys.path[:0] = ['/src/tests/.cache', '/src/wftools']
import bpy
from wf_blender import export_level as ex
bpy.utils.register_class(ex.WF_OT_import_level)
work = Path(tempfile.mkdtemp(prefix='wf-editor-label-'))
source = work / 'in.lev'
source.write_text("{ 'LVL' { 'OBJ' { 'NAME' \"Settings\" } { 'STR' { 'NAME' \"Class Name\" } { 'DATA' \"plantedtanksettings\" } } { 'STR' { 'NAME' \"Editor Label\" } { 'STR' \"Goldie\" } } } }")
assert bpy.ops.wf.import_level(filepath=str(source), oad_dir='/src/wfsource/source/oas') == {'FINISHED'}
obj = bpy.data.objects['Settings']
assert obj['wf_Editor Label'] == 'Goldie'
obj['wf_Editor Label'] = 'A "quoted" name'
out = str(work / 'out.lev')
ok, message = ex.export_scene_to_lev(bpy.context, out)
assert ok, message
parsed = ex._parse_lev(Path(out).read_text())
item = ex._children_by_tag(parsed, 'OBJ')[0]
labels = [ex._name_value(c)[1] for c in ex._children_by_tag(item, 'STR') if ex._name_value(c)[0] == 'Editor Label']
assert labels == [['A "quoted" name']], labels
obj['wf_Editor Label'] = ''
ok, message = ex.export_scene_to_lev(bpy.context, out)
assert ok, message
assert 'Editor Label' not in Path(out).read_text()
print('editor label import/export, quotes and empty value: PASS')
