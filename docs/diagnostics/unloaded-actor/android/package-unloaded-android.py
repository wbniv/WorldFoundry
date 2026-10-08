"""Freeze two diagnostic APKs with the audited armeabi-v7a release library."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
repo=Path('/home/will/WorldFoundry-wbniv/.worktrees/teleport-audit')
fixture=Path('/home/will/finding-your-way-rooms/game/parmenides-slice/build-rooms/scene9/diag/g1v1-loop')
base=fixture/'parmenides-5e1911563e747939.apk';key=fixture/'development-signing.p12'
library=Path('/tmp/t4-android-armv7/libwf_game-unloaded-device.so');out=Path('/tmp/t4-unloaded-android-apks');out.mkdir(exist_ok=True)
tools=Path('/home/will/android-sdk-local/build-tools/34.0.0')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
patch=subprocess.check_output(['git','diff','--','wfsource/source/game','wfsource/source/room'],cwd=repo)
receipts=[]
for label,cd in [('unloaded-actor',Path('/tmp/t4-unloaded-autonomous/cd.iff'))]:
    unsigned=out/(label+'-unsigned.apk');aligned=out/(label+'-aligned.apk');signed=out/(label+'-signed.apk')
    with zipfile.ZipFile(base) as zin,zipfile.ZipFile(unsigned,'w') as zout:
        original_level=zin.read('assets/cd.iff')
        for info in zin.infolist():
            if info.filename.startswith(('META-INF/','lib/')):continue
            data=zin.read(info.filename)
            if info.filename=='assets/cd.iff' and cd:data=cd.read_bytes()
            if info.filename=='assets/wf_args.txt':
                arguments=data.decode().split();arguments=[x for x in arguments if x!='--frame-profile']
                data=('\n'.join(arguments)+'\n').encode()
            entry=zipfile.ZipInfo(info.filename,date_time=info.date_time)
            entry.external_attr=info.external_attr
            entry.compress_type=zipfile.ZIP_STORED if info.filename=='assets/cd.iff' else info.compress_type
            zout.writestr(entry,data)
        zout.writestr('lib/armeabi-v7a/libwf_game.so',library.read_bytes(),compress_type=zipfile.ZIP_STORED)
    subprocess.run([tools/'zipalign','-f','4',unsigned,aligned],check=True)
    subprocess.run([tools/'apksigner','sign','--ks',key,'--ks-pass','pass:android','--out',signed,aligned],check=True)
    subprocess.run([tools/'apksigner','verify',signed],check=True)
    digest=sha(signed);frozen=out/(label+'-'+digest[:16]+'.apk');signed.rename(frozen);frozen.chmod(0o444)
    receipt=dict(label=label,apk=str(frozen),apk_sha256=digest,base_apk=str(base),base_sha256=sha(base),
        library=str(library),library_sha256=sha(library),unstripped_library_sha256=sha(Path('/tmp/t4-android-armv7/libwf_game.so')),
        stripped='DWARF debug sections removed; dynamic symbols and code retained',abi='armeabi-v7a',assertions=False,ubsan=False,
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),source_diff_sha256=hashlib.sha256(patch).hexdigest(),
        cd_sha256=sha(cd) if cd else hashlib.sha256(original_level).hexdigest(),arguments=arguments,
        note='Diagnostic only; audited 32-bit library replaces both base ABIs. Level cd.iff stored uncompressed. Chapter level bytes unchanged.' if not cd
             else 'Diagnostic only; audited 32-bit library and autonomous four-room cd.iff; base Android manifest/Java glue retained.')
    (out/(label+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');receipts.append(receipt)
    print(label,frozen,digest,flush=True)
(out/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
