"""The two device-benchmark mesh fixtures must represent the same crowns."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bench = runpy.run_path(str(ROOT / 'scripts/generate-dfrm-merge-bench.py'))
sys.path.insert(0, str(ROOT / 'scripts'))
levels = runpy.run_path(str(ROOT / 'scripts/build-dfrm-merge-bench-levels.py'))


def test_merged_geometry_matches_fifteen_instances():
    single, single_faces, one_chunk = bench['make'](1)
    merged, merged_faces, merged_chunk = bench['make'](15)
    decode = bench['dc'].decode
    assert decode(one_chunk)['version'] == 1
    data = decode(merged_chunk)
    assert data['version'] == 2 and len(data['curves']) == 15
    assert len(merged_faces) == 15 * len(single_faces) == 180
    assert len(merged) == 15 * len(single)
    for i in range(15):
        offset = (i % 5, 0, (i // 5) * .75)
        for j, p in enumerate(single):
            assert all(abs(merged[i * len(single) + j][k] - p[k] - offset[k]) < 1e-12 for k in range(3))
        assert [(a + i * len(single), b + i * len(single), c + i * len(single))
                for a, b, c in single_faces] == merged_faces[i * len(single_faces):(i + 1) * len(single_faces)]


def test_level_variants_have_one_shared_animation_and_matching_layout():
    source = (ROOT / 'wflevels/aquarium_plants/aquarium_plants.lev').read_text()
    separate, si = levels['generate_scene'](source, False)
    merged, mi = levels['generate_scene'](source, True)
    assert len([name for name in si if name.startswith('crown-')]) == 15
    assert 'crowns' in mi
    assert separate.count('dfrm-pose bm-check') == 15
    assert merged.count('dfrm-pose-curves bm-check') == 1
    assert 'crown-single.iff' in separate and 'crowns-merged.iff' in merged
    assert ': bm-angle INDEXOF_TIME bm@ bm-frac .5 - 30 * ;' in separate
    assert ': bm-angle INDEXOF_TIME bm@ bm-frac .5 - 30 * ;' in merged
    controls = levels['controller'](mi, True)
    for curve in range(1, 15):
        assert f'{243 + 4 * curve} bm!' in controls
    for curve in range(15):
        assert f'1 {240 + 4 * curve} bm!' in controls
