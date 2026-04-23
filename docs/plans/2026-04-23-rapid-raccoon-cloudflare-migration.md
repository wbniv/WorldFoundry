# Plan: `rapid-raccoon.com` onto Cloudflare + Party Games named tunnel + corporate site scaffold

**Date:** 2026-04-23
**Status:** Not started (DNS migration is the prerequisite for everything else).
**Scope:** Migrate `rapid-raccoon.com` DNS from AWS Route 53 → Cloudflare, stand up `www.rapid-raccoon.com` as a small Astro-powered corporate site on Cloudflare Pages, and stand up a named Cloudflare Tunnel at `pg.rapid-raccoon.com` so the Party Games Cast Console URL stops being a quick-tunnel moving target.

## Context

Today (2026-04-23) we've been running Party Games development behind ephemeral `trycloudflare.com` quick tunnels (`https://<random>.trycloudflare.com`). Each server restart or tunnel-process restart rotates the URL, which forces edits to the Cast Console receiver URL and may restart the (unverified-but-cautious) Cast propagation clock.

Separately, `rapid-raccoon.com` is a fresh domain — registered at Dreamhost, DNS at AWS Route 53, apex has no A record, nothing's actively hosted on it. It's intended as a small corporate site for occasional product-launch posts (cadence ~weekly).

Bundling both into one plan because the DNS migration is the enabling prerequisite: once `rapid-raccoon.com` is on Cloudflare, we can stand up a named tunnel on a `pg.` subdomain AND host the corporate site on Cloudflare Pages from the same dashboard, with one TLS story and one DNS panel to worry about.

## Target shape

After this plan lands:

| URL | Destination | Purpose |
|-----|-------------|---------|
| `rapid-raccoon.com` | 301 redirect → `www.rapid-raccoon.com` | Apex canonicalisation |
| `www.rapid-raccoon.com` | Cloudflare Pages (Astro build) | Corporate landing + product-launch posts |
| `pg.rapid-raccoon.com` | Named Cloudflare Tunnel → `http://localhost:8080` | Party Games receiver + controller |

DNS + hosting + tunnel all in Cloudflare. Dreamhost continues to own the registration (where the WHOIS record + renewal billing lives); AWS Route 53 drops out of the loop entirely once NS propagation completes.

## Execution order

Matters because Cast Console gets re-pointed at the new named tunnel URL at the end, and we want that URL to be stable before we touch it (Cast Console edits may restart their propagation clock — unverified but cautious):

1. **Cloudflare DNS migration** — add zone, get NS, flip at Dreamhost, wait for propagation.
2. **Corporate site skeleton on Cloudflare Pages** — scaffold `rapid-raccoon-site` repo, wire to Pages, verify `www.rapid-raccoon.com` serves.
3. **Named Cloudflare Tunnel** — `cloudflared tunnel create/route/config/run` for `pg.rapid-raccoon.com`.
4. **Cast Console receiver URL update** — point the 071CDEDD app at `https://pg.rapid-raccoon.com/receiver`. Last time that field gets touched.
5. **Route 53 cleanup** — delete the now-orphaned hosted zone (saves ~$0.50/mo).

Steps 2 and 3 are independent after step 1 completes; can be done in either order or in parallel.

## Step 1 — DNS migration (Dreamhost NS → Cloudflare NS)

**Pre-state** (verified 2026-04-23):
- `dig +short NS rapid-raccoon.com` returns the four `ns-*.awsdns-*` names (Route 53).
- `dig +short A rapid-raccoon.com` returns empty (apex unused).

**Actions:**

