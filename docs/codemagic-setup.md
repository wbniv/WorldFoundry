# Codemagic Setup (iOS CI)

One-time setup to make `git push 2026-ios` automatically trigger an iOS
Simulator build on Codemagic's cloud Mac mini. Skip if you already see Codemagic
builds firing on push.

**Scope:** this wires up automatic-on-push builds. The build workflow itself is
in [`codemagic.yaml`](../codemagic.yaml) at the repo root; the phase plan is in
[`docs/plans/2026-04-21-ios-port-codemagic.md`](plans/2026-04-21-ios-port-codemagic.md).

## Prerequisites

- A Codemagic account (individual plan covers 500 Mac-min/month — enough for
  20–30 clean builds).
- Admin access to the GitHub repo (to install apps + manage webhooks).
- The `gh` CLI authenticated against the repo owner's GitHub account.

## Step 1 — Create the Codemagic project

In the Codemagic dashboard, add `wbniv/WorldFoundry` as a new app. During that
flow Codemagic will ask how to connect to the repo; pick whatever Codemagic
offers (SSH deploy key is the common default). At this point the project exists
on Codemagic but **nothing will trigger builds automatically** — that's what
the webhook step below fixes.

## Step 2 — Install the Codemagic GitHub App

Visit https://github.com/apps/codemagic-ci-cd and install on the repo owner's
account. On the permissions page choose **Only select repositories** and pick
`wbniv/WorldFoundry`. Do not grant "all repositories".

> **Note.** Installing the GitHub App alone does **not** create a classic repo
> webhook. The app is how Codemagic *authenticates* to the repo; it has its
> own event channel but a Codemagic project created against an SSH/URL
> connection (Step 1) won't automatically start receiving push events from the
> app. Step 3 is the glue.

## Step 3 — Wire the webhook

Codemagic exposes a per-project webhook URL. Go to the Codemagic project's
Webhooks tab:

```
https://codemagic.io/app/<APP_ID>/settings
```

Copy the payload URL — it looks like
`https://api.codemagic.io/hooks/<APP_ID>`. Then register it on GitHub:

```bash
gh api -X POST repos/wbniv/WorldFoundry/hooks \
  -f name=web \
  -F config[url]=https://api.codemagic.io/hooks/<APP_ID> \
  -F config[content_type]=json \
  -F config[insecure_ssl]=0 \
  -F events[]=push \
  -F events[]=pull_request \
  -F active=true
```

GitHub sends an automatic `ping` event on creation. Confirm Codemagic accepted
it:

```bash
HOOK_ID=$(gh api repos/wbniv/WorldFoundry/hooks --jq '.[] | select(.config.url | contains("codemagic.io")) | .id')
gh api repos/wbniv/WorldFoundry/hooks/$HOOK_ID --jq .last_response
# Expected: {"code":202,"status":"active","message":"OK"}
```

HTTP 202 means Codemagic received the event and queued it. The Codemagic
project's **Webhooks → Recent deliveries** page will now show the ping.

## Step 4 — Smoke-test with a push

Push any no-op commit to `2026-ios`:

```bash
git commit --allow-empty -m "chore: webhook smoke test"
git push
```

In the Codemagic dashboard you should see a new build start within ~10s. If
not:

- Check `gh api repos/wbniv/WorldFoundry/hooks/$HOOK_ID/deliveries` — the push
  delivery should be listed with `200` or `202` status.
- Check the `triggering` block in `codemagic.yaml` matches the branch you
  pushed to.
- Check the Codemagic project's Webhooks page for the delivery and any error
  messages.

## Historical notes

- Before 2026-04-22, Codemagic builds were started manually from the dashboard
  for ~2 weeks because the GitHub-side webhook was simply missing — the
  project had been connected via SSH-URL, which doesn't auto-install a
  webhook. See commit `<webhook-setup-commit>` (updates to this doc) and the
  diagnosis thread in that session.
- CircleCI has a separate webhook on this repo from 2017 — don't remove it
  when auditing `gh api .../hooks` output; it's harmless.
