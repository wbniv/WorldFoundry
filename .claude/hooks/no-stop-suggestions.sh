#!/usr/bin/env bash
# Stop hook: block a reply whose LAST LINE is a "wind-down" / stop-suggestion
# closer aimed at the user.
#
# The user banned these (memory feedback_no_stop_suggestions): "good stopping
# point", "good place to pause/stop", "whenever you're ready", or a self-
# congratulatory "N commits/landings this session" tally. On a match we return
# decision:"block" with a reason, forcing a rewrite WITHOUT the closer.
#
# EXCEPTION (user-approved): Claude genuinely asking for a break / saying it is
# tired is fine — only telling the USER to stop is banned.
#
# Only the last non-empty line is inspected, so quoting a banned phrase earlier
# in the message (e.g. while explaining this hook) does not trip it. Reads the
# Stop-hook JSON from stdin; never fails the turn (exit 0 always).

set -euo pipefail

input=$(cat)
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[[ -n "$transcript" && -f "$transcript" ]] || exit 0

# Text of the last assistant message in the transcript (join its text blocks).
text=$(jq -rs '
  (map(select(.type == "assistant")) | last) // {}
  | (.message.content // [])
  | map(select(.type == "text") | .text) | join("\n")
' "$transcript" 2>/dev/null || true)
[[ -n "$text" ]] || exit 0

# The ENDING: the final sentence of the last non-empty line. Closers live here;
# a banned phrase quoted in an EARLIER sentence (e.g. while explaining this hook)
# is left alone.
last_line=$(printf '%s\n' "$text" | awk 'NF{l=$0} END{print l}')
ending=$(printf '%s' "$last_line" | sed -E 's/([.!?]) +/\1\n/g' | awk 'NF{l=$0} END{print l}')

# Banned user-facing closers ("." stands in for apostrophes so the pattern stays
# a clean single-quoted string).
pattern='stopping point|good place to (pause|stop|wrap up|wind down|leave it|break)|place to (pause|wrap up)|whenever you.?re ready|let me know if you.?(d like|want)[^.]{0,40}next|(landing|commit|fix|change)s? this session'

# User-approved exception: Claude requesting a break for itself is fine.
allow='tired|a break|step(ping)? away|call it (a day|here|for now)'

if printf '%s' "$ending" | grep -iqE "$pattern" \
   && ! printf '%s' "$ending" | grep -iqE "$allow"; then
    hit=$(printf '%s' "$ending" | grep -ioE "$pattern" | head -1)
    reason="Your reply ended with a forbidden wind-down/stop-suggestion closer (\"$hit\"). The user banned these (memory feedback_no_stop_suggestions) — only telling THEM to stop, not you asking for a break. Re-send the SAME reply with that closing phrase deleted, ending on the result/status. (If you genuinely want a break, say so explicitly — that is allowed.)"
    jq -n --arg r "$reason" '{decision: "block", reason: $r}'
    exit 0
fi

exit 0
