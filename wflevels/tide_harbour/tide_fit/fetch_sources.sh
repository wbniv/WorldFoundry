#!/usr/bin/env bash
# Fetch the public sources the tide fit uses, politely: one request per file, a pause between requests,
# and nothing re-fetched that is already in the cache.
#
#   fetch_sources.sh [CACHE_DIR]        (default: ~/tmp/chao-phraya-tide)
#
# Sources (all public, no login):
#   HD2026.pdf, HD2027.pdf  Royal Thai Navy Hydrographic Department, predicted highs and lows for station HD,
#                           Royal Thai Navy Headquarters (Bangkok Metropolitan). Index page:
#                           https://hydro.navy.mi.th/sevicetide (2026) and https://hydro.navy.mi.th/servicetide2570 (2027)
#   KL2026.pdf              the same department's table for Ko Lak, used only to check the table's time zone
#   h328.csv                UHSLC fast-delivery hourly sea level for Ko Lak (GMT, millimetres), for the same check
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

cache="${1:-$HOME/tmp/chao-phraya-tide}"
mkdir -p "$cache"
ua="Mozilla/5.0 (research; polite; one request per file)"

fetch() {
    local url="$1" out="$2"
    if [[ -s "$cache/$out" ]]; then
        echo "have   $out"
        return
    fi
    echo "fetch  $out  <-  $url"
    curl -sSL --fail --max-time 120 -A "$ua" -o "$cache/$out.part" "$url"
    mv "$cache/$out.part" "$cache/$out"
    sleep 3                                  # rate limit: be gentle with someone else's server
}

fetch "https://hydro.navy.mi.th/storage/frontend/article/23224/file/th/HD2026.pdf" HD2026.pdf
fetch "https://hydro.navy.mi.th/storage/frontend/article/23259/file/th/HD2027.pdf" HD2027.pdf
fetch "https://hydro.navy.mi.th/storage/frontend/article/23221/file/th/KL2026.pdf" KL2026.pdf
fetch "https://uhslc.soest.hawaii.edu/data/csv/fast/hourly/h328.csv" h328.csv
echo "cache: $cache"
sha256sum "$cache"/HD2026.pdf "$cache"/HD2027.pdf "$cache"/KL2026.pdf "$cache"/h328.csv
