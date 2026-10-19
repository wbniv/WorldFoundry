# Aquarium launcher artwork · 2026-10-03

Generated promotional illustration of a clownfish, tiger barb and betta; not a gameplay screenshot. `artwork.png` is the unmodified imagegen output. Original generation files remain in the imagegen output directory.

The second generation reframes the fish into Android's central safe region. `scripts/gen-android-icons.py aquarium` creates all five densities of square, round and adaptive icons and stamps the approved set D badge from `wflogo.png`. The existing school screenshot still supplies the TV banner.

Generation mode: imagegen, opaque square; followed by imagegen edit using the first generation as reference.

Initial prompt:

Use case: stylized-concept. Asset type: square Android launcher artwork for the World Foundry Aquarium game. Create a polished, distinctive underwater icon illustration, with subtly faceted 3D game-art shading. The primary subjects are a bright orange-and-white clownfish facing right at upper left and a teal-bodied ornamental betta with flowing red-violet fins facing left at lower right, with one smaller silver-gold tiger barb with four black vertical bands behind them. Calm deep navy and turquoise aquarium water, a few simple green aquatic leaves at the lower left, gentle light from above. Large readable silhouettes and restrained detail, appealing at 48px. Keep the entire three-fish group in the central 60 percent of the square so circular Android masks retain the fish; fill the rest with water and soft light. Leave the lower-right corner subdued for an existing badge that will be added by the project's resource generator. Full-bleed square image, no outer frame, no white padding, no rounded corners pre-applied, no aquarium glass edges, no words, no lettering, no logos, no watermark. This is promotional artwork, not a gameplay screenshot.

Edit prompt:

Preserve this exact underwater illustration, fish identities, colors and relative layout. Reframe it as a square Android adaptive icon: zoom out so all three fish together fit entirely within the central 60% of both width and height (roughly x20%-80%, y20%-80%). Extend the surrounding deep turquoise water and soft plants naturally to fill the square, without any frame, padding bands, borders, text or logo. Keep lower-right outer corner dark water for an existing badge. The entire clownfish tail and entire betta tail must fit within the central safe region.

Original source: `exec-742d75ff-968b-4aea-be5f-d68fd98dada7.png`, copied to `artwork.png`. Initial source: `exec-0b645c5b-b276-4fac-b557-b6ed336998dd.png`.

## Badge clearance correction

Will requested swapping the plant and betta because the badge covered the fish. The mask-fit iteration uses `artwork-betta-left-safe.png`; the earlier composition is retained for reference. The betta faces right at lower-left and the plants occupy lower-right. A second edit makes the entire tail fit the circular mask.

Swap edit prompt:

Edit target: the supplied Aquarium launcher illustration. Make only this composition change: swap the lower-left green aquatic plant cluster and the lower-right teal betta with red-violet flowing fins. The betta must be in the lower LEFT of the central safe circle, facing right toward the center, with its entire body and flowing tail visible. The plant cluster must be in the lower RIGHT, taking the betta's former position. Preserve the clownfish at upper left, tiger barb at upper right, underwater background, colors, lighting and illustration style. Keep all fish fully inside the central 60% of the square for Android circular masks. Reserve the lower-right badge area (roughly x60%-78%, y60%-80% of the whole image) for green foliage and water only: no fish body or fins there. Full bleed square, no frame, no added text, no logo; the existing World Foundry badge will be stamped separately.

Mask fit edit prompt:

Edit this image. Preserve every other element exactly. Only adjust the lower-left betta: reduce its size by about 20% and move it slightly upward and right so its entire flowing tail and fins fit inside the circle centered at (50%,50%) with radius 30% of the image width. Betta should occupy approximately x25%-52%, y47%-70% of this square. Keep it facing right. Preserve the green plants in the lower-right, clownfish upper-left, tiger barb upper-right, water, lighting, illustration style. No text, logos, borders or padding. This is an Android launcher icon source and every fish must survive a circular mask of the central two-thirds; lower-right will contain a badge.

First mask-fit imagegen source: `exec-40a810eb-4448-4f9d-9a27-c1e9b95db96c.png`. Intermediate swap source: `exec-214cd62f-a25d-4349-8abe-f60a402d61fa.png`, retained as `artwork-betta-left.png`. Both originals remain in the imagegen output directory.

Will then requested more space between the betta's nose and the badge. The final generator source is `artwork-betta-clear.png` (`exec-4bc0c4f1-f893-4f5c-b0ac-f542059e0f27.png`), moving the betta left and up while retaining its fins inside the round mask.

Clearance edit prompt:

Edit target: this Aquarium icon source. Change only the lower-left betta's position, preserving its size, identity, colors and flowing fins. Translate the betta LEFT by about 6% of the image width and UP by about 4% of the image height. Its nose should end around x47% of image width, leaving a generous visible gap from the World Foundry badge that will occupy x59%-73%, y61%-77%. Keep its entire tail and fins inside the central circular safe region (center 50%,50%, radius 30%). Preserve all other fish, plants, rocks, water and light exactly. No logos, text, border or padding.

## Lower the betta · version 5

Will found the betta too close to the clownfish after the clearance adjustment. The current generator uses `artwork-betta-lowered.png`, lowering that fish while keeping the horizontal badge clearance. Final imagegen source: `exec-e9b335be-0299-4454-965f-fba6d74b07ac.png`; the original remains in the imagegen output directory.

Lowering edit prompt:

Edit the supplied Aquarium icon illustration. Move ONLY the teal/red betta fish DOWN by 7% of the full image height. Keep its exact current horizontal position, size, orientation, colors and fin shape. Its uppermost fin should be approximately at y55% and its lowest fin at y74% of the square; create clear breathing room between it and the clownfish above. Keep the betta entirely visible inside Android's central circular mask: circle centered at x50%, y50% with radius33% of the image width. Do not move it to the right: retain the broad horizontal gap from the existing badge area at lower right. Preserve the clownfish, tiger barb, plants, water, rocks, lighting and overall illustration exactly. Do not add logos, text, borders or padding.
