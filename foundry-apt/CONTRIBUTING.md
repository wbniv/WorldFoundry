# Contributing to foundry-apt

Thanks for considering a contribution! This repo is the signed [APT repo](https://wiki.debian.org/DebianRepository) + metapackage source for [Foundry Linux](https://docs.worldfoundry.org).

## What to contribute

| Most useful | Examples |
|---|---|
| **Bug fixes** | A metapackage `Depends:` line references the wrong package; CI runs out of disk; sign.sh fails on a key with a passphrase. |
| **New vendored upstream packages** | Repackage `xa65`, an updated `f9dasm`, a newer `vgmstream` release. Each one needs a `packages/<name>/` dir, a build script, and the upstream's licence preserved under `/usr/share/doc/<name>/`. |
| **New metapackages** | A focused bundle (e.g. `worldfoundry-shaders-dev`) that pulls in a curated set of system deps. |
| **CI hardening** | shellcheck-clean scripts; arm64 build matrix; a `--dry-run` mode for sign.sh that uses a throwaway GPG key. |

## Workflow

1. **Open an issue first** for anything bigger than a one-line fix — it's cheaper to argue about scope before code than after.
2. Fork → branch from `main` → push → open a PR. The [test workflow](.github/workflows/test.yml) runs shellcheck + builds every `.deb` + checks the dependency closure. PRs that fail CI don't get reviewed.
3. **Don't bump versions in your PR** — the maintainer bumps them at tag time so versioning stays linear.
4. Sign your commits if you can (`git commit -S`). Not required, encouraged.

## Adding a metapackage

1. `mkdir -p packages/worldfoundry-<thing>/DEBIAN`
2. Write `packages/worldfoundry-<thing>/DEBIAN/control` matching the format of the existing five — Section: metapackages, Architecture: all, Depends: …
3. `bash scripts/build-all.sh` to verify it builds.
4. Update `packages/worldfoundry-dev/DEBIAN/control` if the new package should be pulled in by the top-level metapackage.
5. Mention it in `README.md`'s table.

## Adding a vendored upstream package

We repackage upstream binaries (or rebuild from source) when:
- The package isn't in the Ubuntu archive at all (e.g. [`task`](https://github.com/go-task/task), `xa65`), **or**
- The Ubuntu version is too old (e.g. Ghidra in 24.04 is years behind).

Steps:

1. `mkdir packages/<name>/`
2. Write `packages/<name>/build.sh` that:
   - Fetches the upstream artefact (pin a SHA256 — use `curl -fL … && echo "<sha>  -" | sha256sum -c -`)
   - Stages files into a `staging/` dir per the [Debian filesystem hierarchy](https://www.debian.org/doc/packaging-manuals/fhs/) (`usr/bin/`, `usr/share/doc/<name>/copyright`, etc.)
   - Writes `staging/DEBIAN/control` from a template, substituting the upstream version
   - Runs `dpkg-deb --build staging dist/<name>_<version>_<arch>.deb`
3. `bash scripts/build-all.sh` — it auto-detects packages with a `build.sh` and runs them before `dpkg-deb --build` is invoked on the staging tree.
4. Add the upstream's licence to `LICENSES-VENDORED.md`.
5. Confirm `dpkg-deb --info` shows the right metadata and `dpkg-deb --contents` shows the files in the right place.

## Releasing

Maintainer-only:

1. `git tag -s v1.0.X -m "..."` (signed tag).
2. `git push origin v1.0.X`.
3. Watch [the publish workflow](.github/workflows/publish.yml) — it builds, signs, syncs to R2, and smoke-installs `worldfoundry-dev` in a clean Ubuntu 26.04 container.
4. If smoke-install fails, the apt repo is still uploaded — fix forward with `v1.0.X+1`, don't try to delete a published version.

## Licence

By contributing you agree your work is licensed under [GPL-2.0](LICENSE) (matching the rest of the project).
