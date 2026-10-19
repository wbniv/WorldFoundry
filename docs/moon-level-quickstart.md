# WorldFoundry Moon Level: New-Computer Quick Start

Use this guide to set up WorldFoundry on a new Debian-based Linux computer and
run the Moon level. It assumes a graphical desktop and a GitHub account and SSH
key with access to `wbniv/WorldFoundry`.

## 1. Install the bootstrap tools

```bash
sudo apt update
sudo apt install -y git curl gpg
```

Install [Go Task](https://taskfile.dev/) from the Foundry APT repository:

```bash
curl -fsSL https://apt.foundrylinux.org/key.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/foundry.gpg
echo "deb [signed-by=/etc/apt/keyrings/foundry.gpg] https://apt.foundrylinux.org resolute main" \
  | sudo tee /etc/apt/sources.list.d/foundry.list
sudo apt update
sudo apt install -y task
task --version
```

## 2. Confirm GitHub access and clone WorldFoundry

```bash
ssh -T git@github.com
git clone git@github.com:wbniv/WorldFoundry.git
cd WorldFoundry
git switch 2026-new-level
```

The expected SSH response says that authentication succeeded but GitHub does
not provide shell access. GitHub conventionally returns a nonzero status for
this test.

## 3. Install repository dependencies

```bash
task dev-setup
```

This is the repository's canonical setup command. It currently provisions both
the native runtime and Android toolchain. The Moon level does not use the
Android, web-editor, or collaborative-editor toolchains, but setup remains
owned by the repository task rather than duplicated as manual package steps.

## 4. Build and run the Moon level

```bash
task run-moon
```

On the first run, the task automatically:

1. initializes the required vendored submodules;
2. unpacks the vendored Jolt source if necessary;
3. builds `engine/wf_game`;
4. launches `wflevels/moon_site01-standalone.iff` with its required 1024²
   texture and VRAM settings.

Later runs skip the build while the binary is current. Use the same command:

```bash
task run-moon
```

Optional launch modes:

```bash
WF_FULLSCREEN=1 task run-moon
WF_RECORD=moon.mp4 task run-moon
WF_FULLSCREEN=1 WF_RECORD=moon.mp4 task run-moon
```

Runtime output is also written to `/tmp/wfgame_moon.log`.
