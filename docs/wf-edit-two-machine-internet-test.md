# Two editor instances over the internet — run sheet

**Goal:** verify the things headless tests *can't* — two real `wf-edit` instances
on **two machines**, joined across the public internet, editing the same level
live. This is the cross-machine confirmation of the relay-connect work
([critique](investigations/2026-06-01-resilient-retry-plan-critique.md) →
[remediation plan](plans/2026-06-01-implement-the-relay-connect-critique-s-recommendat.md)):

1. **Connect over a stable named tunnel** — no `530` warm-up race, no ephemeral
   hostname (the reason the quick tunnel wasn't good enough for real use).
2. **Live edit sync** — a gizmo drag / field edit on one editor lands on the other.
3. **Mid-session reconnect** — kill the relay/tunnel, both go 🔴, restart, both
   auto-🟢 and edits resume (the headless version is
   [`tests/smoke_relay_reconnect.sh`](../tests/smoke_relay_reconnect.sh)).
4. **Fail-fast + closeable connect** — a bad link fails quickly and the window
   stays closeable (no "Not Responding" freeze).

This complements the headless guards (`wf_edit_connect_retry`,
`wf_edit_connect_abort`, the reconnect smoke); it does not replace them.

---

## Prerequisites

| Machine | Needs |
|---------|-------|
| **Host** (computer 1) | `wf-edit` built (`task build-wf-edit-fast`); `wf-relay` built; `cloudflared` in `PATH` (or `task fetch-cloudflared`); a Cloudflare **named tunnel** set up once (below) |
| **Joiner** (computer 2) | `wf-edit` built — **nothing else** (no cloudflared, no relay, no account) |
| Both | the non-ASan binary (`build-editor-fast/wf-edit`) — ASan ~2–3×'s RSS and two editors + a browser won't fit; see [`task build-wf-edit-fast`](../Taskfile.yml) |

Build on each machine:

```bash
git pull origin 2026-new-level
task build-wf-edit-fast
# host only — --host-tunnel needs the relay binary present:
cargo build --release --bin wf-relay --manifest-path wftools/wf_collab/Cargo.toml
```

---

## One-time tunnel setup (host only) — the login model, no secret to keep

Use Cloudflare's `tunnel login`, **not** a dashboard connector token: `cloudflared`
owns a `0600` credential under `~/.cloudflared/` (a one-time browser auth), so
there is nothing to paste, store, or safeguard. Full detail + the dashboard
alternative: [manual → Named tunnel](wf-edit-manual.md#named-tunnel--durable-rate-limit-free-stable-hostname).

```bash
cloudflared tunnel login                                  # browser → ~/.cloudflared/cert.pem (0600)
cloudflared tunnel create wf-host                         # → ~/.cloudflared/<UUID>.json (the run credential)
cloudflared tunnel route dns wf-host wf.<your-domain>     # CNAME → the tunnel
```

> The run credential is the per-tunnel `<UUID>.json`. To host from a *different*
> machine than the one you ran `create` on, copy `~/.cloudflared/cert.pem` and
> `~/.cloudflared/<UUID>.json` there — those two files are the credential.

---

## Run it

### 1. Host (computer 1)

Tell `wf-edit` the tunnel **name + hostname** (no secret). Env is easiest for a
one-off; or put `tunnel_name` / `tunnel_hostname` in `~/.config/wf-edit/identity.json`.

```bash
export WF_COLLAB_TUNNEL_NAME=wf-host          # the name from `tunnel create` (the UUID also works)
export WF_COLLAB_TUNNEL_HOSTNAME=wf.<your-domain>
task named-tunnel ROOM=test1
```

Confirm in the host's stderr — this is the proof the named path engaged:

```
wf-edit: starting named tunnel for room 'test1'…
wf-edit: using named tunnel — hostname wf.<your-domain> (login cred, rate-limit-free)
wf-edit: relay connected ws://127.0.0.1:9900 room=test1 (peer …)     ← loopback self-join (Fix 1)
   share link →  wfedit+s://wf.<your-domain>/r/test1
```

No `Establishing` / `530` warm-up phase, and the hostname is stable across
sessions — that's the named tunnel's whole reason for being. Copy the share link.

### 2. Joiner (computer 2)

```bash
task join URL='wfedit+s://wf.<your-domain>/r/test1'
```

The joiner needs no cloudflared and no account — it just dials the public
`wss://` host. Its stderr should print `relay connected wss://wf.<your-domain> …`.

---

## What to verify

| # | Check | How |
|---|-------|-----|
| 1 | **Both connected** | Each editor's Collaborators panel shows 🟢 and lists the other peer |
| 2 | **Live edit sync** | Drag the move/rotate gizmo (or change a field) on one → it moves on the other within a frame or two |
| 3 | **Mid-session reconnect** | On the host, **Ctrl-C** the editor's tunnel (or `kill` cloudflared / wf-relay), watch both go 🔴; relaunch the host → both return 🟢 and a fresh edit syncs again. Host log shows `relay dropped — reconnecting` → `relay reconnected, re-joined` |
| 4 | **Fail-fast + closeable** | On a third launch, paste a bad link (e.g. `--url=wfedit+s://nope.invalid/r/x`) → it gives up quickly (NXDOMAIN fails fast; a refusing-but-resolvable host retries ≤15 s), and the window's **X closes immediately** at any point — no freeze |

Capture both editors' stderr and a screenshot of the two 🟢 panels as the proof.

---

## Troubleshooting

- **`cloudflared` errors on missing `cert.pem` / credentials** → you're hosting
  from a machine that never ran `tunnel login`/`create`. Run them there, or copy
  `~/.cloudflared/{cert.pem,<UUID>.json}` over (see the setup note above).
- **Tunnel up but the hostname 404s** → ingress. wf-edit passes
  `--url http://localhost:9900` so a separate `~/.cloudflared/config.yml` is *not*
  needed; if you wrote one, make sure its ingress routes the hostname to
  `http://localhost:9900` (the `wf-relay` port, `kRelayPort`).
- **Joiner connects but sees no peer / no edits** → confirm both used the **same**
  `--room`. Distinct `~/.config/wf-edit/identity.json` per machine gives distinct
  `peer_id`s (auto on first run); same config dir = they look like one peer.
- **Editor `Killed` mid-startup** → ASan build OOM. Use `build-editor-fast/wf-edit`
  (non-ASan), not `build-editor/wf-edit`.
- **Quick-tunnel fallback** (no account / throwaway session): drop the
  `WF_COLLAB_TUNNEL_*` env and run `./build-editor-fast/wf-edit --host-tunnel` —
  you get an ephemeral `*.trycloudflare.com` link instead. Rate-limited and the
  host changes every session, which is exactly why the named tunnel exists.
  Details: [manual → Host a call (quick tunnel)](wf-edit-manual.md#host-a-call-quick-tunnel--zero-config-share-a-link).
