# Aquarium launcher artwork · 2026-10-03

Generated promotional illustration of a clownfish, tiger barb and betta; not a gameplay screenshot. `artwork.png` is the unmodified imagegen output. Original generation files remain in the imagegen output directory.

The second generation reframes the fish into Android's central safe region. `scripts/gen-android-icons.py aquarium` creates all five densities of square, round and adaptive icons and stamps the approved set D badge from `wflogo.png`. The existing school screenshot still supplies the TV banner.

Generation mode: imagegen, opaque square; followed by imagegen edit using the first generation as reference.

Initial prompt:

Use case: stylized-concept. Asset type: square Android launcher artwork for the World Foundry Aquarium game. Create a polished, distinctive underwater icon illustration, with subtly faceted 3D game-art shading. The primary subjects are a bright orange-and-white clownfish facing right at upper left and a teal-bodied ornamental betta with flowing red-violet fins facing left at lower right, with one smaller silver-gold tiger barb with four black vertical bands behind them. Calm deep navy and turquoise aquarium water, a few simple green aquatic leaves at the lower left, gentle light from above. Large readable silhouettes and restrained detail, appealing at 48px. Keep the entire three-fish group in the central 60 percent of the square so circular Android masks retain the fish; fill the rest with water and soft light. Leave the lower-right corner subdued for an existing badge that will be added by the project's resource generator. Full-bleed square image, no outer frame, no white padding, no rounded corners pre-applied, no aquarium glass edges, no words, no lettering, no logos, no watermark. This is promotional artwork, not a gameplay screenshot.

Edit prompt:

Preserve this exact underwater illustration, fish identities, colors and relative layout. Reframe it as a square Android adaptive icon: zoom out so all three fish together fit entirely within the central 60% of both width and height (roughly x20%-80%, y20%-80%). Extend the surrounding deep turquoise water and soft plants naturally to fill the square, without any frame, padding bands, borders, text or logo. Keep lower-right outer corner dark water for an existing badge. The entire clownfish tail and entire betta tail must fit within the central safe region.

Final source: `exec-742d75ff-968b-4aea-be5f-d68fd98dada7.png`, copied to `artwork.png`. Initial source: `exec-0b645c5b-b276-4fac-b557-b6ed336998dd.png`.
