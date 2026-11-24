"""Exercise live population changes in the actual zForth director."""
import tempfile
from pathlib import Path

def test_population_and_attached_decorations_follow_live_settings():
    import verify_cuckoo_village_forth as vm
    with tempfile.TemporaryDirectory() as temp:
        ids, indices = vm.build(Path(temp))
        host = vm.Host(Path(temp), ids, indices)
        try:
            for houses, trees, bavaria, flowers in ((24, 24, 1, 1), (0, 0, 1, 0),
                                                     (1, 1, 0, 0), (13, 12, 1, 1),
                                                     (24, 24, 0, 0)):
                host.frame_at(vm.day_of(2026, 12, 25), 23 * 3600, houses=houses,
                              trees=trees, bavaria=bavaria, flowers=flowers)
                for i in range(24):
                    present = int(i < houses)
                    assert host.read(300 + i) == present
                    assert host.read(360 + i) == present * flowers
                    assert host.read(400 + i) == present * (1 - flowers)
                    assert host.read(500 + i) == present
                    assert host.read(vm.tl.BAVARIA_HOUSE_CELL0 + i) == present * bavaria
                    tree = int(i < trees)
                    assert host.read(330 + i) == tree
                    assert host.read(440 + i) == tree
                    for group in range(2):
                        cell = vm.tl.FLICKER_CELL0 + 4 * i + 2 * group
                        assert host.read(cell) + host.read(cell + 1) == tree
        finally:
            host.close()
