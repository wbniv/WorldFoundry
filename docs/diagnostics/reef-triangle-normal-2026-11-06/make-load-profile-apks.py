"""Add the same existing frame-profiler switch to each matched benchmark APK."""
import subprocess
import zipfile
from pathlib import Path

root = Path('/tmp/reef-profile-apks')
tools = Path('/home/will/android-sdk-local/build-tools/34.0.0')
for style in ('realistic', 'anime'):
    for variant in ('baseline', 'candidate'):
        name = style + '-' + variant
        source = root / (name + '.apk')
        unsigned = root / (name + '-load-unsigned.apk')
        aligned = root / (name + '-load-aligned.apk')
        signed = root / (name + '-load.apk')
        with zipfile.ZipFile(source) as src, zipfile.ZipFile(unsigned, 'w') as dst:
            for info in src.infolist():
                if info.filename.startswith('META-INF/'):
                    continue
                content = src.read(info.filename)
                if info.filename == 'assets/wf_args.txt':
                    content += b'\n--frame-profile\n'
                dst.writestr(info, content)
        subprocess.run([str(tools/'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
        subprocess.run([str(tools/'apksigner'), 'sign', '--ks', '/home/will/.android/debug.keystore',
                        '--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android',
                        '--key-pass', 'pass:android', '--out', str(signed), str(aligned)], check=True)
        subprocess.run([str(tools/'apksigner'), 'verify', str(signed)], check=True)
