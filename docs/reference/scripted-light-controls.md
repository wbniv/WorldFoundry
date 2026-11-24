# Scripted light controls

Light actors expose three read/write local-system mailboxes: `LIGHT_RED` (3048), `LIGHT_GREEN` (3049) and `LIGHT_BLUE` (3050). Values are normalized from 0 to 1, clamped to that range and stored as 8-bit color channels. They start at the authored light color. The current color is read when the light is applied to the camera, so changing one affects subsequent renders. Both ambient and directional lights support color.

Directional lights derive their direction from the actor's orientation. Use the existing `ROTATION_A`, `ROTATION_B` and `ROTATION_C` actor mailboxes (3012–3014), in revolutions; each write immediately changes that actor's rotation. Ambient light has no orientation. These controls do not create positional or spot lights.

For example, in zForth, with `sun` containing a directional light's actor index:

```forth
0.8 3048 sun write-actor-mailbox  \ red
0.6 3049 sun write-actor-mailbox  \ green
0.4 3050 sun write-actor-mailbox  \ blue
0.125 INDEXOF_ROTATION_B sun write-actor-mailbox
```

Mailbox 3051 (`MATERIAL_OPACITY`) sets mesh material 0 opacity from 0 to 1; it is write-only and has no effect on actors without a 3D mesh. Changes are quantized to 8-bit steps. Use it deliberately for translucent actors, taking care with depth sorting, shared material instances, static mesh caches and overdraw. Levels that never write these mailboxes keep their authored lighting and material behavior.