1. Log into [dash.cloudflare.com](https://dash.cloudflare.com) → Add a Site → `rapid-raccoon.com` → Free plan.
2. Cloudflare scans Route 53 records (likely finds nothing substantial). Accept whatever it imports — we can tweak after.
3. Cloudflare assigns a pair of nameservers (e.g. `ada.ns.cloudflare.com` + `xander.ns.cloudflare.com`). Copy them.
4. Log into Dreamhost → Manage Domains → `rapid-raccoon.com` → set nameservers to the Cloudflare pair, remove the AWS ones.
5. Propagation: check `dig +short NS rapid-raccoon.com` every 15 minutes until the output flips to the Cloudflare pair. Usually 10 minutes to a few hours.
6. Cloudflare dashboard should flip the zone to "Active" once propagation is detected on their end.

**Rollback:** revert nameservers at Dreamhost to the four `ns-*.awsdns-*` ones. Nothing destructive happens in this step; the Route 53 zone data is still there untouched.

**Verification after step 1:**
- `dig +short NS rapid-raccoon.com` → Cloudflare pair.
- Cloudflare dashboard → zone status "Active".
- Nothing serving on `www` or apex yet; that's expected.

## Step 2 — Corporate site skeleton (Astro + Cloudflare Pages)

**Decision: Astro** (not plain HTML). Reasoning:
- First-class markdown + content collections fit the "weekly product-launch post" cadence.
- Already familiar from `~/SRC/finding-your-way/` (Astro 5, pnpm, Playwright).
- Zero-JS-to-user output — same end-user bundle size as plain HTML, just with a build step we're already used to.

**Trade-off noted:** Astro has 6-12-month-cadence breaking major upgrades. Accept that as maintenance cost. If the corporate site grows beyond 30 pages or the launch-post cadence stops, plain HTML could be revisited — but I don't expect to hit that.

**Actions:**

1. **New repo**: `~/SRC/rapid-raccoon-site/` (separate from this repo). Initialise with `git init`, `gh repo create wbniv/rapid-raccoon-site --public --source=.` (or private — your call).
2. **Scaffold** (default is a fresh `pnpm create astro@latest`; fork from `finding-your-way` if you want that toolbelt pre-wired — pick when we get here):
   ```sh
   cd ~/SRC
   pnpm create astro@latest rapid-raccoon-site
   #   template: "Empty"   (or "Basics" for a very minimal landing)
   #   TypeScript: Strict
   #   install deps: yes
   #   initialise git: no (we already init'd)
   cd rapid-raccoon-site
   pnpm run dev   # http://localhost:4321
   ```
3. **Initial structure**:
   ```
   rapid-raccoon-site/
     astro.config.mjs
     package.json
     public/
       favicon.svg
     src/
       layouts/
         Base.astro           — shared header + footer, used by every page
       pages/
         index.astro          — landing page (hand-written HTML inside <Base>)
         products/
           index.astro        — lists all product-launch posts from the content collection
           [slug].astro       — per-launch page rendering a markdown file
       content/
         config.ts            — defines the "products" collection schema
         products/
           2026-04-23-example-launch.md   — first post to prove the pipeline works
     README.md
   ```
   The whole site's ~5 files + 1 markdown template. Growing the site = drop new `.md` files into `src/content/products/`.
4. **Cloudflare Pages wiring**:
   - dash.cloudflare.com → Pages → Create → Connect to Git → pick `wbniv/rapid-raccoon-site`.
   - Build command: `pnpm run build`.
   - Build output: `dist`.
   - Node version: 22 (matches `finding-your-way`).
   - Deploy. Cloudflare Pages auto-deploys every push to `main`.
5. **Custom domain wiring**:
   - Pages project → Custom domains → Add custom domain → `www.rapid-raccoon.com`. Cloudflare creates the CNAME automatically since the zone is on Cloudflare.
   - Also add the apex `rapid-raccoon.com` and configure it to redirect to `www` via a Page Rule (free plan gets 3 rules, plenty):
     - Target: `rapid-raccoon.com/*`
     - Action: Forwarding URL → 301 → `https://www.rapid-raccoon.com/$1`
6. **TLS** — automatic via Cloudflare's Universal SSL. No certbot.

**Rollback:** Pages project can be deleted from the Cloudflare dashboard; custom domains can be detached. DNS records Cloudflare auto-created for Pages can be removed. Low-risk — there's nothing production-critical on the domain yet.

**Verification after step 2:**
- `https://www.rapid-raccoon.com` loads the Astro site.
- `https://rapid-raccoon.com` 301s to `https://www.rapid-raccoon.com`.
- New markdown post pushed to `main` → appears at `/products/<slug>` within ~1 min of build completing.

**Revisit trigger:** if the corporate site outgrows Astro (unlikely) or weekly launches become a CMS-editor workflow (more likely if non-dev contributors join), reconsider — probably a markdown-driven Astro site plus a small admin UI, not a rewrite.

## Step 3 — Named Cloudflare Tunnel (`pg.rapid-raccoon.com`)

**Actions:**

```sh
cloudflared tunnel login
# Browser auth → pick rapid-raccoon.com zone.
# Drops a cert.pem into ~/.cloudflared/

cloudflared tunnel create party-games
# Prints a UUID + writes ~/.cloudflared/<uuid>.json credentials file.
# Note the UUID.

cloudflared tunnel route dns party-games pg.rapid-raccoon.com
# Creates a CNAME in Cloudflare DNS: pg → <uuid>.cfargotunnel.com
```

**Config file** (`~/.cloudflared/config.yml`):
```yaml
tunnel: party-games
credentials-file: /home/will/.cloudflared/<uuid>.json
ingress:
  - hostname: pg.rapid-raccoon.com
    service: http://localhost:8080
  - service: http_status:404
```

**Run** (dev-hand mode): `cloudflared tunnel run party-games`.

**Run** (always-on, preferred): install as systemd unit —
```sh
sudo cloudflared service install
# Registers /etc/systemd/system/cloudflared.service reading from /etc/cloudflared/config.yml.
# You'll want to copy the config.yml + credentials into /etc/cloudflared/ for the root-run service, OR keep it user-level by writing a ~/.config/systemd/user/cloudflared.service unit.
```

**Verification after step 3:**
- `curl -s -o /dev/null -w "%{http_code}\n" https://pg.rapid-raccoon.com/receiver` → 200 (with the Party Games server running locally on :8080).
- `curl -s --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" https://pg.rapid-raccoon.com/ws | head -1` → `HTTP/1.1 101 Switching Protocols`.
- Quick-tunnel processes (`cloudflared tunnel --url http://localhost:8080`) can be killed — we don't need them any more.

**Rollback:** `cloudflared tunnel delete party-games` removes the tunnel; the `pg` CNAME can stay harmlessly (points at a dead tunnel) or be deleted manually from the Cloudflare DNS panel. Previous `trycloudflare.com` quick tunnels are always available as a fallback.

## Step 4 — Cast Console receiver URL update

- [cast.google.com/publish](https://cast.google.com/publish) → Applications → `071CDEDD` → Receiver Details.
- Change URL from the current `helped-enjoy-calm-renewable.trycloudflare.com/receiver` to `https://pg.rapid-raccoon.com/receiver`.
- Save.
- This may or may not restart the Cast Console propagation clock (we've been cautious about this all day without actually testing) — but since the receiver content at the new URL is identical, if the app was previously visible to test devices, it should remain visible. If the propagation clock DOES restart: 48 h to re-propagate, Phase 1d re-delayed.

**Verification:** reload the controller URL at `https://pg.rapid-raccoon.com/controller?name=Will` on laptop Chrome; `cast-state` should still flip correctly. Cast launch on TV still works (or still waits for propagation, depending on timing).

## Step 5 — Route 53 cleanup (after verification of steps 1-4)

- AWS Console → Route 53 → Hosted zones → `rapid-raccoon.com` → Delete.
- Saves ~$0.50/month.
- Only do this after confirming Cloudflare DNS is resolving everything correctly — the old Route 53 zone is useful as a rollback target until you're confident.

## Follow-up / revisit triggers

- **Astro major-version upgrades** appear every 6-12 months with breaking changes. Pin, update on a rhythm, don't let it get two majors behind.
- **Corporate site page count crossing ~30** without a blog-style workflow — reconsider content-collection structure or CMS options.
- **AWS reconsideration** — if the corporate site grows into something with dynamic behaviour (API, auth, database), Cloudflare Workers + KV + D1 is the in-ecosystem answer; a shift to AWS is overkill unless specific AWS features are wanted.
- **Party Games Phase 4 hosting** — when the game moves off a laptop and into a real server, the named tunnel here becomes either (a) a tunnel to an always-on VM elsewhere, or (b) replaced with direct HTTPS against a public host. This plan's `pg.rapid-raccoon.com` URL stays stable in either case.
- **Corporate site visitor analytics** — if you want them, Cloudflare Pages has built-in Web Analytics (free, privacy-respecting, no cookies).
