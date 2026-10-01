#!/usr/bin/env bash
# find-chromecast.sh: find the Chromecast on the LAN after its DHCP lease moved it.
#
# Starts at the last known address and increments the last octet (then decrements it), asking each host's Cast
# descriptor (http://<ip>:8008/ssdp/device-desc.xml, no adb and no pairing needed) for its model, until the model
# matches. Prints:  <ip>  <modelName>  <friendlyName>   and remembers the address for next time.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: find-chromecast.sh [--from IP] [--span N] [--model REGEX] [--port N] [-h|--help]

Finds the Chromecast by walking the last octet of an address: IP, IP+1, IP+2 ... IP+N, then IP-1 ... IP-N.
Each host is asked for its Cast descriptor on port 8008 (no adb, no pairing); the first whose modelName matches
REGEX wins and is printed as "<ip>  <modelName>  <friendlyName>".

  --from IP       where to start (default: the remembered address in ~/.cache/wf/chromecast-ip, else 192.168.4.37)
  --span N        how far to walk each way (default 24)
  --model REGEX   modelName to match, extended regex (default "Chromecast")
  --port N        the Cast descriptor port (default 8008; the tests use a fake server on another port)
  -h, --help      this text

Exit 0 and the line above when found; exit 1 when nothing matched. adb over Wi-Fi still needs Wireless debugging
switched on at the TV and the port it shows: this script only answers "what is its address now".
EOF
}

FROM=""
SPAN=24
MODEL="Chromecast"
PORT=8008
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/wf/chromecast-ip"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --from)    FROM="${2:?--from needs an address}"; shift 2 ;;
        --span)    SPAN="${2:?--span needs a number}"; shift 2 ;;
        --model)   MODEL="${2:?--model needs a regex}"; shift 2 ;;
        --port)    PORT="${2:?--port needs a number}"; shift 2 ;;
        *)         echo "find-chromecast: unknown option $1 (see --help)" >&2; exit 2 ;;
    esac
done

if [[ -z "$FROM" ]]; then
    FROM="$(cat "$CACHE" 2>/dev/null || true)"
    FROM="${FROM:-192.168.4.37}"
fi
[[ "$FROM" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.([0-9]+)$ ]] || { echo "find-chromecast: '$FROM' is not an IPv4 address" >&2; exit 2; }
PREFIX="${BASH_REMATCH[1]}"
START="${BASH_REMATCH[2]}"

# Probe the candidates concurrently (a dead LAN address costs about a second to time out) but pick the answer nearest the
# walk order: START, START+1 ... START+SPAN, then START-1 ... START-SPAN.
export PREFIX START SPAN MODEL PORT CACHE
exec python3 - <<'PY'
import os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

prefix, start, span = os.environ["PREFIX"], int(os.environ["START"]), int(os.environ["SPAN"])
model_rx, port, cache = re.compile(os.environ["MODEL"]), int(os.environ["PORT"]), os.environ["CACHE"]

order = [start + d for d in range(0, span + 1)] + [start - d for d in range(1, span + 1)]
order = [n for n in order if 1 <= n <= 254]

def tag(name, body):
    m = re.search(rf"<{name}>([^<]*)</{name}>", body)
    return m.group(1) if m else ""

def probe(n):
    ip = f"{prefix}.{n}"
    try:
        body = urllib.request.urlopen(f"http://{ip}:{port}/ssdp/device-desc.xml", timeout=1.5).read().decode("utf-8", "replace")
    except Exception:
        return None
    return ip, tag("modelName", body), tag("friendlyName", body)

with ThreadPoolExecutor(max_workers=16) as pool:
    results = list(pool.map(probe, order))          # map keeps the walk order

for r in results:
    if r and model_rx.search(r[1]):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        open(cache, "w").write(r[0] + "\n")
        print(f"{r[0]}\t{r[1]}\t{r[2]}")
        sys.exit(0)

print(f"find-chromecast: no host matching '{model_rx.pattern}' within {span} of {prefix}.{start} on port {port} (is the TV on and on this network?)", file=sys.stderr)
sys.exit(1)
PY
