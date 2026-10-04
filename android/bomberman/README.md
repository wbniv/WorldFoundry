# Bomberman solo for Android TV

Offline WebView package of the current `/home/will/wf-games/bomberman` prototype.
Frozen assets and their source checksums are committed here; this is separate
from the planned smooth-movement and multiplayer work.

Remote arrows select a cat or move. OK starts/restarts/drops one bomb. Back pauses
or resumes. Backgrounding clears held directions and pauses the game.

Build: `python3 android/bomberman/build.py` (installed SDK and pinned ecj compiler).
Verify: `/home/will/wf-games/bin/dbox node android/bomberman/verify.mjs`.
Install: `python3 android/bomberman/install.py`.

Installation uses two coordinator-owned `install` jobs, preserving reservations
and the foreground app. It sends no input and never launches the installed app.
The installer may request local sudo authentication to activate the reviewed
coordinator adapter. Evidence is saved in `docs/diagnostics/bomberman-chromecast/`.
