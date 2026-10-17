#!/usr/bin/env python3
"""Retain frozen release pairs and replace superseded profiling fixtures.

Never rewrites an APK. Each cohort retains its native/source provenance, and
the cooked assets must match exactly between release and profile fixtures.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-fixtures', type=Path, required=True)
    parser.add_argument('--profile-fixtures', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    release = json.loads((args.release_fixtures / 'variants.json').read_text())
    profile = json.loads((args.profile_fixtures / 'variants.json').read_text())
    if profile.get('profile_scope_version') != 2:
        raise ValueError('Corrected profiling scope v2 is required')
    variants, sources = {}, {}
    for name, original in release['variants'].items():
        if original['frame_profile']:
            continue
        item = copy.deepcopy(original)
        item.update(native=release['native'], cohort='release', profile_scope_version=None)
        variants[name] = item
        sources[name] = args.release_fixtures / (name + '.apk')
    for name, original in profile['variants'].items():
        if not original['frame_profile']:
            continue
        paired = variants[name.removesuffix('-profile')]
        if any(original[field] != paired[field] for field in ['cd_sha256', 'level_sha256']):
            raise ValueError('Cooked assets changed between cohorts: ' + name)
        item = copy.deepcopy(original)
        item.update(native=profile['native'], cohort='profile')
        variants[name] = item
        sources[name] = args.profile_fixtures / (name + '.apk')
    for name, source in sources.items():
        if sha(source) != variants[name]['apk_sha256']:
            raise ValueError('Frozen fixture changed: ' + name)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        target = args.out / (name + '.apk')
        if target.exists():
            if sha(target) != variants[name]['apk_sha256']:
                raise ValueError('Conflicting output fixture: ' + name)
        else:
            target.symlink_to(source.resolve())
    result = dict(profile_scope_version=2, variants=variants,
                  cohorts={label: {k: manifest[k] for k in ['native', 'source_revision', 'source_diff_sha256', 'base_apk_sha256']}
                           for label, manifest in [('release', release), ('profile', profile)]},
                  source_manifests={label: dict(path=str(path.resolve()), sha256=sha(path)) for label, path in
                                    [('release', args.release_fixtures / 'variants.json'),
                                     ('profile', args.profile_fixtures / 'variants.json')]},
                  note='Release CPU/GPU pairs share one native build; corrected profile pairs share another. Cooked assets match exactly. Never combine instrumented presentation with release timing.')
    (args.out / 'variants.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Verified immutable release/profile cohorts:', args.out)


if __name__ == '__main__':
    main()
