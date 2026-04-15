#!/usr/bin/env python3
"""
playback.py — Replay a Postman Collection v2.1 against the WF REST API.

Reads timing from each item's description field (x-playback-t / x-playback-ref tags).
Substitutes {{ref_name}} placeholders in URLs with server-assigned IDs as POSTs respond.

Usage:
    python3 playback.py [options]

Options:
    --file FILE      Postman collection to replay (default: events.json)
    --speed F        Playback speed multiplier (default: 1.0)
                     2.0 = twice as fast; 0.5 = half speed; 0 = instant (no delays)
    --host HOST      Override REST API host (default: from collection variable wf_host)
    --port N         Override REST API port (default: from collection variable wf_port)
    --loop           Repeat the sequence indefinitely; sends DELETE for all live boxes
                     between loops (Ctrl-C to stop)
    --dry-run        Print requests without sending them

Requirements: pip install requests
"""

import argparse
import json
import re
import sys
import time

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Postman collection parsing helpers

def collection_var(collection, key):
    """Extract a collection-level variable by key."""
    for v in collection.get("variable", []):
        if v.get("key") == key:
            return v.get("value", "")
    return ""


def parse_description(desc):
    """Parse x-playback-t and x-playback-ref from an item description."""
    t = None
    ref = None
    for line in (desc or "").splitlines():
        m = re.match(r"x-playback-t:\s*([0-9.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.match(r"x-playback-ref:\s*(\S+)", line)
        if m:
            ref = m.group(1)
    return t, ref


def substitute_vars(text, live_ids, col_vars):
    """Replace {{key}} with live_ids[key] if present, else col_vars[key]."""
    def replacer(m):
        key = m.group(1)
        if key in live_ids:
            return live_ids[key]
        if key in col_vars:
            return col_vars[key]
        return m.group(0)  # leave unknown vars as-is

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


# ---------------------------------------------------------------------------

def run_once(items, col_vars, args, live_ids):
    """
    Replay the item list once. `live_ids` is modified in-place (ref → server id).
    Returns the set of live refs at the end of the sequence (for loop cleanup).
    """
    session = requests.Session()

    prev_t = 0.0
    for i, item in enumerate(items):
        t, ref = parse_description(item.get("description", ""))
        if t is None:
            t = prev_t  # no timing tag → fire immediately after previous

        # Sleep for the gap between this event and the previous one.
        gap = t - prev_t
        if gap > 0 and args.speed > 0:
            time.sleep(gap / args.speed)
        prev_t = t

        req = item.get("request", {})
        method = req.get("method", "GET").upper()
        url_raw = req.get("url", {}).get("raw", "")

        # Apply CLI host/port overrides, then substitute live IDs and col vars.
        effective_vars = dict(col_vars)
        if args.host:
            effective_vars["wf_host"] = args.host
        if args.port:
            effective_vars["wf_port"] = str(args.port)

        url = substitute_vars(url_raw, live_ids, effective_vars)

        # Resolve body
        body_obj = req.get("body", {})
        body_str = body_obj.get("raw", "") if body_obj else ""
        if body_str:
            body_str = substitute_vars(body_str, live_ids, effective_vars)

        headers = {"Content-Type": "application/json"} if body_str else {}

        label = item.get("name", f"item {i}")
        print(f"[{t:7.3f}s] {method:6s} {url}")

        if args.dry_run:
            if body_str:
                print(f"         body: {body_str}")
            continue

        try:
            resp = session.request(
                method, url,
                data=body_str.encode() if body_str else None,
                headers=headers,
                timeout=10,
            )
        except requests.RequestException as e:
            print(f"         ERROR: {e}", file=sys.stderr)
            continue

        status = resp.status_code
        body_out = resp.text.strip()[:120]  # truncate long responses in log
        print(f"         → {status}  {body_out}")

        # Track server-assigned IDs for create operations.
        if method == "POST" and status == 201 and ref:
            try:
                data = resp.json()
                server_id = data.get("id", "")
                if server_id:
                    live_ids[ref] = server_id
                    print(f"         id  {ref} → {server_id}")
            except ValueError:
                pass

        # Remove from live tracking on delete.
        if method == "DELETE" and status == 204 and ref and ref in live_ids:
            del live_ids[ref]

    return set(live_ids.keys())


def cleanup_live(live_ids, col_vars, args):
    """DELETE all remaining live boxes (used between loop iterations)."""
    if not live_ids:
        return
    effective_host = args.host or col_vars.get("wf_host", "localhost")
    effective_port = args.port or col_vars.get("wf_port", "8765")
    base = f"http://{effective_host}:{effective_port}"
    session = requests.Session()
    for ref, sid in list(live_ids.items()):
        url = f"{base}/boxes/{sid}"
        print(f"[cleanup] DELETE {url}")
        if not args.dry_run:
            try:
                session.delete(url, timeout=5)
            except requests.RequestException as e:
                print(f"          ERROR: {e}", file=sys.stderr)
    live_ids.clear()


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--file",    default="events.json", help="Postman collection file")
    p.add_argument("--speed",   type=float, default=1.0, help="Playback speed multiplier (0 = instant)")
    p.add_argument("--host",    default="",   help="Override REST API host")
    p.add_argument("--port",    default="",   help="Override REST API port")
    p.add_argument("--loop",    action="store_true",  help="Loop indefinitely")
    p.add_argument("--dry-run", action="store_true",  help="Print without sending")
    args = p.parse_args()

    with open(args.file) as f:
        collection = json.load(f)

    items = collection.get("item", [])
    col_vars = {v["key"]: v["value"] for v in collection.get("variable", [])}

    if not items:
        print("No items in collection.", file=sys.stderr)
        sys.exit(1)

    iteration = 0
    try:
        while True:
            iteration += 1
            live_ids = {}
            if args.loop:
                print(f"\n=== Loop iteration {iteration} ===")
            run_once(items, col_vars, args, live_ids)
            if not args.loop:
                break
            cleanup_live(live_ids, col_vars, args)
            print("=== Loop complete; restarting ===")
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
