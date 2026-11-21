# Sea Stars — source-asset review

These images render the actual authored 3D meshes, skins and Blender arm rigs.
The soft lighting is for asset review. They are not gameplay screenshots or
Chromecast performance evidence. Gameplay integration and device testing are
held until this asset pass is ready for review, as requested on 2026-11-20.

- [Tank composition](01-tank-wide.png): open sand, three bare outcrops, brittle-star ledge, three Thalassia clumps and the ten-animal default population.
- [Six species](02-species-sheet.png): blue Linckia, chocolate-chip star, red Fromia, sand-sifting star, green brittle star and cushion star.
- [Player poses and underside](03-player-sheet.png): leading arm, front-glass oral face, corner bend and Reach.
- [512-square source atlas](04-texture-atlas.png): dorsal species skins, oral skin, dark knobs, red eyespot, marginal plates, sand, rock, seagrass and water.

Editable source: `wflevels/aquarium_sea_stars/sea_stars_assets.blend`. The atlas is
packed into the master. Each true sea-star arm has four bones; the brittle star has sixteen per arm, with a curled resting pose;
the source stores Glide, Lead, Corner, Reach, Row and Hide actions where
applicable, plus transform actions for burial, emergence and cushion puff.
The game meshes carry corresponding five-curve DFRM v2 bindings. The cushion
uses transforms only. See [the research sheet](../sea-stars-research.md) for the
boundary between observed biology and approved stylized animation.

The source preserves the game UV convention. A material-node conversion lets
Blender display the atlas correctly without changing the exported coordinates.
Runtime exports are reproducibly built from the generators, not by exporting
the presentation lighting from the review master.

Rebuild all meshes, atlas, packed master and rendered views:

```sh
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
  --python-exit-code 1 --python wflevels/aquarium_sea_stars/generate.py -- \
  --repo /src --out /src/wflevels/aquarium_sea_stars \
  --art-dir /src/docs/reference/sea-stars-art
python3 wflevels/aquarium_sea_stars/review_images.py
python3 -m pytest tests/test_sea_stars_assets.py -q
```

[Source-file validation](verification.json) and [16 asset checks](asset-checks.txt) accompany the review.

The static scenery is 3,474 triangles across four groups, below the approved
20,000 / four-group limit. The six species have separate exported models;
multiple residents reuse their species geometry.

[Bestiary catalogue PDF](../sea-stars-bestiary/sea-stars-bestiary.pdf): six entries, eighteen orthographic views, player poses and source register.
