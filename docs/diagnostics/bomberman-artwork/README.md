# Cat-Boom! launcher artwork

Updated 2026-10-04 using the built-in imagegen tool. High-resolution masters are `cat-boom-icon.png` and `cat-boom-banner.png`; Android resources are exported at 512×512 and 320×180 respectively.

Prompt set: preserve the existing orange tabby, amber eyes, green scarf, gold paw badge, curled tail, dark navy background and polished illustration style. Raise its paw and add one airborne black cartoon bomb with a curved fuse, orange spark and subtle tossing arc. Keep the cat and bomb fully visible. For the banner, place the cat on the left and bold white title on the right. Remove WF; final title exactly `Cat-Boom!`.

The Android launcher label also uses `Cat-Boom!`. The existing package identifier stays stable for upgrades.

## Launcher refresh correction

The first artwork update reused versionCode 1. A device capture confirmed the launcher still displayed the old icon and label despite the new APK. VersionCode 2 (`0.2-cat-boom`) references new `cat_boom_icon` and `cat_boom_banner` resources. Background reinstall on Chromecast 01 succeeded, and `refreshed-launcher/screenshot.png` visually confirms the new name and airborne bomb. No launcher data was cleared and no restart was needed.

Chromecast 02 refresh job `J-d04b2d68ee0a` failed during connection because the registered Cast identity could not be discovered near its last address. The refreshed version is not yet verified there.
