# One-time setup

**Run `task setup`.** (Equivalently `./scripts/setup.sh`.) It automates every section below
except the three inputs no credential can supply on its own — creating the AWS IAM user,
minting the Codemagic API token, and creating the PagerDuty service. The script is idempotent
(safe to re-run after stopping partway), checks the real remote state before every phase
rather than a local marker file, and shows exactly what it is about to write before every
mutation, asking for confirmation each time. Nothing is stored blindly.

`task setup-check` reports which credentials already exist without prompting or changing
anything — start there if you just want to know where you stand.

There is no `task deploy` counterpart here: WorldFoundry has no Terraform and nothing to
provision. This is pure credential bootstrap for CI, specifically to make
[`.github/workflows/codemagic-budget.yml`](../.github/workflows/codemagic-budget.yml) live —
it is inert until all three of `secrets.CODEMAGIC_API_TOKEN`, `vars.WF_CODEMAGIC_APP_ID` and
`secrets.PAGERDUTY_ROUTING_KEY` exist on [wbniv/WorldFoundry](https://github.com/wbniv/WorldFoundry).

Per-project credential discipline applies here the same as everywhere else: WorldFoundry gets
its own `wf-terraform` AWS user and its own `/wf/*` SSM namespace — never borrowed from
another project's, even though several live under the same AWS account.

## What ends up where

| Credential | Source of truth | Also written to |
|---|---|---|
| AWS access key | `~/.aws/credentials` `[wf-terraform]` | `~/.aws/config` `[profile wf-terraform]` |
| Codemagic API token | SSM SecureString `/wf/codemagic-api-token` | GitHub secret `CODEMAGIC_API_TOKEN`; local `~/.config/codemagic/token` (0600) |
| Codemagic app id (not secret) | GitHub **variable** `WF_CODEMAGIC_APP_ID` | local `~/.config/codemagic/app-id` |
| PagerDuty routing key | SSM SecureString `/wf/pagerduty-routing-key` | GitHub secret `PAGERDUTY_ROUTING_KEY` |

Every run is logged to `.setup-logs/setup-<UTC timestamp>.log`, with `.setup-logs/latest.log`
pointing at the most recent one (gitignored). No secret is ever echoed to stdout, so those
logs are safe to read back when something fails.

---

## A. AWS: create the `wf-terraform` IAM user (~3 min)

WorldFoundry has no AWS access at all today, and no existing credential can create a new IAM
user for it — so this first step is unavoidably manual. Everything afterwards is automated.

1. Create the IAM user: [console → IAM → Users → Create user](https://us-east-1.console.aws.amazon.com/iam/home#/users/create)
   - Name: `wf-terraform` — do **not** tick "Provide user access to the AWS Management Console"
2. On the "Set permissions" screen choose **Attach policies directly**, then:

   | Filter by Type | Search | Action |
   |---|---|---|
   | AWS managed - job function | `AdministratorAccess` | tick it |
   | AWS managed - job function | `ReadOnlyAccess` | tick it |

   Click the **Policies selected** tab to confirm both are checked → Next → Create user.
3. Open the new user → **Security credentials** → **Create access key**
   - Use case: **Command Line Interface (CLI)** → acknowledge the warning
   - Description tag: `wf-terraform-<your hostname>`
   - Copy both values immediately — the secret is shown exactly once.
4. Paste them when the script asks. It writes `~/.aws/credentials` via `configparser`
   (so a re-run after a mistyped key repairs the entry instead of appending a broken
   duplicate), appends the profile block to `~/.aws/config` with `region = us-east-1`, and
   verifies with `aws sts get-caller-identity`.

Region override: `WF_AWS_REGION=eu-west-1 task setup` if `us-east-1` is ever wrong for this
project. The region only affects where the two SSM parameters live.

**Standing caveat — the AdministratorAccess grant is not narrowed.** The
[`iam-bootstrap`](../../.config/claude/will/skills/iam-bootstrap/SKILL.md) pattern narrows a
project's IAM user via a Terraform-managed `infrastructure/aws/iam-self/` module, so the broad
grant is temporary. WorldFoundry has no Terraform at all, and its entire AWS surface is two
SSM SecureStrings — so that phase is deliberately skipped rather than a whole Terraform state
backend being stood up for it. If WF ever grows real infra, run the full `iam-bootstrap` flow
then and narrow this user as part of it.

## B. Codemagic: API token + app id

### The token

Codemagic has no API for minting its own API token, so this one is manual too.

1. Open [https://codemagic.io/settings](https://codemagic.io/settings)
2. Top-left: pick your account/team (the personal account, for WorldFoundry)
3. **Settings → Integrations**
4. Row **Codemagic API** → click **Show** (or **Connect**, if it has never been enabled)
5. Copy the token and paste it when the script asks (input is hidden)

The script validates it before storing anything: a `GET` of
[https://api.codemagic.io/apps](https://api.codemagic.io/apps) with an `x-auth-token` header,
where HTTP 200 means valid. That is deliberately the identical check
the `codemagic-build` skill's driver makes in its own `bootstrap` subcommand
(`~/.claude/skills/codemagic-build/codemagic.py`), so both paths agree on what "valid" means.
A non-200 aborts the phase and stores nothing.

Once validated it goes to three places: SSM `/wf/codemagic-api-token` (source of truth), the
GitHub Actions secret `CODEMAGIC_API_TOKEN`, and `~/.config/codemagic/token` (mode 0600) so
the `codemagic-build` skill works locally without an `export`.

If a later step fails (network, `gh` auth), the token is session-cached in
`.setup-logs/.codemagic-session-cache` so a re-run does not re-prompt for it. That cache is
deleted the moment the phase reaches its real end state.

### The app id

There is no API to look this up — it is the hex id in the dashboard URL.

1. Open [https://codemagic.io/apps](https://codemagic.io/apps)
2. Click the WorldFoundry app
3. Copy the id out of the URL: `codemagic.io/app/<APP_ID>/...`

It is not a secret, so the prompt echoes it. It is stored as a GitHub Actions **variable**
(`gh variable set WF_CODEMAGIC_APP_ID`, not `gh secret set`) because the budget workflow reads
it as `vars.WF_CODEMAGIC_APP_ID`, and additionally written to `~/.config/codemagic/app-id`.

**What changed to make that local file work:** `~/.claude/skills/codemagic-build/codemagic.py`
previously resolved the app id from `--app-id` or `$CODEMAGIC_APP_ID` only. It now falls back
to `~/.config/codemagic/app-id` (new `APP_ID_FILE` + `_need_app_id()`), mirroring how it
already resolves the token from `~/.config/codemagic/token`. So after `task setup`, both
`codemagic.py build` and `codemagic.py logs` work in a fresh shell with no environment
variables set at all. That file lives in the shared skills tree, not in this repo.

## C. PagerDuty: service + Events API v2 routing key

1. Open [https://app.pagerduty.com/service-directory](https://app.pagerduty.com/service-directory)
2. **+ New Service**
3. Name: `worldfoundry-codemagic-budget`
4. Escalation policy: your default (Will Norris)
5. Integrations → select **Events API V2** → **Create Service**
6. On the new service's **Integrations** tab, copy the **Integration Key** — that is the
   routing key

Paste it when the script asks (hidden). It is stored at SSM `/wf/pagerduty-routing-key` and as
the GitHub Actions secret `PAGERDUTY_ROUTING_KEY`.

No validation call here, unlike the Codemagic token: PagerDuty's Events API v2 has no read
endpoint to probe, and its only write endpoint creates a real incident. The script checks the
key's shape (32 characters) and warns rather than fails if it differs.

This phase is genuinely optional in the sense that the budget monitor degrades gracefully
without it — it still computes and reports usage, and just logs the alerts it would have sent
instead of paging.

## D. Verify

The script prints a summary of all five items at the end of every run. Once they are all
green, smoke-test the monitor without paging anyone:

```sh
gh workflow run codemagic-budget.yml -R wbniv/WorldFoundry -f dry_run=true
gh run list --workflow=codemagic-budget.yml -R wbniv/WorldFoundry --limit 1
```

Cross-check the `used=` minutes figure it prints against the Codemagic dashboard. To exercise
the threshold logic end to end, re-run with `-f override_minutes=1 -f dry_run=true`, which
forces all three thresholds to cross while still never POSTing to PagerDuty.

## Migrating to a new machine

**Prerequisite:** `scripts/creds-dump.sh`, `scripts/creds-commit.sh` and `setup.sh
--import-creds` all source `../../python-tui-lib/scripts/creds-bundle.sh`. On a fresh machine
that will fail with a clear "not found" error until `python-tui-lib` is cloned as a sibling of
this repo: `cd .. && git clone git@github.com:wbniv/python-tui-lib.git`.

**Option A — plain tarball, manual transfer (nothing lands in git history):**

1. Old machine: `task creds-dump` — writes a chmod-600 tarball under `.setup-logs/`.
2. Move it over a trusted channel only (AirDrop, scp, a password manager's secure attachment,
   encrypted USB) — never email, chat, or a public link. It holds live secrets in plaintext.
3. New machine: `task setup -- --import-creds=/path/to/the/tarball`.
4. Delete both copies once the new machine is confirmed working.

**Option B — GPG-encrypted, committed to git (no manual transfer step):**

1. Old machine: `task creds-commit` — writes `secrets/creds-bundle.tar.gpg`, prompting you to
   set a passphrase. Review it, then `git add`/`git commit` yourself; the script never commits.
2. New machine: after `git clone`, `task setup -- --import-creds=secrets/creds-bundle.tar.gpg`
   — gpg prompts for the same passphrase.
3. The tradeoff is real: once committed, the blob's exposure window is "as long as the repo
   exists", not "until a transferred copy is deleted". Pair with periodic AWS key rotation
   regardless of encryption strength.

Neither option exports anything already pushed to SSM or GitHub — only the local AWS profile
and any unfinished session state.
