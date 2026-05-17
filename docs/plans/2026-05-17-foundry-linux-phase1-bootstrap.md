# Foundry Linux Phase 1 bootstrap — manual setup

**Date:** 2026-05-17
**Status:** Not started
**Scope:** All one-time human actions needed before the GitHub Actions `publish.yml` in `worldfoundry/foundry-apt` can build, sign, and serve the APT repo at `apt.worldfoundry.org`. Covers GitHub repo extraction, GPG key generation, AWS SSM + OIDC, and Cloudflare R2 + DNS.

Phase 0 (setup script split) is complete. Phase 1 is blocked on these steps. Nothing here requires code changes — it is all account/infra setup.

Reference for command-level detail: [`foundry-apt/docs/infra-setup.md`](../../foundry-apt/docs/infra-setup.md).

---

## Pre-flight

Before starting, confirm you have access to:

| Account | Used for |
|---------|----------|
| [github.com/worldfoundry](https://github.com/worldfoundry) org (admin) | create the new repo, set secrets |
| [Cloudflare dashboard](https://dash.cloudflare.com/) (worldfoundry.org zone) | R2 bucket, DNS, Pages |
| [AWS console](https://console.aws.amazon.com/) (or CLI configured) | SSM SecureString, IAM OIDC role |
| A machine with `gpg`, `aws` CLI, and `git` installed | key gen + SSM upload |

---

## ~~Step 1 — Decide the canonical domain~~ (resolved)

**`apt.worldfoundry.org`** — matches the proposal and is self-describing. `publish.yml` and `infra-setup.md` updated 2026-05-17.

---

## Step 2a — Create both GitHub orgs

Go to [github.com/organizations/new](https://github.com/organizations/new) twice:

| Org | Plan | Purpose |
|-----|------|---------|
| `worldfoundry` | Free | Engine, games, wftools — `WorldFoundry`, `wf-games`, etc. |
| `foundry-linux` | Free | Distro infrastructure — `foundry-apt`, `foundry-linux-iso`, `foundry-devbox`, `foundry-docs` |

Domain **`foundrylinux.org`** is registered and on Cloudflare. Distro APT endpoint: **`apt.foundrylinux.org`** (R2 bucket, same pattern as `apt.worldfoundry.org`).

Both free, no payment needed.

---

## Step 2b — Extract `foundry-apt/` into its own GitHub repo

`foundry-apt/` currently lives inside the main `WorldFoundry.2026-new-level` repo. The `publish.yml` OIDC trust policy scopes to `repo:foundry-linux/foundry-apt:ref:refs/tags/v*`, so it must be a standalone repo.

```bash
# From the WorldFoundry.2026-new-level root:
cd foundry-apt
git init
git add .
git commit -m "Initial commit: foundry-apt Phase 1 setup"
# Create the GitHub repo (public):
gh repo create foundry-linux/foundry-apt --public --source=. --remote=origin --push
```

After pushing: enable **GitHub Discussions** on the new repo
(Settings → General → Features → Discussions ✓).

---

## Step 3 — Generate the GPG signing key

On a machine with a [YubiKey](https://www.yubico.com/) attached (or any clean, offline-capable machine):

```bash
gpg --full-generate-key
# Type: RSA (sign only)  |  Bits: 4096  |  Expires: 2 years
# Name: World Foundry Packages
# Email: packages@worldfoundry.org
gpg --armor --export packages@worldfoundry.org > /tmp/foundry-packages.pub.gpg
gpg --armor --export-secret-keys packages@worldfoundry.org > /tmp/foundry-packages.sec.gpg
```

The secret key file must **never** be committed. Shred it immediately after step 4.

---

## Step 4 — Store the private key in AWS SSM

```bash
aws ssm put-parameter \
  --name /foundry-apt/signing-key \
  --type SecureString \
  --value "$(cat /tmp/foundry-packages.sec.gpg)" \
  --description "GPG private key for foundry-apt — CI signing"
shred -u /tmp/foundry-packages.sec.gpg
```

Uses the free AWS-managed `aws/ssm` KMS key (no $1/month customer-managed key needed).

---

## Step 5 — Create GitHub OIDC identity provider in AWS IAM

No long-lived AWS credentials in GitHub — [OIDC federation](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) only.

1. IAM → Identity Providers → Add provider:
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. Create IAM role `foundry-apt-publish`:
   - Trusted entity: the OIDC provider above
   - Condition: `token.actions.githubusercontent.com:sub` = `repo:worldfoundry/foundry-apt:ref:refs/tags/v*`
   - Inline policy — minimal:
     ```json
     {
       "Effect": "Allow",
       "Action": ["ssm:GetParameter", "kms:Decrypt"],
       "Resource": "arn:aws:ssm:*:*:parameter/foundry-apt/*"
     }
     ```

3. Copy the role ARN — needed in step 7.

---

## Step 6 — Create Cloudflare R2 bucket and issue API token

1. [R2 dashboard](https://dash.cloudflare.com/?to=/:account/r2) → Create bucket → name: `foundry-apt`, region: `auto`.
2. Bucket → Settings → R2.dev subdomain → Enable (gives a `pub-xxxxx.r2.dev` URL for smoke testing).
3. [R2 API tokens](https://dash.cloudflare.com/?to=/:account/r2/api-tokens) → Create API token:
   - Permissions: Object Read & Write
   - Bucket: `foundry-apt` only
   - Note the **Access Key ID**, **Secret Access Key**, and your **account ID** (visible in the URL).

---

## Step 7 — Configure DNS and attach the custom domain

1. Cloudflare DNS (worldfoundry.org zone) → Add record:
   - Type: CNAME
   - Name: `apt` (for `apt.worldfoundry.org`) — or `foundry` if you chose the other name
   - Target: `pub-xxxxx.r2.dev`
   - Proxy: orange cloud (proxied)

2. R2 bucket → Settings → Public access → Connect custom domain → `apt.worldfoundry.org`.

3. Verify once propagated: `curl -I https://apt.worldfoundry.org/` should return 200 (the bucket is empty at this point, so 404 on `InRelease` is fine — just checking TLS + routing).

---

## Step 8 — Publish the public signing key

The smoke-install job in CI fetches the key from `https://apt.worldfoundry.org/key.gpg`. It needs to be there before the first tag push.

Upload `/tmp/foundry-packages.pub.gpg` to the R2 bucket as `key.gpg`:

```bash
export AWS_ACCESS_KEY_ID=<R2 access key>
export AWS_SECRET_ACCESS_KEY=<R2 secret key>
aws s3 cp /tmp/foundry-packages.pub.gpg \
  s3://foundry-apt/key.gpg \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com
```

Also copy it to `worldfoundry.org/keys/packages.gpg` (Cloudflare Pages) and link from the repo README install snippet.

Shred the local copy: `shred -u /tmp/foundry-packages.pub.gpg`.

---

## Step 9 — Set repo secrets on `worldfoundry/foundry-apt`

On [github.com/worldfoundry/foundry-apt](https://github.com/worldfoundry/foundry-apt) → Settings → Secrets and variables → Actions:

| Secret name | Value |
|-------------|-------|
| `AWS_ROLE_ARN` | ARN of `foundry-apt-publish` role from step 5 |
| `R2_ACCESS_KEY_ID` | From step 6 |
| `R2_SECRET_ACCESS_KEY` | From step 6 |
| `R2_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |

---

## Step 10 — Push the first tag

```bash
cd foundry-apt   # the new standalone repo
git tag v1.0.0
git push origin v1.0.0
```

Watch [github.com/worldfoundry/foundry-apt/actions](https://github.com/worldfoundry/foundry-apt/actions). The `smoke-install` job at the end proves a clean Ubuntu 26.04 container can `apt install worldfoundry-dev` from the live repo.

---

## Verification

After the workflow goes green:

```bash
# From any Ubuntu-family 26.04 machine:
curl -fsSL https://apt.worldfoundry.org/key.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/foundry.gpg
echo "deb [signed-by=/etc/apt/keyrings/foundry.gpg] https://apt.worldfoundry.org resolute main" \
  | sudo tee /etc/apt/sources.list.d/foundry.list
sudo apt update
apt-cache show worldfoundry-dev   # should print the metapackage description
```

`apt-get install -y --no-install-recommends worldfoundry-dev` (in a container, not your dev machine) is the definitive test.

---

## Status checklist

- [x] Domain name decided (`apt.worldfoundry.org`) and code updated
- [ ] `worldfoundry` GitHub org created (free plan)
- [ ] `foundry-linux` GitHub org created (free plan)
- [ ] `foundry-linux/foundry-apt` GitHub repo created and pushed
- [ ] GitHub Discussions enabled on the repo
- [ ] GPG signing key generated (`packages@worldfoundry.org`, 4096-bit RSA, 2-year expiry)
- [ ] Public key uploaded to R2 as `key.gpg` and to `worldfoundry.org/keys/packages.gpg`
- [ ] Private key stored in AWS SSM at `/foundry-apt/signing-key`
- [ ] Local copy of private key shredded
- [ ] GitHub OIDC identity provider added to AWS IAM
- [ ] `foundry-apt-publish` IAM role created with scoped trust + minimal policy
- [ ] R2 bucket `foundry-apt` created
- [ ] R2 API token issued (Read + Write, bucket-scoped)
- [ ] DNS CNAME `apt.worldfoundry.org` → R2 bucket configured (proxied)
- [ ] Custom domain attached to R2 bucket
- [ ] `AWS_ROLE_ARN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` repo secrets set
- [ ] First tag `v1.0.0` pushed
- [ ] `publish.yml` workflow goes green
- [ ] `smoke-install` job confirms `apt install worldfoundry-dev` works from the live repo
