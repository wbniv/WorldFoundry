# foundry-apt

**Phase 1 of the [Foundry Linux](https://docs.worldfoundry.org) distro plan** — the signed APT repo + `worldfoundry-*` metapackages that collapse the Phase 0 curl-bash installer into a one-line `apt install worldfoundry-dev`.

## Quick start (consumer)

Once the repo is live at `foundry.worldfoundry.org`:

```bash
curl -fsSL https://foundry.worldfoundry.org/key.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/foundry.gpg
echo "deb [signed-by=/etc/apt/keyrings/foundry.gpg] https://foundry.worldfoundry.org resolute main" \
  | sudo tee /etc/apt/sources.list.d/foundry.list
sudo apt update
sudo apt install worldfoundry-dev
```

`resolute` is the suite name (matches Kubuntu 26.04's [release codename](https://kubuntu.org/news/kubuntu-26-04-resolute-released/) "Resolute Raccoon"). The repo also exposes a `noble` suite as an alias for 24.04 users on the `--allow-24.04` path.

## Metapackages

| Package | Pulls in | When you want it |
|---|---|---|
| **`worldfoundry-dev`** | everything below | Default — most contributors |
| `worldfoundry-engine-build-deps` | build-essential, cmake, libx11, libgl, gdb, xxd, pkg-config, git | Just compiling the engine |
| `worldfoundry-blender` | Blender 4.2 (from PPA) + python3 + engine-build-deps | Authoring levels |
| `worldfoundry-retro-tools` | mame, dasm, cc65, z80*, radare2, binwalk, sox, m68k binutils; Recommends [ghidra](https://ghidra-sre.org/), [f9dasm](http://www.df.lth.se.orbin.se/~triad/f9dasm/), [vgmstream](https://vgmstream.org/), [libvgm](https://github.com/ValleyBell/libvgm), xa65 | Porting arcade ROMs |
| `worldfoundry-android-dev` | JDK 17, adb, NDK r26c | Cross-compiling for Android (separate because ~3 GB) |

The package set comes from [`Taskfile.yml:236-251`](../Taskfile.yml) (`task dev-setup`) plus the retro tooling from [`docs/investigations/2026-05-15-claude-arcade-tooling.md`](../docs/investigations/2026-05-15-claude-arcade-tooling.md).

## Repo layout

```
foundry-apt/
  packages/
    worldfoundry-dev/DEBIAN/control
    worldfoundry-engine-build-deps/DEBIAN/control
    worldfoundry-blender/DEBIAN/control
    worldfoundry-retro-tools/DEBIAN/control
    worldfoundry-android-dev/DEBIAN/control
  aptly/
    aptly.conf                  Local aptly config (rootDir, architectures)
  scripts/
    build-all.sh                dpkg-deb --build for every package/
    init-repo.sh                aptly repo create (idempotent)
    publish-local.sh            aptly publish repo → ./public/
    sign.sh                     CI-side: fetch GPG key from AWS SSM, sign Release
  .github/workflows/
    test.yml                    PR: shellcheck + build all .debs + sanity check
    publish.yml                 tag push: build + sign + sync to Cloudflare R2
  dist/                         build output (gitignored)
  public/                       published apt repo (gitignored)
  docs/infra-setup.md           one-time setup: R2 bucket, AWS SSM, GPG, DNS
```

## Local development

Build every `.deb` and inspect the result without touching aptly:

```bash
bash scripts/build-all.sh
dpkg-deb --info dist/worldfoundry-dev_1.0.0_all.deb
dpkg-deb --contents dist/worldfoundry-dev_1.0.0_all.deb
```

End-to-end with [aptly](https://www.aptly.info/) (requires `sudo apt install aptly`):

```bash
bash scripts/build-all.sh       # → dist/*.deb
bash scripts/init-repo.sh       # → ~/.aptly/foundry repo
bash scripts/publish-local.sh   # → ./public/ apt tree
sudo apt-get update -o Dir::Etc::sourcelist="<(echo deb [trusted=yes] file://$(pwd)/public resolute main)"
apt-cache depends worldfoundry-dev
```

## Adding or upgrading a package

1. Bump `Version:` in `packages/<name>/DEBIAN/control` (semver — `1.0.0` → `1.0.1` for fixes, `1.1.0` for new deps).
2. Update the `Depends:` / `Recommends:` lines as needed.
3. `bash scripts/build-all.sh` to verify it builds.
4. Tag the release: `git tag v1.0.1 && git push origin v1.0.1` — the [publish workflow](.github/workflows/publish.yml) builds, signs, and syncs to R2 automatically.

## Phase 0 → Phase 1 → Phase 2+

- **[Phase 0](../foundry-linux-setup/)** (current): bash installer composes the apt list inline; works on any vanilla Ubuntu-family 26.04
- **Phase 1 (this repo):** signed apt repo + metapackages → `apt install worldfoundry-dev`
- **Phase 2:** `ghcr.io/worldfoundry/devbox:26.04` Distrobox image (`Dockerfile FROM ubuntu:26.04 RUN apt install worldfoundry-dev`)
- **Phase 3:** Foundry Linux ISO (`live-build` pulls from this repo into a Kubuntu 26.04 remix)

See [`docs/investigations/2026-05-16-foundry-linux-distro-proposal.md`](../docs/investigations/2026-05-16-foundry-linux-distro-proposal.md) for the full plan.

## Hosting

- **Apt repo:** [Cloudflare R2](https://www.cloudflare.com/developer-platform/products/r2/) (10 GB free tier, zero egress) → `foundry.worldfoundry.org`
- **Signing key:** [AWS SSM SecureString](https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-paramstore-securestring.html) (free tier) + [GitHub OIDC federation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect) — no long-lived AWS access keys in repo secrets
- **Release signing (annual):** YubiKey offline (Tier 2)

Detailed setup in [`docs/infra-setup.md`](docs/infra-setup.md).

## License

GPL-2 (matches the WF engine licence).
