| Date | Change |
|------|--------|
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/988091ed) | Tide fit: count the fitted curve's turning points; the poster and the research carry the finding |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/5d47d74e) | The tide at Bangkok: an A3 poster, built |

<!--history-meta v1
988091ed	author	Will Norris
988091ed	added	1
988091ed	deleted	0
988091ed	files	1
988091ed	body	The fitted tide wiggles at flat tops: 1440 turns in 2026 where the Navy's table lists 1225 highs and lows.\ncount_turns.py measures it per year and for several thresholds; ignoring turns under 4 cm leaves within 3\nof the table in both years, while 10 cm drops 63 listed events. turning_points.json holds the result, the\nposter's accuracy panel quotes it (28 claims, no overflow) and the research explains it. A test keeps the\ncommitted counts in step with the constants. linux-test gains poppler-utils, which the poster test needs.\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
5d47d74e	author	Will Norris
5d47d74e	added	26
5d47d74e	deleted	0
5d47d74e	files	1
5d47d74e	body	Portrait A3 (297 x 420 mm), eight panels, 27 claims each chipped verified, other source or\nours, on the repository's poster pipeline. The research document comes first; make_poster.py\nrefuses to build on an unconfirmed claim, a verified claim with no source or an ours claim\nthat does not name what computes it. The numbers are read from tide_constants.json and\ntime_zone_check.json and from the Navy's printed table, not typed. The exporter reuses the\nseahorse poster's, changing only the PDF name.\n\nPanels: two highs a day or one; a sum of waves; spring and neap; a year of highs and lows;\nfrom a table to constants; how good it is (median 4.1-4.5 cm on an unseen year); which clock\nthe table uses; the harbour and what we do not know. Review found and fixed: a negative\nspring-neap period, a chip calling design statements measured, spikes in the year panel on\ndays with no low, a caption at 2.30:1 contrast, and a wrapped title. Nine tests pass, including\nan independent check of the period against NOAA's speeds and a contrast and size check on all\ndrawn text. Still open and not ours to tick: a person reads the printed-size proof, and the\nprint is on matte stock.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
-->
