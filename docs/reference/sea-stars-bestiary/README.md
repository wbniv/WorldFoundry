# Sea Stars bestiary catalogue

[Nine-page PDF](sea-stars-bestiary.pdf) · [HTML catalogue](index.html)

Six species are presented with a three-quarter portrait, dorsal view, side
profile and oral view. A cover shows the default ten-animal tank; a player
page shows Lead, the front-glass underside, Corner and Reach. The closing
register records Blender objects and research references.

The dark palette, serif headings and grouped model turnarounds follow
`finding-your-way/docs/art-bible/npc-catalog.html`. The sea stars use dorsal,
side and oral views because they have no fixed front. These are renders of
the actual authored meshes and materials. Planned behaviour is labelled;
gameplay and device acceptance remain pending.

Rebuild from the packed Blender master:

```sh
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
  --python-exit-code 1 --python wflevels/aquarium_sea_stars/render_bestiary.py -- \
  --out /src/docs/reference/sea-stars-bestiary/views
python3 wflevels/aquarium_sea_stars/build_bestiary.py
```

Editable entry text is in `catalogue.json`. `views/manifest.json` records the
source-master hash and each of the 18 view hashes. The original full-size
three-quarter and pose images remain in `../sea-stars-art/`.
