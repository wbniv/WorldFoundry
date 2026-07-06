# Storing **and streaming** 100 TB of moon maps to players

> Investigation — 2026-06-04. Pricing pulled live from provider pages and 2026
> trackers (see [Sources](#sources)). Figures are list price, USD unless marked €.
> Hetzner is **ex-VAT** (EU +~20%; US/non-EU usually €0 via reverse charge).
>
> **Use case:** the [moon level](../plans/2026-06-04-moon-overhead-map-and-chunk-texture-streaming.md)
> — ~100 TB of high-resolution maps covering the whole Moon, stored online **and
> streamed to game clients on demand**. That second word changes everything below.

## The job changed: this is a content-delivery problem now

"Store 100 TB" is a storage question. "Store **and stream** 100 TB to players" is a
**CDN** question. Once players are pulling tiles, the bill is no longer the 100 TB at
rest — it's the **egress**, and egress scales with players, not with the map. The map
is fixed at 100 TB; the traffic out can be 5 TB/month or 5 PB/month depending on how
many people are flying over the Moon.

So the stack is two layers, and they're priced on opposite axes:

| Layer | What it costs | Scales with |
|-------|---------------|-------------|
| **Origin storage** (the 100 TB at rest) | flat $/TB·month | map size (fixed) |
| **CDN egress** (tiles → players) | $/TB served | player traffic (variable, unbounded) |

The entire decision reduces to: **pick a CDN that doesn't bill egress.** Get that
right and total cost ≈ flat storage cost regardless of player count. Get it wrong
(CloudFront) and a popular launch week can cost more than a year of storage.

## Architecture

```
     GLOBAL PLAYERS                 CDN EDGE  (Cloudflare, ~330 cities)        ORIGIN  (100 TB, one bucket)
                                  ┌────────────────────────────────────┐
 ┌────────┐ GET /moon/z/x/y.tile  │  ┌──────────────────────────────┐  │
 │ player ├─────────────────────► │  │ cache HIT  ~95% → serve here  │──┼──► to player   FREE, not metered
 └────────┘                       │  └──────────────────────────────┘  │
 ┌────────┐                       │  ┌──────────────────────────────┐  │     ┌─────────────────────────────┐
 │ player ├─────────────────────► │  │ cache MISS ~5% → pull origin  │──┼──┐  │  R2   $1.5k/mo   (native)   │
 └────────┘                       │  └──────────────────────────────┘  │  └─►│   — or —                    │
    ⋮                             └────────────────────────────────────┘ free│  B2   $600/mo   (Bandwidth   │
 ┌────────┐                                                              fill │         Alliance → CF)       │
 │ player ├─────────────────────►   tiles are immutable → cache forever       └─────────────────────────────┘
 └────────┘
```

The win is the **cache hit ratio**. Moon tiles are static and content-addressed, so
once an edge has served `/moon/8/137/92.tile` it serves every later request for it
from cache — free, near the player, never touching the origin. Origin egress is only
the ~5% cache-miss fill, and on R2/B2-via-Cloudflare even that is free. So the 100 TB
origin is paid for **once a month at rest**, and the streaming is paid for **never**
(on Cloudflare) or **cheaply** (bunny).

### How the moon data is shaped (why this caches so well)

```
Moon = a quadtree of tiles. The client streams ONLY the tiles in view, at its LOD.

 LOD 0   whole Moon, coarse     1 tile         ▢
 LOD 1                          4 tiles         ▢▢
                                                ▢▢
 LOD 2                          16 tiles        ▢▢▢▢
                                                ▢▢▢▢ …
   ⋮                              ⋮
 LOD k   ≈1 m/pixel        ~billions of tiles   ▢▢▢▢▢▢▢… ◄── the 100 TB lives down here
                                                 └── but only ~dozens are fetched per frame,
                                                     and popular regions (landing sites) stay hot in cache
```

A new HTTP-backed `HALGetAssetAccessor` fetches tiles by `z/x/y` over HTTPS instead of
from `cd.iff`; immutable `Cache-Control` lets the edge hold them forever.

## Layer 1 — origin storage (the 100 TB at rest)

Only the providers that hand off to a CDN for free (or near-free) belong here:

| Origin | Storage / mo (100 TB) | $/TB·mo | Egress **to CDN** | Ops | Type |
|--------|----------------------:|--------:|-------------------|-----|------|
| **Backblaze B2** | **$600** | $6 | **$0** (free to Cloudflare/bunny/Fastly) | low | S3 API |
| **Cloudflare R2** | $1,500 | $15 | **$0** (CDN is same vendor) | lowest | S3 API |
| **Hetzner SX** dedicated | **~$240** | ~$1.3 raw | **$0** (unlimited free traffic) | high | you run nginx origin |
| bunny Edge Storage | ~$1,000–2,000 | $10–20 | $0 (to bunny CDN) | low | integrated w/ bunny CDN |

The struck options from the storage-only study (Wasabi, Storj, AWS S3) don't make the
cut: Wasabi/Storj cap or bill egress *and* aren't CDN-native; S3's only CDN partner is
CloudFront, the most expensive egress on the market.

### Is the Hetzner Storage Box comparable to R2? (folded in from the discussion)

Short answer: **for private bytes-at-rest, yes and it's ~7× cheaper; as a streaming
origin behind a CDN, not really.** On the "do I babysit a machine?" axis the Storage
Box *is* like R2 — Hetzner runs the hardware, you just connect. The real gaps:

| | Cloudflare R2 | Hetzner Storage Box |
|--|---------------|---------------------|
| **API** | S3 object API — apps integrate natively, presigned URLs, billions of objects/bucket | SFTP / SMB / WebDAV / rsync only — **no S3 API, no clean HTTP origin** |
| **Namespace** | one unbounded bucket | fixed plans, **20 TB cap/box** → 100 TB = 5 boxes/mounts |
| **Durability** | geo-distributed, ~11 nines by design | single **box in one datacenter** (internal RAID, no geo-redundancy) |
| **Serving** | sits behind Cloudflare's global edge | one NIC in one EU DC — fine for backup, **not a CDN origin** |
| **Ops** | zero | zero (hardware), but geo-redundancy is *your* problem |

For *this* job (CDN origin for tile streaming) the Storage Box is the wrong shape —
it has no HTTP/S3 origin a CDN can pull from cleanly, and it's single-region. The
Hetzner option that *does* fit is the **SX dedicated server** running nginx: cheapest
storage of all, free egress to the CDN — but now you own the origin box, its disks,
and its replication. That's the "high ops" row above.

## Layer 2 — the CDN (where the money actually goes)

This is the decisive table. Cost to **serve tiles to players**, per TB:

| CDN | Egress to players | Notes |
|-----|------------------:|-------|
| **Cloudflare** (cache in front of R2/B2) | **$0 / TB** | bandwidth not metered; R2 egress is $0 by design; B2→CF free via Bandwidth Alliance |
| **bunny.net** Volume Network | **~$5 / TB** ($0.005/GB, first 500 TB) | cheap, integrated with bunny Storage; not free |
| **bunny.net** Standard Network | $10–60 / TB | $0.01/GB NA/EU … $0.06/GB APAC |
| **AWS CloudFront** | **~$85 / TB** ($0.085/GB, ↓ to ~$20/TB at PB) | S3→CloudFront fill is free, but CF→player is brutal |

### The same picture as a graph — total monthly cost vs. player traffic

```
Egress cost only (per month), log-ish vertical scale
                                                            ╱● S3 + CloudFront
   $160,000 ┤                                          ╱╱╱╱
                                                   ╱╱╱╱
    $33,000 ┤                              ●╱╱╱╱╱
                                      ╱╱╱╱╱
     $4,000 ┤                  ●╱╱╱╱╱                  ○ bunny CDN (Volume)
                          ╱╱╱╱╱            ○────────○
       $425 ┤      ●╱╱╱╱╱        ○────────○
        $25 ┤  ○───●────○────────○
         $0 ┤━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ R2/B2 + Cloudflare  ($0, flat)
            └────┬────────┬─────────┬──────────┬─────────
               5 TB     50 TB    500 TB       5 PB     player egress / month
             (~1k)     (~10k)   (~100k)      (~1M)     players @ ~5 GB each/mo
```

Exact figures (egress only; add the flat storage cost from Layer 1):

| Monthly player egress | Cloudflare (R2/B2) | bunny (Volume) | AWS CloudFront |
|-----------------------|-------------------:|---------------:|---------------:|
| 5 TB   (~1k players)  | **$0** | ~$25     | ~$425     |
| 50 TB  (~10k players) | **$0** | ~$250    | ~$4,000   |
| 500 TB (~100k players)| **$0** | ~$2,500  | ~$33,000  |
| 5 PB   (~1M players)  | **$0** | ~$25,000 | ~$160,000 |

> Player-count estimates assume ~5 GB of tiles streamed per active player per month —
> adjust to taste; the *shape* is what matters. Cloudflare is a flat line at $0; the
> others bend upward with popularity.

## Full stack: what you'd actually pay

Total monthly = flat storage + egress. At a representative **500 TB/mo of streaming**
(≈100k active players):

```
 Hetzner SX  + Cloudflare  │█  ~$240            ◄ cheapest, but you run + replicate the origin
 B2          + Cloudflare  │██  ~$600           ◄ cheapest fully-managed
 R2          + Cloudflare  │████  ~$1,500       ◄ simplest (one vendor, native)
 bunny Stg.  + bunny CDN   │██████████  ~$3,500
 S3          + CloudFront  │██████████████████████████████████  ~$35,000   ◄ avoid
                           └──────────────────────────────────────────────────
                            $0       $5k        $15k                $35k
```

The three Cloudflare-fronted stacks are **flat** across the whole player range above —
$240 / $600 / $1,500 a month whether 10k or 1M people are playing. That flatness, not
the storage sticker, is the prize.

## What to watch for

- **Cloudflare ToS §2.8 — serve large media via R2, not a bare cache.** Cloudflare's
  no-egress-fee CDN isn't licensed to serve unlimited large non-HTML files on a
  generic proxy/Pro plan. **R2 is the explicitly-supported zero-egress path for large
  assets** — use R2 as origin (or R2 public bucket + custom domain) and you're inside
  the supported model. B2→Cloudflare is cheaper storage and also $0 egress, but for
  high-volume game-asset serving the no-questions path is R2.
- **Cache hit ratio is the whole economy.** The $0/$cheap egress assumes ~95% edge
  hits. Immutable, content-addressed tile URLs + long `Cache-Control` are mandatory —
  cache-bust the tiles and you turn every request into an origin pull.
- **Single-region origin = cache-miss latency, not a cost.** R2/B2 are multi-region;
  a Hetzner SX origin is one DC, so the ~5% misses are slower for far-away players. The
  CDN hides it for the 95%; budget a second origin if misses matter.
- **Durability is the provider's job on R2/B2, yours on Hetzner.** A self-hosted SX
  origin needs its own backup/replica (a second SX ~€220/mo) — still cheaper than R2.
- **One-time ingress is ~free.** Uploading the 100 TB once costs only PUT/operation
  fees (R2 Class A $4.50/M, ~$5 total for ~1M objects); data-in is free everywhere.
- **Mid-2026 price drift:** Hetzner +up to 37% on Apr 1 2026 (figures above are post-
  increase); bunny/Cloudflare/B2 stable.

## Bottom line for the moon level

- **Recommended default → R2 + Cloudflare CDN.** ~$1,500/mo, **flat**, $0 egress at any
  player count, S3 API, one vendor, the ToS-clean path for serving large game assets.
  The `HALGetAssetAccessor` HTTP backend points at an R2 public bucket on a custom
  domain; tiles cache at the edge forever.
- **Cheaper, still fully managed → B2 + Cloudflare CDN.** ~$600/mo, also $0 egress
  (Bandwidth Alliance). Save $900/mo vs R2 for one extra integration seam (B2 as
  origin, Cloudflare cache rules). Worth it if storage cost dominates.
- **Cheapest if you'll run a box → Hetzner SX135 + Cloudflare/bunny.** ~$240/mo, free
  egress, but you own the origin, its disks, replication, and a backup. Best when ops
  capacity exists and budget is the constraint.
- **Do not** stream from S3 + CloudFront: storage ~$2,250/mo *and* egress that turns a
  popular week into a five-figure bill. The exact stack to avoid for player-facing data.

## Sources

- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) · [R2 zero-egress](https://www.cloudflare.com/products/r2/) · [Cloudflare zero-egress strategy](https://egresscost.com/cloudflare/)
- [Backblaze B2 pricing](https://www.backblaze.com/cloud-storage/pricing) · [B2 free egress to CDN partners](https://leanopstech.com/blog/backblaze-b2-pricing-2026/)
- [bunny.net CDN pricing](https://bunny.net/pricing/) · [bunny Storage pricing](https://bunny.net/pricing/storage/)
- [AWS CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/) · [CloudFront per-GB 2026](https://blog.blazingcdn.com/en-us/aws-cloudfront-pricing-2026-per-gb-cost-and-regional-breakdown)
- [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Hetzner SX storage servers](https://www.hetzner.com/dedicated-rootserver/matrix-sx/) · [SX65 €109/mo](https://looking.house/companies/hetzner-com/dedicated-servers/sx65) · [Storage Box](https://www.hetzner.com/storage/storage-box/) · [Hetzner Apr 2026 price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
- [Wasabi pricing](https://wasabi.com/pricing) · [Storj pricing](https://www.storj.io/pricing) — *(both excluded: egress caps/fees, not CDN-native)*
- [100 TB storage price comparison](https://leanopstech.com/blog/cloud-storage-pricing-comparison-2026/)
