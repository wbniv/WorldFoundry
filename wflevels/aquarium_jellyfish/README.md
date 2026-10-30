# Jellyfish

Build: `bash wflevels/aquarium_jellyfish/build.sh`.

Run: `bash wflevels/aquarium_jellyfish/run.sh`.

Hold OK for one second during play to open Settings. The Director offers live
Pulse tempo (Slow, Relaxed, Normal, Brisk, Fast), Stroke strength (Gentle,
Normal, Strong), Companions (0–50), and Jellyfish size (Small, Normal, Large).
The default is 5 companions, preserving the original 6 jellyfish. The bounded
Companions slider uses whole numbers. Beyond the original 5, new companions
appear in separated positions across the tank as the count increases.
Every jellyfish retains the full 341-face bell and arms geometry. The extras
combine those two meshes into one actor without dropping polygons.
On Chromecast HD, full-detail builds measured 59.8 fps with 0 companions,
50.2 fps with 5, and 39.2 fps with 12. Initial counts of 15, 26, and 50
caused the app to leave the foreground before measurement.
The 0–50 range is intended for testing on other devices, not a guarantee that
every count runs on Chromecast HD. Earlier low-detail measurements of about
58 fps at 5 and 35 fps at 26 are preserved in the diagnostics history.
The size setting changes the visible meshes; the player's collision hull keeps
its original dimensions.

Configuration and exported assets live here; procedural geometry, controls, checks and the isolated five-tank menu preview live in [aquarium_tanks](../aquarium_tanks/README.md).
