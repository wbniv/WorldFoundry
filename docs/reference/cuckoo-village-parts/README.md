# Cuckoo Village: what every part is

[cuckoo-village-parts.pdf](cuckoo-village-parts.pdf) (34 pages, A4): one card for each of the level's 102 actors, grouped as the ground, the cottages and trees, the clock tower (body, carved case piece by piece, what moves), Bavaria mode and the engine objects. Each card shows the part on its own, where it sits in the village or the tower (in magenta, ringed when small) and a wireframe with the hidden lines removed, and says what it is, what shows it and what moves it. The pictures are Blender renders of the level's own meshes under neutral light, not engine frames.

- The card texts are `wflevels/cuckoo_village/catalogue_entries.py`; `tests/test_cuckoo_village_catalogue.py` fails when an actor in `inventory.json` has no card.
- `inventory.json` is the built level's actor list (`CUCKOO_INVENTORY=<file>` with `blender_create_cuckoo_village.py`).
- `index.html` and `img/` are generated and not committed; regenerate them and the PDF with `scripts/cuckoo-village-catalogue.py` (its header gives the Blender render command, about 15 minutes on the CPU).
