"""Shared dimensions and budgets for the Gulf reef's static scene."""
SEED = 20261102
DIMENSIONS_M = (1.20, 0.60, 0.55)
WORLD_SCALE = 10.0
TITLE = 'Gulf of Thailand Reef'
STATIC_TRIANGLES_MAX = 70000
ANIME_STATIC_TRIANGLES_MAX = 70000
STATIC_GROUPS_MAX = 11
ANIME_HULL_TRIANGLES_MAX = 24000

WORM_TRIANGLES_MAX = 5000

# Rock-module kit (plan 2026-11-08 W5b). The Fixed arrangement keeps the budgets above; the
# worst set the Random layout can show at once (3 heroes with their dressing, the 2 largest
# fillers, every colony clump) has its own ceiling, checked on cast1 by R0 probe P4.
KIT_VISIBLE_TRIANGLES_MAX = {'realistic': 72000, 'anime': 72000}
KIT_VISIBLE_GROUPS_MAX = 22
# Room #0 asset slot (the standalone wrapper's RAM 'ROOM'; R0 report section 9). The cooked
# level must fit with every kit piece loaded; 36,000,000 is the tested fallback (ask first).
ROOM_SLOT_BYTES = 32_000_000
