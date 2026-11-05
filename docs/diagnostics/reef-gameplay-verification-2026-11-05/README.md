# Reef gameplay verification

The new feather-duster, flowerpot and leather-coral meshes have deformation
curves. The feather-duster proximity and recovery timing and the changing
flowerpot current are exercised by `tests/test_species_movement.py`; the
exported deformation data and posed vertices are checked by
`tests/test_aquarium_thai_reef.py`.

The Pixel's installed Aquarium APK is SHA-256
`91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`.
The installation was verified, but launcher verification reported the device
locked. The following coordinator jobs were submitted and had not completed
when this note was written:

- J‑66b8b79a4891 compares diagnostic feather-duster views with the fish near
  and far.
- J‑9709aeb79835 runs both ordinary reef styles.
- J‑c325dfbe7700 compares diagnostic clam, guard-crab and cleaner-shrimp views
  with the fish near and far.

Each diagnostic level uses the current reef assets and reaction scripts, starts
the fish at a chosen position, and frames the corresponding animal. These are
controlled observations, not evidence of manually steering the fish through
the tank. The two build scripts record how the comparison packages were
assembled; their `/tmp` inputs are temporary. Each job restores the installed
APK above. Download each completed job with `task chromecast:evidence` and
inspect the images before declaring a visual reaction verified.
