# Foundry Linux Phase 1 bootstrap

**Date:** 2026-05-17
**Status:** In progress
**Scope:** All setup needed before the GitHub Actions `publish.yml` in `foundry-linux/foundry-apt`
can build, sign, and serve the APT repo at `apt.foundrylinux.org`.

Everything here is executed via CLI — no manual console steps except where explicitly called out
as the minimum unavoidable surface (with justification).

Reference for command-level detail: [`foundry-apt/docs/infra-setup.md`](../../foundry-apt/docs/infra-setup.md).

---

## ~~Step 1 — Decide the canonical domain~~ (done)

**`apt.foundrylinux.org`** — `foundrylinux.org` is the registered domain; the `apt` subdomain is
self-describing. All tooling updated to reflect this.

---

## Step 1b — Create the Cloudflare operator API token

Handled automatically by `bootstrap.sh` when `CF_API_TOKEN` is not already exported.
Uses the **Global API Key** once to mint a scoped `foundry-linux-operator` token;
the Global API Key is not needed again after that.

---

## ~~Step 2a — Create the `foundry-linux` GitHub org~~ (done)

Org exists. GitHub org creation has no public API — noted here as the one unavoidable manual step.
All subsequent GitHub operations use `gh` CLI.

---

## ~~Step 2b — Push `foundry-apt/` to its own GitHub repo~~ (done)

`foundry-apt/` in the linuxfoundry.org repo is the development working copy;
the standalone `foundry-linux/foundry-apt` repo is the CI-facing authoritative source.
The `publish.yml` OIDC trust policy scopes to `repo:foundry-linux/foundry-apt:ref:refs/tags/v*`.

---

## Steps 3–9 — Run `bootstrap.sh`

Steps 2b–9 are fully automated. From the `linuxfoundry.org` repo root:

```bash
# If you don't have CF_API_TOKEN yet, also export:
export CF_EMAIL="wbnorris@gmail.com"
export CF_GLOBAL_API_KEY="<global-api-key>"
# Global API Key: Cloudflare dash → My Profile → API Tokens → Global API Key

bash scripts/bootstrap.sh --dry-run   # preview all steps
bash scripts/bootstrap.sh             # run for real
```

Step 1b (CF operator token) runs automatically when `CF_API_TOKEN` is not already exported.
If `CF_API_TOKEN` is already set (re-run scenario), set `CF_ACCOUNT_ID` and `CF_ZONE_ID` too.

What the script does, in order:
- **1b** Create `foundry-linux-operator` Cloudflare token (R2 + DNS + user-token:edit)
- **2b** Push `foundry-apt/` to `foundry-linux/foundry-apt` on GitHub
- **3** Generate 4096-bit RSA GPG signing key (`packages@foundrylinux.org`, 2-year expiry)
- **4** Store private key in AWS SSM `/foundry-apt/signing-key`; shred local copy
- **5** Register GitHub OIDC provider in AWS IAM; create `foundry-apt-publish` role
- **6** Create R2 bucket `foundry-apt`; create scoped `foundry-apt-ci` CI token
- **7** Create proxied DNS CNAME `apt.foundrylinux.org`; attach custom domain to bucket
- **8** Upload `key.gpg` to R2; shred local public key copy
- **9** Set `AWS_ROLE_ARN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` secrets

All steps are idempotent — safe to re-run.

---

## Step 10 — Push the first tag

```bash
gh repo clone foundry-linux/foundry-apt /tmp/foundry-apt-release
git -C /tmp/foundry-apt-release tag v0.0.1
git -C /tmp/foundry-apt-release push origin v0.0.1
# Watch: https://github.com/foundry-linux/foundry-apt/actions
```

The `smoke-install` job at the end of `publish.yml` proves a clean Ubuntu 26.04 container can
install a metapackage from the live repo.

---

## Verification

After the workflow goes green, run from any Ubuntu 26.04 machine (or container):

```bash
curl -fsSL https://apt.foundrylinux.org/key.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/foundry.gpg

echo "deb [signed-by=/etc/apt/keyrings/foundry.gpg] https://apt.foundrylinux.org resolute main" \
  | sudo tee /etc/apt/sources.list.d/foundry.list

sudo apt update
apt-cache show foundry-linux-dev
```

`apt-get install -y --no-install-recommends foundry-linux-dev` in a container is the definitive test.

---

## Status checklist

- [x] Domain decided — `apt.foundrylinux.org`
- [ ] Cloudflare operator token `foundry-linux-operator` created (`CF_API_TOKEN`)
- [x] `foundry-linux` GitHub org created
- [x] `foundry-linux/foundry-apt` GitHub repo created and pushed
- [ ] GPG signing key generated (`packages@foundrylinux.org`, 4096-bit RSA, 2-year expiry)
- [ ] Private key stored in AWS SSM at `/foundry-apt/signing-key`
- [ ] Local copy of private key shredded
- [ ] GitHub OIDC identity provider added to AWS IAM
- [ ] `foundry-apt-publish` IAM role created with scoped trust + minimal SSM policy
- [ ] R2 bucket `foundry-apt` created
- [ ] R2.dev subdomain enabled
- [ ] Scoped R2 CI token created
- [ ] Public signing key uploaded to R2 as `key.gpg`
- [ ] DNS CNAME `apt.foundrylinux.org` configured (proxied)
- [ ] Custom domain attached to R2 bucket
- [ ] `AWS_ROLE_ARN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` secrets set on repo
- [ ] First tag `v0.0.1` pushed
- [ ] `publish.yml` workflow green
- [ ] `smoke-install` job confirms `apt install foundry-linux-dev` from live repo
