#!/usr/bin/env python3
"""
generate_events.py — Generate a Postman Collection v2.1 of WF REST box events.

Output is a valid Postman Collection that can be imported into Postman directly.
Timing between requests is encoded in each item's `description` field as:
    x-playback-t: <seconds>
    x-playback-ref: <label>

playback.py reads these tags; Postman ignores them.

Usage:
    python3 generate_events.py [options]

Options:
    --count N        Total events to generate (default: 30)
    --seed S         RNG seed for reproducible output (default: random)
    --max-live N     Max boxes alive at once; forces a delete when exceeded (default: 8)
    --size-min F     Minimum box dimension in metres (default: 0.5)
    --size-max F     Maximum box dimension in metres (default: 5.0)
    --world-size F   Half-extent of world cube for random positions (default: 10.0)
    --interval F     Mean seconds between events (default: 1.5)
    --out FILE       Output path (default: events.json)
    --host HOST      Postman collection variable wf_host (default: localhost)
    --port N         Postman collection variable wf_port (default: 8765)
"""

import argparse
import json
import math
import random
import sys
import time
import uuid

PALETTE = [
    "#e05050",  # red
    "#5080e0",  # blue
    "#50e080",  # green
    "#e0c040",  # yellow
    "#e080c0",  # pink
    "#40c0e0",  # cyan
    "#e09040",  # orange
    "#9050e0",  # purple
    "#ffffff",  # white
]


def rand_box(rng, args):
    """Return a dict of box creation parameters."""
    cx, cy, cz = args.near_player
    return {
        "x": round(rng.uniform(cx - args.world_size, cx + args.world_size), 3),
        "y": round(rng.uniform(cy, cy + args.world_size), 3),
        "z": round(rng.uniform(cz - args.world_size, cz + args.world_size), 3),
        "l": round(rng.uniform(args.size_min, args.size_max), 3),
        "w": round(rng.uniform(args.size_min, args.size_max), 3),
        "h": round(rng.uniform(args.size_min, args.size_max), 3),
        "color": rng.choice(PALETTE),
    }


def make_item(name, method, url_path, body, t, ref, host_var, port_var):
    """Build a Postman Collection v2.1 item."""
    url_raw = f"http://{{{{{host_var}}}}}:{{{{{port_var}}}}}{url_path}"

    # Split path into segments for Postman's URL object.
    segments = [s for s in url_path.split("/") if s]

    item = {
        "name": name,
        "description": f"x-playback-t: {t:.3f}\nx-playback-ref: {ref}",
        "request": {
            "method": method,
            "header": [],
            "url": {
                "raw": url_raw,
                "protocol": "http",
                "host": [f"{{{{{host_var}}}}}"],
                "port": f"{{{{{port_var}}}}}",
                "path": segments,
            },
        },
    }

    if body is not None:
        item["request"]["header"].append(
            {"key": "Content-Type", "value": "application/json"}
        )
        item["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, separators=(",", ":")),
            "options": {"raw": {"language": "json"}},
        }

    return item


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--count",      type=int,   default=30,         help="Total events")
    p.add_argument("--seed",       type=int,   default=None,       help="RNG seed")
    p.add_argument("--max-live",   type=int,   default=8,          help="Max live boxes")
    p.add_argument("--size-min",   type=float, default=0.5,        help="Min dimension (m)")
    p.add_argument("--size-max",   type=float, default=5.0,        help="Max dimension (m)")
    p.add_argument("--world-size",  type=float, default=10.0,       help="World half-extent (m)")
    p.add_argument("--near-player", type=str,   default="0,0,0",
                   help="Centre of generation volume as x,y,z (default: 0,0,0)")
    p.add_argument("--interval",   type=float, default=1.5,        help="Mean seconds between events")
    p.add_argument("--out",        type=str,   default="events.json", help="Output file")
    p.add_argument("--host",       type=str,   default="localhost", help="REST API host")
    p.add_argument("--port",       type=int,   default=8765,        help="REST API port")
    args = p.parse_args()
    try:
        args.near_player = tuple(float(v) for v in args.near_player.split(","))
        if len(args.near_player) != 3:
            raise ValueError
    except ValueError:
        p.error("--near-player must be x,y,z (e.g. 1.5,0,-3.2)")

    rng = random.Random(args.seed)
    seed_used = args.seed if args.seed is not None else "(random)"
    print(f"Seed: {seed_used}", file=sys.stderr)

    # Track live boxes as {ref_label: box_params}
    live = {}   # ref → creation params
    counter = 0
    items = []
    t = 0.0

    ops_available = ["create", "delete", "recolor", "resize"]
    op_weights    = [0.50,     0.25,     0.15,       0.10]

    for _ in range(args.count):
        # Force a delete when at capacity; force a create when empty.
        if len(live) >= args.max_live:
            op = "delete"
        elif not live:
            op = "create"
        else:
            op = rng.choices(ops_available, weights=op_weights, k=1)[0]

        if op == "create":
            counter += 1
            ref = f"box_{counter:02d}"
            params = rand_box(rng, args)
            url_path = "/boxes"
            item = make_item(
                f"Create {ref} ({params['l']}×{params['w']}×{params['h']}m {params['color']})",
                "POST", url_path, params, t, ref,
                "wf_host", "wf_port",
            )
            live[ref] = params

        elif op == "delete":
            ref = rng.choice(list(live.keys()))
            url_path = f"/boxes/{{{{{ref}}}}}"
            item = make_item(
                f"Delete {ref}",
                "DELETE", url_path, None, t, ref,
                "wf_host", "wf_port",
            )
            del live[ref]

        elif op == "recolor":
            ref = rng.choice(list(live.keys()))
            color = rng.choice(PALETTE)
            url_path = f"/boxes/{{{{{ref}}}}}/color"
            item = make_item(
                f"Recolor {ref} → {color}",
                "PATCH", url_path, {"color": color}, t, ref,
                "wf_host", "wf_port",
            )

        elif op == "resize":
            ref = rng.choice(list(live.keys()))
            # Change one or two of l/w/h
            axes = rng.sample(["l", "w", "h"], k=rng.randint(1, 3))
            body = {ax: round(rng.uniform(args.size_min, args.size_max), 3) for ax in axes}
            url_path = f"/boxes/{{{{{ref}}}}}/size"
            desc = " ".join(f"{k}={v}" for k, v in body.items())
            item = make_item(
                f"Resize {ref} ({desc})",
                "PATCH", url_path, body, t, ref,
                "wf_host", "wf_port",
            )

        items.append(item)

        # Advance time with slight jitter (exponential gap ≈ Poisson process)
        t += rng.expovariate(1.0 / args.interval)

    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "WF Box Demo",
            "description": (
                f"Generated by generate_events.py. "
                f"Seed: {seed_used}. "
                f"{args.count} events over ~{t:.1f}s."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [
            {"key": "wf_host", "value": args.host, "type": "string"},
            {"key": "wf_port", "value": str(args.port), "type": "string"},
        ],
    }

    with open(args.out, "w") as f:
        json.dump(collection, f, indent=2)

    print(f"Wrote {len(items)} events → {args.out}  (~{t:.1f}s at 1× speed)", file=sys.stderr)


if __name__ == "__main__":
    main()
