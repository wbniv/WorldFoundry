#!/usr/bin/env python3
"""wf-asset — search and download licensed 3D assets from supported providers.

Usage:
  wf_asset.py search "tree" [--provider polyhaven] [--limit 20]
  wf_asset.py download polyhaven/medieval-tree-04 --dest wflevels/test/assets
  wf_asset.py policy show [--blend-dir .]
  wf_asset.py providers list
"""

import argparse
import os
import sys
from pathlib import Path

# Locate providers.py relative to this script. providers.py lives in the
# wf_asset_browser Blender add-on (which is where the shared
# provider-search/download logic was extracted to); the CLI imports it
# from there so the two front-ends share one source of truth.
sys.path.insert(0, str(Path(__file__).parent / "wf_asset_browser"))
import providers as _p


def cmd_search(args):
    policy = _p.load_policy(args.policy_dir)
    creds  = _p.Credentials(sketchfab_api_key=os.environ.get("WF_SKETCHFAB_API_KEY"))
    print(f"policy: {policy.policy_path or '(fallback — CC0 only)'}", file=sys.stderr)

    names = [n.strip() for n in args.provider.split(",")] if args.provider else None
    prov_map = (
        {n: _p._ALL_PROVIDERS[n] for n in names if n in _p._ALL_PROVIDERS}
        if names
        else _p._ALL_PROVIDERS
    )

    all_results = []
    for name, prov in prov_map.items():
        print(f"  searching {name}... ", end="", file=sys.stderr, flush=True)
        try:
            results = prov.search(args.query, policy, args.limit)
            results = [r for r in results if policy.allows(r.licence_id)]
            print(f"{len(results)} results", file=sys.stderr)
            all_results.extend(results)
        except Exception as e:
            print(f"FAILED: {e}", file=sys.stderr)

    all_results = all_results[: args.limit]
    print(f"\n{len(all_results)} results after policy filter:")
    for c in all_results:
        trust = "  ⚠ lower-trust" if c.lower_trust else ""
        print(f"  [{c.provider}/{c.provider_id}] {c.title:<50}  {c.licence_id}{trust}")


def cmd_download(args):
    parts = args.asset.split("/", 1)
    if len(parts) != 2:
        print("error: asset must be 'provider/asset-id'", file=sys.stderr)
        sys.exit(1)
    provider_name, asset_id = parts

    policy = _p.load_policy(args.policy_dir)
    creds  = _p.Credentials(sketchfab_api_key=os.environ.get("WF_SKETCHFAB_API_KEY"))

    prov = _p._ALL_PROVIDERS.get(provider_name)
    if prov is None:
        print(f"error: unknown provider {provider_name!r}", file=sys.stderr)
        sys.exit(1)

    print(f"resolving {args.asset}...", file=sys.stderr)
    try:
        results   = prov.search(asset_id, policy, 10)
        candidate = next((c for c in results if c.provider_id == asset_id), None)
    except Exception as e:
        candidate = None
        print(f"  search failed: {e}", file=sys.stderr)

    if candidate is None:
        print("  not found via search; attempting direct download", file=sys.stderr)
        candidate = _p.AssetCandidate(
            provider=provider_name,
            provider_id=asset_id,
            title=asset_id,
            thumbnail_url="",
            licence_id=_p.CC0,
            download_url="",
            original_url="",
            attribution_string="",
            attribution_required=False,
        )

    if not policy.allows(candidate.licence_id):
        print(f"error: licence {candidate.licence_id!r} not accepted by policy", file=sys.stderr)
        sys.exit(1)

    dest = Path(args.dest) / provider_name / asset_id
    print(f"downloading to {dest}...", file=sys.stderr)
    try:
        path, _ = _p.download(candidate, args.dest, credentials=creds)
        print(f"downloaded: {path}")
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_policy(args):
    policy = _p.load_policy(args.blend_dir)
    print(f"policy file: {policy.policy_path or '(not found — using fallback CC0-only)'}")
    accept = sorted(policy.accept_ids)
    reject = sorted(policy.reject_ids | policy.reject_default_ids)
    print(f"accept: {', '.join(accept)}")
    print(f"reject: {', '.join(reject)}")
    print(f"require_attribution_credits: {policy.require_attribution_credits}")


def cmd_providers(_args):
    for name in _p.PROVIDER_NAMES:
        print(name)


def main():
    parser = argparse.ArgumentParser(
        prog="wf-asset",
        description="World Foundry asset browser CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search providers for assets")
    p_search.add_argument("query", help='Search query, e.g. "tree"')
    p_search.add_argument("--provider", default="", metavar="NAME[,NAME]",
                          help="Restrict to specific provider(s), comma-separated")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--policy-dir", default=".", metavar="DIR")

    p_dl = sub.add_parser("download", help="Download an asset by provider/id")
    p_dl.add_argument("asset", help='Asset ID as "provider/asset-id"')
    p_dl.add_argument("--dest", required=True, metavar="DIR")
    p_dl.add_argument("--policy-dir", default=".", metavar="DIR")

    p_pol = sub.add_parser("policy", help="Show or manage the licence policy")
    p_pol_sub = p_pol.add_subparsers(dest="pol_cmd")
    p_show = p_pol_sub.add_parser("show")
    p_show.add_argument("--blend-dir", default=".", metavar="DIR")

    p_prov = sub.add_parser("providers", help="List registered providers")
    p_prov_sub = p_prov.add_subparsers(dest="prov_cmd")
    p_prov_sub.add_parser("list")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "policy":
        if getattr(args, "pol_cmd", None) == "show":
            cmd_policy(args)
        else:
            p_pol.print_help()
    elif args.command == "providers":
        cmd_providers(args)


if __name__ == "__main__":
    main()
