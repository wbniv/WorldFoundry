# foundry-apt infrastructure setup

One-time human setup needed before [`publish.yml`](../.github/workflows/publish.yml) can sync the apt repo to its public home. Track progress in `## Status` at the bottom.

## 1. Generate the signing GPG key

Done locally on a machine with a [YubiKey](https://www.yubico.com/) ideally, otherwise a fresh USB stick:

```bash
gpg --full-generate-key
# Type: RSA (sign only)
# Bits: 4096
# Expires: 2 years (rotate annually)
# Real name: World Foundry Packages
# Email: packages@worldfoundry.org
gpg --armor --export packages@worldfoundry.org > /tmp/foundry-packages.pub.gpg
gpg --armor --export-secret-keys packages@worldfoundry.org > /tmp/foundry-packages.sec.gpg  # NEVER commit
```

Publish the **public** key to `worldfoundry.org/keys/packages.gpg` (Cloudflare Pages) and link from the README install snippet.

## 2. Store the private key in AWS SSM SecureString

```bash
# One-time: create a free AWS-managed KMS key alias (we get one free per account)
aws ssm put-parameter \
  --name /foundry-apt/signing-key \
  --type SecureString \
  --value "$(cat /tmp/foundry-packages.sec.gpg)" \
  --description "GPG private key for foundry-apt — used by GH Actions publish workflow"
shred -u /tmp/foundry-packages.sec.gpg
```

## 3. Create the GitHub OIDC role in AWS

The CI workflow uses [OIDC federation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect/configuring-openid-connect-in-amazon-web-services) so no long-lived AWS access keys ever leave AWS. Steps:

1. Add GitHub as an [OIDC identity provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) in IAM (URL: `https://token.actions.githubusercontent.com`, audience: `sts.amazonaws.com`).
2. Create an IAM role `foundry-apt-publish` with trust policy restricted to `repo:foundry-linux/foundry-apt:ref:refs/tags/v*` (tag pushes only).
3. Attach a minimal inline policy: `ssm:GetParameter` on `/foundry-apt/*` only.
4. Add the role ARN to the foundry-apt repo as the `AWS_ROLE_ARN` secret.

## 4. Create the Cloudflare R2 bucket

1. R2 dashboard → Create bucket → name: `foundry-apt`, region: `auto`.
2. Settings → R2.dev subdomain → enable (gives a free public URL like `pub-xxxxx.r2.dev` for smoke testing).
3. Create an [R2 API token](https://developers.cloudflare.com/r2/api/s3/tokens/) scoped to the `foundry-apt` bucket with `Object Read & Write`.
4. Add to the repo secrets:
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_ENDPOINT` (`https://<account-id>.r2.cloudflarestorage.com`)

## 5. Wire up the custom domain

1. Cloudflare DNS → add a CNAME `apt` → `pub-xxxxx.r2.dev` (proxied: orange cloud on).
2. R2 bucket → Settings → Public access → Connect custom domain → `apt.worldfoundry.org`.
3. Verify: `curl -I https://apt.worldfoundry.org/dists/resolute/Release` returns 200.

## 6. First release

```bash
git tag v1.0.0
git push origin v1.0.0
# Watch the publish workflow at:
#   https://github.com/foundry-linux/foundry-apt/actions
```

After it goes green, the smoke-install job inside the workflow proves a clean Ubuntu 26.04 container can `apt install worldfoundry-dev` from the live repo.

## Status

- [ ] GPG signing key generated
- [ ] Public key published to `worldfoundry.org/keys/packages.gpg`
- [ ] Private key stored in AWS SSM
- [ ] GitHub OIDC identity provider added to AWS
- [ ] `foundry-apt-publish` IAM role created
- [ ] `AWS_ROLE_ARN` repo secret set
- [ ] Cloudflare R2 bucket `foundry-apt` created
- [ ] R2 API token issued
- [ ] R2 secrets added to repo
- [ ] DNS CNAME `foundry.worldfoundry.org` configured
- [ ] Custom domain attached to R2 bucket
- [ ] First tag (`v1.0.0`) pushed
- [ ] Smoke-install passes against live repo
