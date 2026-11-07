"""Package each rebuilt reef as an auto-selected, temporary review APK."""
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
out = Path('/tmp/reef-leather-review-apks')
out.mkdir(exist_ok=True)
tools = Path('/home/will/android-sdk-local/build-tools/34.0.0')
source = root/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'
for style, level in [('realistic', 'aquarium_thai_reef'), ('anime', 'aquarium_thai_reef_anime')]:
    manifest = out/(style+'.manifest')
    manifest.write_text('title WF Aquarium\nprompt Choose a tank\nlevel '+
                        str(root/'wflevels'/(level+'-standalone.iff'))+
                        ' | Gulf of Thailand Reef '+style+'\n')
    asset = out/(style+'.iff')
    subprocess.run([str(root/'wftools/cdpack-rs/target/release/cdpack'),
                    str(root/'wfsource/source/game/shell-menu.fth'), '--manifest',
                    str(manifest), '-o', str(asset)], check=True)
    unsigned, aligned, signed = (out/(style+suffix) for suffix in ('-unsigned.apk','-aligned.apk','.apk'))
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(unsigned, 'w') as dst:
        for info in src.infolist():
            if not info.filename.startswith('META-INF/') and info.filename != 'assets/cd.iff':
                dst.writestr(info, src.read(info.filename))
        dst.writestr('assets/cd.iff', asset.read_bytes(), compress_type=zipfile.ZIP_STORED)
    subprocess.run([str(tools/'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
    subprocess.run([str(tools/'apksigner'), 'sign', '--ks', '/home/will/.android/debug.keystore',
                    '--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android',
                    '--key-pass', 'pass:android', '--out', str(signed), str(aligned)], check=True)
    subprocess.run([str(tools/'apksigner'), 'verify', str(signed)], check=True)
